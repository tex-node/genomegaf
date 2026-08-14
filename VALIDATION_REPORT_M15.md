# Validation report — GenomeGAF (M15)

Generated 2026-08-14 01:49 UTC. Timeframe: M15. Bar budget: 12000. Development/holdout split: 60/40. Walk-forward CV folds: 3. Monte Carlo sims: 2000.

**Methodology:** for each instrument, the first 60% of history is a development slice used only to pick pipeline parameters via walk-forward cross-validation (pattern DB trained on progressively larger prefixes, tested on the next held-out chunk, DB frozen during each test chunk). The chosen parameters are then evaluated exactly once on the final holdout slice, which neither the parameter search nor the pattern DB has ever seen. All P&L figures include a real, broker-quoted round-turn transaction cost and lag every position decision by one bar (no same-bar look-ahead). Statistical significance is assessed two ways: a binomial test on directional hit rate, and a Monte Carlo comparison against a random-direction baseline with identical trade timing and sizing.

## US500
- Symbol: `US500cash-1` (MT5) — 12000 M15 bars (2026-02-11 to 2026-08-14)
- Round-turn transaction cost used: 0.69 bps
- Yahoo cross-check: 1560 overlapping bars, hourly-return correlation = 0.2122
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 7200 bars (development slice, never touches holdout)
- Selected: window=20, horizon=10, threshold=0.95 (mean fold Sharpe +0.005)

**Holdout results (4800 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 4800 |
| Bars with an active (non-zero) direction | 171 |
| Total return | -0.30% |
| CAGR | -1.49% |
| Sharpe (annualized) | -3.418 |
| Sortino (annualized) | -1.030 |
| Max drawdown | -0.41% |
| Profit factor | 0.693 |
| Win rate (active bars) | +29.31% |
| Hit rate (direction sign vs realized sign) | +46.20% (n=171, p=0.3202) |
| Random-direction MC baseline | mean final equity 0.997, real result at percentile +46.70% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe -2.274, total return -0.53%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## US100
- Symbol: `US100cash-1` (MT5) — 12000 M15 bars (2026-02-11 to 2026-08-14)
- Round-turn transaction cost used: 0.27 bps
- Yahoo cross-check: 1560 overlapping bars, hourly-return correlation = 0.2932
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 7200 bars (development slice, never touches holdout)
- Selected: window=10, horizon=5, threshold=0.9 (mean fold Sharpe +0.002)

**Holdout results (4800 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 4800 |
| Bars with an active (non-zero) direction | 1572 |
| Total return | -0.83% |
| CAGR | -4.12% |
| Sharpe (annualized) | -1.029 |
| Sortino (annualized) | -0.906 |
| Max drawdown | -1.48% |
| Profit factor | 0.961 |
| Win rate (active bars) | +36.38% |
| Hit rate (direction sign vs realized sign) | +48.69% (n=1567, p=0.3003) |
| Random-direction MC baseline | mean final equity 0.984, real result at percentile +67.65% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe -0.694, total return -1.14%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## DJIA
- Symbol: `US30cash-1` (MT5) — 12000 M15 bars (2026-02-11 to 2026-08-14)
- Round-turn transaction cost used: 0.20 bps
- Yahoo cross-check: 1560 overlapping bars, hourly-return correlation = 0.1876
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 7200 bars (development slice, never touches holdout)
- Selected: window=10, horizon=5, threshold=0.95 (mean fold Sharpe +0.018)

**Holdout results (4800 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 4800 |
| Bars with an active (non-zero) direction | 261 |
| Total return | -0.06% |
| CAGR | -0.29% |
| Sharpe (annualized) | -0.635 |
| Sortino (annualized) | -0.252 |
| Max drawdown | -0.27% |
| Profit factor | 0.948 |
| Win rate (active bars) | +30.33% |
| Hit rate (direction sign vs realized sign) | +41.63% (n=257, p=0.0073) |
| Random-direction MC baseline | mean final equity 0.998, real result at percentile +69.30% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe -0.161, total return -0.04%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## EURUSD
- Symbol: `EURUSD` (MT5) — 12000 M15 bars (2026-02-20 to 2026-08-14)
- Round-turn transaction cost used: 0.35 bps
- Yahoo cross-check: 5564 overlapping bars, hourly-return correlation = 0.0105
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 7200 bars (development slice, never touches holdout)
- Selected: window=20, horizon=5, threshold=0.95 (mean fold Sharpe -0.005)

**Holdout results (4800 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 4800 |
| Bars with an active (non-zero) direction | 93 |
| Total return | -0.14% |
| CAGR | -0.74% |
| Sharpe (annualized) | -4.325 |
| Sortino (annualized) | -0.831 |
| Max drawdown | -0.17% |
| Profit factor | 0.465 |
| Win rate (active bars) | +25.19% |
| Hit rate (direction sign vs realized sign) | +48.39% (n=93, p=0.7557) |
| Random-direction MC baseline | mean final equity 0.999, real result at percentile +22.40% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe -2.546, total return -0.15%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## XAUUSD
- Symbol: `XAUUSD` (MT5) — 12000 M15 bars (2026-02-11 to 2026-08-14)
- Round-turn transaction cost used: 0.77 bps
- Yahoo cross-check: 4354 overlapping bars, hourly-return correlation = 0.0415
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 7200 bars (development slice, never touches holdout)
- Selected: window=20, horizon=10, threshold=0.95 (mean fold Sharpe +0.023)

**Holdout results (4800 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 4800 |
| Bars with an active (non-zero) direction | 175 |
| Total return | -0.50% |
| CAGR | -2.50% |
| Sharpe (annualized) | -2.462 |
| Sortino (annualized) | -0.503 |
| Max drawdown | -0.78% |
| Profit factor | 0.723 |
| Win rate (active bars) | +38.05% |
| Hit rate (direction sign vs realized sign) | +50.86% (n=175, p=0.8206) |
| Random-direction MC baseline | mean final equity 0.997, real result at percentile +38.30% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe -1.606, total return -0.68%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## Summary

| Instrument | Holdout Sharpe | Hit rate (p-value) | Beats random baseline? | Verdict |
|---|---|---|---|---|
| US500 | -3.418 | +46.20% (p=0.3202) | no | No statistically significant edge over chance on this holdout slice. Matches the... |
| US100 | -1.029 | +48.69% (p=0.3003) | no | No statistically significant edge over chance on this holdout slice. Matches the... |
| DJIA | -0.635 | +41.63% (p=0.0073) | no | No statistically significant edge over chance on this holdout slice. Matches the... |
| EURUSD | -4.325 | +48.39% (p=0.7557) | no | No statistically significant edge over chance on this holdout slice. Matches the... |
| XAUUSD | -2.462 | +50.86% (p=0.8206) | no | No statistically significant edge over chance on this holdout slice. Matches the... |

## Honest caveats — read before trading any of this

- This is one holdout slice per instrument, not multiple independent out-of-sample periods across different market regimes. A single passing result is encouraging, not proof.
- Transaction costs used are current spread snapshots (or fallback assumptions where MT5 reported a stale/zero spread) — they don't model slippage, widened spreads during news/volatility, or commission.
- Position sizing (3x confidence, clipped to [-1,1]) is illustrative, not risk-managed. There is no stop-loss, max-drawdown circuit breaker, or correlation-aware sizing across instruments here.
- No instrument here was tested through a genuinely different regime (e.g. a volatility shock or trend reversal) unless one happened to fall in its holdout window by chance.
- Signals-only mode is what's implemented — nothing in this repository places live orders.
