# GAF Pattern-Recognition Indicator — Python Prototype

Implements the pipeline from the blueprint: ATR-normalized returns →
Gramian Angular Field encoding → flattened fingerprint → rolling
historical database → cosine-similarity matching → forward-return
projection.

## Files

- `gaf_core.py` — normalization, GAF encoding, fingerprint extraction
- `pattern_db.py` — rolling fingerprint database + vectorized similarity search
- `projection.py` — forward-return statistics and confidence scoring
- `gaf_indicator.py` — stateful `GAFIndicator` class, one `on_bar()` call per closed bar
- `data_loader.py` — CSV loader for real OHLC data (MT5 exports and plain high/low/close CSVs)
- `demo.py` — synthetic-data smoke test + backtest + visualizations (`--csv path.csv` to use real data)
- `web/dashboard.html` — self-contained, in-browser reimplementation of the whole pipeline for
  interactive testing (no Python required) — see below
- `PORTING_NOTES.md` — what changes when you port this to MQL5

## Interactive testing dashboard

`web/dashboard.html` is a single self-contained HTML/JS file that reimplements the entire
pipeline (ATR, normalization, GAF encoding, pattern DB, projection) in the browser, so you can
test the indicator without running Python. Open it directly, or serve it locally:

```bash
node .claude/serve.js   # serves web/ on http://localhost:8842
```

From the dashboard you can:
- Generate the same kind of synthetic demo data as `demo.py`, or upload a real OHLC CSV
  (high/low/close columns, MT5 export headers like `<HIGH>` are recognized)
- Tune `window`, `atr_period`, `horizon`, method, similarity threshold, min matches, and DB size
- Run the backtest and see live KPIs, price/signal/equity charts, and an interactive GAF
  fingerprint heatmap for any bar
- A "Limit bars" control caps runtime, since similarity search is O(bars²)

A hosted copy (for quick testing without cloning the repo) is linked from the repo description.

## Quick start

```bash
python3 demo.py
```

Produces `backtest_overview.png` (price / signal / toy equity) and
`gaf_example.png` (one actual GAF matrix, so you can see the
"fingerprint" it's matching on).

## Using your own data

Replace `make_synthetic_data()` in `demo.py` with a loader for your
MT5-exported CSV (needs high/low/close arrays), then feed bars through
`GAFIndicator.on_bar()` in order:

```python
from gaf_indicator import GAFIndicator, GAFIndicatorConfig

ind = GAFIndicator(GAFIndicatorConfig(window=20, atr_period=14, horizon=10))
for i, (h, l, c) in enumerate(zip(high, low, close)):
    signal = ind.on_bar(i, h, l, c)
    if signal is not None and signal.n_matches >= 5:
        print(i, signal.direction, signal.confidence, signal.n_matches)
```

## One bug I hit and fixed — worth knowing about

The blueprint's rescale step (`clamp(x_t * k, -1, 1)` with a fixed
constant `k`) doesn't actually work: ATR-normalized log returns are
tiny (~0.01 in magnitude), so a fixed `k` either clips almost
everything to the same value or leaves everything clustered near
`arccos(0)` — either way, every window's GAF matrix comes out nearly
identical, and the "similarity search" silently degenerates into
"matches almost everything." I caught this because the first GAF
matrix I plotted was a flat, single-color square, and the demo's match
count was an absurd ~1,488 matches per bar.

The fix (and what's actually in `gaf_core.py` now) is **per-window
min-max rescaling** into [-1, 1] — the standard approach in the GAF
literature. It's also arguably a *better* realization of the
"fractal/volatility-independence" property the blueprint wants, since
it self-calibrates to each window rather than depending on a hand-picked
constant.

## A second bug: same-bar look-ahead in the toy P&L simulation

`demo.py`'s backtest loop used to apply each bar's signal to that same
bar's *already-realized* return, instead of the next bar's — a classic
look-ahead bug, separate from (and in addition to) the GAF rescale bug
above. It's subtle because the pattern-matching itself was already
correctly look-ahead-free (a match only counts once its forward outcome
has happened); the bug was only in how the resulting position was wired
into the equity curve.

This wasn't just "slightly optimistic" — it was actively misleading,
because the fingerprint window's *last* data point IS that same-bar
return (in normalized form), so the buggy version was partly scoring the
signal against a value baked into its own input. After fixing it (see
`validation.py`'s `apply_positions()`, and the equivalent fix in
`demo.py` and `web/dashboard.html`), the synthetic-data backtest result
**flipped from losing money to +157% (2.57x)**.

That flip is actually reassuring, not alarming: the synthetic data has
*real* injected repeating motifs (see `make_synthetic_data()`), so a
correctly-wired matcher finding and profiting from genuine repeating
structure is the expected good outcome. The original "loses money"
result was itself an artifact of the bug, not evidence the mechanism
was sound — this project's earlier claim that a losing synthetic
backtest was "the correct outcome to expect" no longer holds now that
the bug is fixed.

## Honest state of the results

Synthetic-data validation now shows the matcher both finding the
injected motifs *and* profiting from them once the look-ahead bug above
is fixed — a meaningfully stronger validation of the mechanism than
before. That still isn't evidence it works on real markets. Real
validation — walk-forward train/test splits, real transaction costs,
statistical significance testing against a random baseline, and
parameter selection that never touches the data it's scored on — now
lives in `validation.py` / `run_validation.py`, which runs the full
pipeline against real MT5 history for US500, US100, DJIA, EUR/USD, and
XAU/USD. See `VALIDATION_REPORT.md` (generated by that script) for
current, instrument-by-instrument results — read its "Honest caveats"
section before treating any of it as a green light to trade real money.

## Reasonable next steps

1. ~~Feed it real OHLC data and re-run the backtest~~ — done, see
   `mt5_feed.py` / `yahoo_feed.py` / `run_validation.py`.
2. ~~Add walk-forward validation~~ — done, see `validation.py`'s
   `select_best_config()` and the dev/holdout split in
   `run_validation.py`.
3. ~~Tune `window`, `horizon`, and `similarity_threshold`~~ — done via
   walk-forward cross-validated grid search per instrument; see
   `VALIDATION_REPORT.md` for the chosen values and whether they held up
   out-of-sample.
4. Widen `run_validation.py`'s `PARAM_GRID` and re-run periodically —
   it's intentionally narrowed for runtime, and markets drift, so a
   config validated once won't stay valid forever.
5. If `VALIDATION_REPORT.md` shows a real, statistically-significant
   edge on an instrument: forward-test it via `live_signal.py` on a demo
   account for a real out-of-sample stretch before trusting it with
   capital — a single historical holdout period is not enough evidence
   on its own.
6. Once you're happy with the signal quality in Python, port using
   `PORTING_NOTES.md`.
