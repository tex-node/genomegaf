# Validation report — GenomeGAF (D1)

Generated 2026-08-14 01:47 UTC. Timeframe: D1. Bar budget: 2000. Development/holdout split: 60/40. Walk-forward CV folds: 3. Monte Carlo sims: 2000.

**Methodology:** for each instrument, the first 60% of history is a development slice used only to pick pipeline parameters via walk-forward cross-validation (pattern DB trained on progressively larger prefixes, tested on the next held-out chunk, DB frozen during each test chunk). The chosen parameters are then evaluated exactly once on the final holdout slice, which neither the parameter search nor the pattern DB has ever seen. All P&L figures include a real, broker-quoted round-turn transaction cost and lag every position decision by one bar (no same-bar look-ahead). Statistical significance is assessed two ways: a binomial test on directional hit rate, and a Monte Carlo comparison against a random-direction baseline with identical trade timing and sizing.

## US500
- Symbol: `US500cash-1` (MT5) — 1426 D1 bars (2021-07-13 to 2026-08-13)
- Round-turn transaction cost used: 0.97 bps
- Yahoo cross-check: 1278 overlapping bars, hourly-return correlation = 0.9677
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 855 bars (development slice, never touches holdout)
- Selected: window=10, horizon=5, threshold=0.9 (mean fold Sharpe +0.000)

