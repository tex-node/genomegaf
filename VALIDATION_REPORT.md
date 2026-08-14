# Validation report — GenomeGAF

Generated 2026-08-13 21:34 UTC. Timeframe: H1. Development/holdout split: 60/40. Walk-forward CV folds: 3. Monte Carlo sims: 2000.

**Methodology:** for each instrument, the first 60% of history is a development slice used only to pick pipeline parameters via walk-forward cross-validation (pattern DB trained on progressively larger prefixes, tested on the next held-out chunk, DB frozen during each test chunk). The chosen parameters are then evaluated exactly once on the final holdout slice, which neither the parameter search nor the pattern DB has ever seen. All P&L figures include a real, broker-quoted round-turn transaction cost and lag every position decision by one bar (no same-bar look-ahead). Statistical significance is assessed two ways: a binomial test on directional hit rate, and a Monte Carlo comparison against a random-direction baseline with identical trade timing and sizing.

## US500
- Symbol: `US500cash-1` (MT5) — 8000 H1 bars
- Round-turn transaction cost used: 0.60 bps
- Yahoo cross-check: 2374 overlapping bars, hourly-return correlation = 0.2750
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 4800 bars (development slice, never touches holdout)
- Selected: window=10, horizon=10, threshold=0.95 (mean fold Sharpe +0.001)

**Holdout results (3200 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 3200 |
| Bars with an active (non-zero) direction | 181 |
| Total return | -0.67% |
| CAGR | -1.24% |
| Sharpe (annualized) | -1.206 |
| Sortino (annualized) | -0.337 |
| Max drawdown | -0.97% |
| Profit factor | 0.735 |
| Win rate (active bars) | +32.85% |
| Hit rate (direction sign vs realized sign) | +53.98% (n=176, p=0.2913) |
| Random-direction MC baseline | mean final equity 0.997, real result at percentile +35.10% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe -0.942, total return -1.03%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## US100
- Symbol: `US100cash-1` (MT5) — 8000 H1 bars
- Round-turn transaction cost used: 0.30 bps
- Yahoo cross-check: 2374 overlapping bars, hourly-return correlation = 0.2879
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 4800 bars (development slice, never touches holdout)
- Selected: window=10, horizon=5, threshold=0.95 (mean fold Sharpe +0.021)

**Holdout results (3200 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 3200 |
| Bars with an active (non-zero) direction | 187 |
| Total return | -0.71% |
| CAGR | -1.32% |
| Sharpe (annualized) | -1.134 |
| Sortino (annualized) | -0.402 |
| Max drawdown | -1.42% |
| Profit factor | 0.816 |
| Win rate (active bars) | +30.25% |
| Hit rate (direction sign vs realized sign) | +55.08% (n=187, p=0.1647) |
| Random-direction MC baseline | mean final equity 0.998, real result at percentile +26.85% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe -1.001, total return -1.31%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## DJIA
- Symbol: `US30cash-1` (MT5) — 8000 H1 bars
- Round-turn transaction cost used: 0.21 bps
- Yahoo cross-check: 2374 overlapping bars, hourly-return correlation = 0.2841
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 4800 bars (development slice, never touches holdout)
- Selected: window=20, horizon=10, threshold=0.95 (mean fold Sharpe +0.003)

**Holdout results (3200 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 3200 |
| Bars with an active (non-zero) direction | 225 |
| Total return | +0.65% |
| CAGR | +1.21% |
| Sharpe (annualized) | 1.368 |
| Sortino (annualized) | 0.658 |
| Max drawdown | -0.70% |
| Profit factor | 1.237 |
| Win rate (active bars) | +37.67% |
| Hit rate (direction sign vs realized sign) | +45.09% (n=224, p=0.1416) |
| Random-direction MC baseline | mean final equity 0.998, real result at percentile +89.00% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe 1.381, total return +1.30%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## EURUSD
- Symbol: `EURUSD` (MT5) — 8000 H1 bars
- Round-turn transaction cost used: 1.72 bps
- Yahoo cross-check: 7839 overlapping bars, hourly-return correlation = 0.0945
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 4800 bars (development slice, never touches holdout)
- Selected: window=20, horizon=10, threshold=0.95 (mean fold Sharpe -0.012)

**Holdout results (3200 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 3200 |
| Bars with an active (non-zero) direction | 60 |
| Total return | -0.11% |
| CAGR | -0.21% |
| Sharpe (annualized) | -1.548 |
| Sortino (annualized) | -0.379 |
| Max drawdown | -0.12% |
| Profit factor | 0.659 |
| Win rate (active bars) | +32.56% |
| Hit rate (direction sign vs realized sign) | +55.00% (n=60, p=0.4386) |
| Random-direction MC baseline | mean final equity 0.997, real result at percentile +94.65% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe -2.487, total return -0.43%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## XAUUSD
- Symbol: `XAUUSD` (MT5) — 8000 H1 bars
- Round-turn transaction cost used: 0.86 bps
- Yahoo cross-check: 7359 overlapping bars, hourly-return correlation = 0.1264
- Parameter selection: 3-fold walk-forward CV over 8 configs on the first 4800 bars (development slice, never touches holdout)
- Selected: window=10, horizon=10, threshold=0.95 (mean fold Sharpe -0.002)

**Holdout results (3200 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 3200 |
| Bars with an active (non-zero) direction | 132 |
| Total return | +0.87% |
| CAGR | +1.62% |
| Sharpe (annualized) | 1.216 |
| Sortino (annualized) | 0.396 |
| Max drawdown | -0.85% |
| Profit factor | 1.297 |
| Win rate (active bars) | +33.17% |
| Hit rate (direction sign vs realized sign) | +50.00% (n=132, p=1.0000) |
| Random-direction MC baseline | mean final equity 0.996, real result at percentile +88.10% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe 0.406, total return +0.48%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## Summary

| Instrument | Holdout Sharpe | Hit rate (p-value) | Beats random baseline? | Verdict |
|---|---|---|---|---|
| US500 | -1.206 | +53.98% (p=0.2913) | no | No statistically significant edge over chance on this holdout slice. Matches the... |
| US100 | -1.134 | +55.08% (p=0.1647) | no | No statistically significant edge over chance on this holdout slice. Matches the... |
| DJIA | 1.368 | +45.09% (p=0.1416) | no | No statistically significant edge over chance on this holdout slice. Matches the... |
| EURUSD | -1.548 | +55.00% (p=0.4386) | yes | No statistically significant edge over chance on this holdout slice. Matches the... |
| XAUUSD | 1.216 | +50.00% (p=1.0000) | no | No statistically significant edge over chance on this holdout slice. Matches the... |

## Honest caveats — read before trading any of this

- This is one holdout slice per instrument, not multiple independent out-of-sample periods across different market regimes. A single passing result is encouraging, not proof.
- Transaction costs used are current spread snapshots (or fallback assumptions where MT5 reported a stale/zero spread) — they don't model slippage, widened spreads during news/volatility, or commission.
- Position sizing (3x confidence, clipped to [-1,1]) is illustrative, not risk-managed. There is no stop-loss, max-drawdown circuit breaker, or correlation-aware sizing across instruments here.
- No instrument here was tested through a genuinely different regime (e.g. a volatility shock or trend reversal) unless one happened to fall in its holdout window by chance.
- Signals-only mode is what's implemented — nothing in this repository places live orders.
