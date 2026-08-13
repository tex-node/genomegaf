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

## Honest state of the results

On synthetic data (random walk with injected repeating motifs at
different scales — see `make_synthetic_data()`), the matcher correctly
finds those motifs across volatility regimes, which validates the
mechanism. But the toy backtest *loses* money on that same synthetic
data, and that's the correct outcome to expect — there's no real
tradable structure in synthetic noise. The equity curve is not
evidence the strategy works; it only confirms the pipeline isn't
broken. Real validation requires running this on actual historical
price data with proper walk-forward testing, transaction costs, and
out-of-sample splits — none of which this prototype does yet.

## Reasonable next steps

1. Feed it real OHLC data (MT5 export) and re-run `demo.py`'s backtest
   logic against it.
2. Add walk-forward validation (train DB on data up to time T, test
   only on bars after T) — the current backtest technically avoids
   look-ahead bias per-bar, but doesn't separate "training" and
   "testing" periods, which real validation needs.
3. Tune `window`, `horizon`, and `similarity_threshold` — these were
   picked for the demo, not optimized.
4. Once you're happy with the signal quality in Python, port using
   `PORTING_NOTES.md`.