**Holdout results (571 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 571 |
| Bars with an active (non-zero) direction | 12 |
| Total return | -0.88% |
| CAGR | -0.40% |
| Sharpe (annualized) | -0.986 |
| Sortino (annualized) | -0.185 |
| Max drawdown | -0.92% |
| Profit factor | 0.099 |
| Win rate (active bars) | +18.18% |
| Hit rate (direction sign vs realized sign) | +58.33% (n=12, p=0.5637) |
| Random-direction MC baseline | mean final equity 1.000, real result at percentile +2.95% of 2000 sims |

**Read:** Too few holdout signals to draw a statistical conclusion — needs more history or looser thresholds.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe -0.795, total return -1.80%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## US100
- Symbol: `US100cash-1` (MT5) — 1426 D1 bars (2021-07-13 to 2026-08-13)
- Round-turn transaction cost used: 0.41 bps
- Yahoo cross-check: 1278 overlapping bars, hourly-return correlation = 0.9564
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 855 bars (development slice, never touches holdout)
- Selected: window=10, horizon=5, threshold=0.9 (mean fold Sharpe +0.000)

**Holdout results (571 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 571 |
| Bars with an active (non-zero) direction | 9 |
| Total return | -0.81% |
| CAGR | -0.37% |
| Sharpe (annualized) | -0.515 |
| Sortino (annualized) | -0.088 |
| Max drawdown | -1.26% |
| Profit factor | 0.501 |
| Win rate (active bars) | +29.41% |
| Hit rate (direction sign vs realized sign) | +44.44% (n=9, p=0.7389) |
| Random-direction MC baseline | mean final equity 0.999, real result at percentile +24.45% of 2000 sims |

**Read:** Too few holdout signals to draw a statistical conclusion — needs more history or looser thresholds.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe 0.054, total return +0.13%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## DJIA
- Symbol: `US30cash-1` (MT5) — 1426 D1 bars (2021-07-13 to 2026-08-13)
- Round-turn transaction cost used: 0.26 bps
- Yahoo cross-check: 1278 overlapping bars, hourly-return correlation = 0.9789
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 855 bars (development slice, never touches holdout)
- Selected: window=10, horizon=5, threshold=0.9 (mean fold Sharpe +0.011)

**Holdout results (571 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 571 |
| Bars with an active (non-zero) direction | 18 |
| Total return | +1.28% |
| CAGR | +0.58% |
| Sharpe (annualized) | 0.753 |
| Sortino (annualized) | 0.405 |
| Max drawdown | -0.44% |
| Profit factor | 2.425 |
| Win rate (active bars) | +33.33% |
| Hit rate (direction sign vs realized sign) | +50.00% (n=18, p=1.0000) |
| Random-direction MC baseline | mean final equity 1.000, real result at percentile +86.30% of 2000 sims |

**Read:** Too few holdout signals to draw a statistical conclusion — needs more history or looser thresholds.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe 0.146, total return +0.53%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## EURUSD
- Symbol: `EURUSD` (MT5) — 2000 D1 bars (2020-02-14 to 2026-08-13)
- Round-turn transaction cost used: 0.27 bps
- Yahoo cross-check: 1670 overlapping bars, hourly-return correlation = 0.5886
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 1200 bars (development slice, never touches holdout)
- Selected: window=10, horizon=5, threshold=0.9 (mean fold Sharpe +0.035)

**Holdout results (800 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 800 |
| Bars with an active (non-zero) direction | 109 |
| Total return | -0.26% |
| CAGR | -0.10% |
| Sharpe (annualized) | -0.249 |
| Sortino (annualized) | -0.126 |
| Max drawdown | -0.60% |
| Profit factor | 0.896 |
| Win rate (active bars) | +38.00% |
| Hit rate (direction sign vs realized sign) | +46.79% (n=109, p=0.5026) |
| Random-direction MC baseline | mean final equity 0.999, real result at percentile +43.55% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe 0.419, total return +1.09%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## XAUUSD
- Symbol: `XAUUSD` (MT5) — 2000 D1 bars (2020-01-31 to 2026-08-13)
- Round-turn transaction cost used: 1.46 bps
- Yahoo cross-check: 1644 overlapping bars, hourly-return correlation = 0.8969
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 1200 bars (development slice, never touches holdout)
- Selected: window=10, horizon=5, threshold=0.95 (mean fold Sharpe +0.000)

**Holdout results (800 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 800 |
| Bars with an active (non-zero) direction | 3 |
| Total return | +0.78% |
| CAGR | +0.29% |
| Sharpe (annualized) | 0.929 |
| Sortino (annualized) | 9.620 |
| Max drawdown | -0.00% |
| Profit factor | 88.740 |
| Win rate (active bars) | +50.00% |
| Hit rate (direction sign vs realized sign) | +66.67% (n=3, p=0.5637) |
| Random-direction MC baseline | mean final equity 1.000, real result at percentile +87.95% of 2000 sims |

**Read:** Too few holdout signals to draw a statistical conclusion — needs more history or looser thresholds.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe 0.578, total return +0.69%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## Summary

| Instrument | Holdout Sharpe | Hit rate (p-value) | Beats random baseline? | Verdict |
|---|---|---|---|---|
| US500 | -0.986 | +58.33% (p=0.5637) | no | Too few holdout signals to draw a statistical conclusion — needs more history or... |
| US100 | -0.515 | +44.44% (p=0.7389) | no | Too few holdout signals to draw a statistical conclusion — needs more history or... |
| DJIA | 0.753 | +50.00% (p=1.0000) | no | Too few holdout signals to draw a statistical conclusion — needs more history or... |
| EURUSD | -0.249 | +46.79% (p=0.5026) | no | No statistically significant edge over chance on this holdout slice. Matches the... |
| XAUUSD | 0.929 | +66.67% (p=0.5637) | no | Too few holdout signals to draw a statistical conclusion — needs more history or... |

## Honest caveats — read before trading any of this

- This is one holdout slice per instrument, not multiple independent out-of-sample periods across different market regimes. A single passing result is encouraging, not proof.
- Transaction costs used are current spread snapshots (or fallback assumptions where MT5 reported a stale/zero spread) — they don't model slippage, widened spreads during news/volatility, or commission.
- Position sizing (3x confidence, clipped to [-1,1]) is illustrative, not risk-managed. There is no stop-loss, max-drawdown circuit breaker, or correlation-aware sizing across instruments here.
- No instrument here was tested through a genuinely different regime (e.g. a volatility shock or trend reversal) unless one happened to fall in its holdout window by chance.
- Signals-only mode is what's implemented — nothing in this repository places live orders.
