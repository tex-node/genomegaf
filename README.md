# GAF Pattern-Recognition Indicator — Python Prototype

**Project status: closed, no tradable edge found.** See
[`CLAUDE.md`](CLAUDE.md) for the final conclusion and what was tested
before picking this back up.

Implements the pipeline from the blueprint: ATR-normalized returns →
Gramian Angular Field encoding → flattened fingerprint → rolling
historical database → cosine-similarity matching → forward-return
projection.

## Files

- `gaf_core.py` — normalization (ATR and rank/quantile variants), GAF encoding, fingerprint extraction
- `regime.py` — trend×volatility regime labeling, for regime-conditional pattern matching
- `pattern_db.py` — rolling fingerprint database + vectorized similarity search (optionally regime-filtered)
- `projection.py` — forward-return statistics, confidence scoring, recency-decay weighting, skew
- `gaf_indicator.py` — stateful `GAFIndicator` class, one `on_bar()` call per closed bar
- `data_loader.py` — CSV loader for real OHLC data (MT5 exports and plain high/low/close CSVs)
- `mt5_feed.py` / `yahoo_feed.py` — real market data connectors (read-only; no order placement anywhere)
- `validation.py` / `run_validation.py` — walk-forward CV, holdout evaluation, transaction costs,
  significance testing against real MT5 history — see `VALIDATION_REPORT.md`
- `live_signal.py` — signals-only live watcher (prints/logs; never places an order)
- `demo.py` — synthetic-data smoke test + backtest + visualizations (`--csv path.csv` to use real data)
- `web/dashboard.html` — self-contained, in-browser reimplementation of the whole pipeline for
  interactive testing (no Python required) — see below
- `PORTING_NOTES.md` — what changes when you port this to MQL5

## v2 review — rank normalization, regime filtering, recency decay

A separate Claude session (working from an earlier fork of this code, before
the look-ahead-bug fix and the MT5 validation pipeline existed here) added
four features on top of the original prototype: rank/quantile normalization
as an alternative to ATR division, regime-conditional pattern matching
(9-state trend×volatility buckets), recency-decay weighted statistics, and
return-distribution skew. The ideas were sound and the session was
appropriately skeptical of its own results (it ran an 8-seed synthetic
comparison rather than trusting one favorable run, and caught a real bug
mid-build). But its own backtest loop still had the same-bar look-ahead bug
this repo already fixed, and it was never tested against real market data.

Those four features have been ported into this repo's validated codebase
(`gaf_core.rank_normalize_series`, `regime.py`, the regime filter in
`pattern_db.PatternDB.query()`, and the recency/skew additions in
`projection.py`) — keeping this repo's `learn`-flag true walk-forward
freeze rather than the fork's leakier "burn-in" approach — and tested the
same rigorous way as the rest of this project:
`py run_validation.py --feature-set enhanced`. See `VALIDATION_REPORT.md`'s
"Round 2" section for the result: more interesting than the plain baseline
(the first batch of nominally p<0.05 results in this project), but none of
them survive even a simple correction for running 5 tests in one batch —
encouraging enough to warrant one more independent check, not yet enough
to trade.

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
XAU/USD on H1, M15, and D1 timeframes. **Result: no statistically
significant directional edge on any instrument, on any of the three
timeframes tested.** See [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)
for the combined summary (including why the one nominally-significant
cell across 11 tests is very likely a multiple-comparisons false
positive, not a real edge), or the per-timeframe reports
(`VALIDATION_REPORT_H1.md`, `_M15.md`, `_D1.md`) for full detail — read
the "Honest caveats" sections before treating any of it as a green light
to trade real money.

## Reasonable next steps

1. ~~Feed it real OHLC data and re-run the backtest~~ — done, see
   `mt5_feed.py` / `yahoo_feed.py` / `run_validation.py`.
2. ~~Add walk-forward validation~~ — done, see `validation.py`'s
   `select_best_config()` and the dev/holdout split in
   `run_validation.py`.
3. ~~Tune `window`, `horizon`, and `similarity_threshold`~~ — done via
   walk-forward cross-validated grid search per instrument, across three
   timeframes; see `VALIDATION_REPORT.md` for the outcome (no edge found).
4. Widen `run_validation.py`'s `PARAM_GRID` — it's intentionally narrowed
   for runtime. Given the current results, widening it is exploratory,
   not a fix for a known-close result.
5. If a future `run_validation.py` run ever shows a real,
   statistically-significant edge on an instrument (correcting for
   multiple comparisons — see `VALIDATION_REPORT.md`'s note on that):
   forward-test it via `live_signal.py` on a demo account for a real
   out-of-sample stretch before trusting it with capital. A single
   historical holdout period is not enough evidence on its own, and
   nothing validated so far clears that bar.
6. Once you're happy with the signal quality in Python, port using
   `PORTING_NOTES.md`.
