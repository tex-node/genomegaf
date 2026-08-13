# Porting to MQL5 — what changes and why

This Python prototype is deliberately written so every step maps to a
straightforward MQL5 equivalent. Nothing here relies on Python-only
tricks. Below is what to change, in priority order.

## 1. ATR — make it incremental (O(1) per bar, not O(n))

`gaf_core.atr()` recomputes the whole series every call, which is fine
for a backtest but wasteful in `OnCalculate()`. MQL5 already has a
built-in `iATR()` — just call that instead of reimplementing Wilder's
smoothing. Don't port the Python ATR function at all; use the native
indicator handle.

## 2. Normalization — same formula, just per-bar

```mql5
double logRet = MathLog(close[i] / close[i-1]);
double x = logRet / atrBuffer[i];
```

Store the last `window` values of `x` in a circular buffer (a simple
`double x_buf[]` array with a rolling write index — MQL5 doesn't need
anything fancier than that).

## 3. GAF encoding — direct translation

The min-max rescale, `arccos`, and `cos(phi_i+phi_j)` all have direct
MQL5 equivalents (`MathArccos`, `MathMin`/`MathMax` over the window,
`MathCos`). This is the one part of the pipeline that's genuinely
O(N²) per bar (N = window length, typically 10–30), which is trivial
at that size — don't worry about optimizing it.

**Important:** keep the min-max rescale (not the fixed-`k` version).
That's the piece that makes the "same shape, different volatility
regime" matching actually work, and it's exactly as cheap to compute
in MQL5 as the fixed version.

## 4. The pattern database — this is the part that needs real thought

`pattern_db.py`'s ring buffer + vectorized `fps @ live_unit` dot
product works because numpy does the N_history × fingerprint_len
matmul in optimized C. MQL5 has no equivalent BLAS call (pre-3000
builds don't have a matrix type at all; even in newer builds, a
manual loop is usually simpler and fast enough for this size).

Two practical options:
- **Small DB (a few thousand fingerprints):** a plain nested loop —
  for each stored fingerprint, compute the dot product against the
  live one in an inner loop over the fingerprint's length. At
  window=20 the fingerprint is 190 floats; a few thousand of those is
  well within what MT5 can do every bar without lag.
- **Larger DB:** cap it with a hard `max_size` (exactly like the
  Python ring buffer) rather than letting it grow unbounded — MT5
  indicators run on every tick, so an ever-growing linear scan will
  eventually cause visible lag on the chart.

Either way, keep the DB in an MQL5 array of structs (`fingerprint[]`,
`bar_index`, `close`), not in a file or database engine — file I/O on
every tick will absolutely wreck performance.

## 5. Projection — trivial, no changes needed

Mean/std of forward returns over the matched set is a plain loop.
Nothing here needs special handling.

## 6. Things that will bite you if skipped

- **No look-ahead:** the Python version enforces `(current_bar -
  bar_index) >= horizon` before a stored fingerprint counts as a
  usable match — i.e., its outcome must have already happened. Copy
  this check exactly; it's the single easiest way to accidentally
  build an indicator that looks great in backtest and is worthless
  live.
- **Recompute window on every new bar, not every tick**, unless you
  specifically want intra-bar updates — use `IsNewBar()` gating, or
  MT5's `OnCalculate` will thrash recomputing GAF matrices tick by
  tick for no benefit.
- **Warm-up period:** the indicator needs `atr_period + window + 1`
  closed bars before it produces anything (see `on_bar()`'s `needed`
  check) — don't plot/trade off it before then.
