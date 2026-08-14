# Validation report — GenomeGAF (H1, enhanced feature set)

Generated 2026-08-14 06:33 UTC. Timeframe: H1. Feature set: enhanced ({'normalization': 'rank', 'rank_lookback': 252, 'use_regime_filter': True, 'trend_lookback': 50, 'vol_lookback': 100, 'recency_halflife': 500}). Bar budget: 8000. Development/holdout split: 60/40. Walk-forward CV folds: 3. Monte Carlo sims: 2000.

**Methodology:** for each instrument, the first 60% of history is a development slice used only to pick pipeline parameters via walk-forward cross-validation (pattern DB trained on progressively larger prefixes, tested on the next held-out chunk, DB frozen during each test chunk). The chosen parameters are then evaluated exactly once on the final holdout slice, which neither the parameter search nor the pattern DB has ever seen. All P&L figures include a real, broker-quoted round-turn transaction cost and lag every position decision by one bar (no same-bar look-ahead). Statistical significance is assessed two ways: a binomial test on directional hit rate, and a Monte Carlo comparison against a random-direction baseline with identical trade timing and sizing.

## US500
- Symbol: `US500cash-1` (MT5) — 8000 H1 bars (2025-04-04 to 2026-08-14)
- Round-turn transaction cost used: 0.75 bps
- Yahoo cross-check: 2373 overlapping bars, hourly-return correlation = 0.2750
- Feature set: **enhanced** ({'normalization': 'rank', 'rank_lookback': 252, 'use_regime_filter': True, 'trend_lookback': 50, 'vol_lookback': 100, 'recency_halflife': 500})
- Parameter selection: 3-fold walk-forward CV over 16 configs on the first 4800 bars (development slice, never touches holdout)
- Selected: window=10, horizon=10, threshold=0.85 (mean fold Sharpe +0.007)

**Holdout results (3200 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 3200 |
| Bars with an active (non-zero) direction | 116 |
| Total return | +0.05% |
| CAGR | +0.08% |
| Sharpe (annualized) | 0.150 |
| Sortino (annualized) | 0.045 |
| Max drawdown | -0.39% |
| Profit factor | 1.033 |
| Win rate (active bars) | +32.42% |
| Hit rate (direction sign vs realized sign) | +61.74% (n=115, p=0.0118) |
| Random-direction MC baseline | mean final equity 0.997, real result at percentile +81.85% of 2000 sims |

**Read:** Hit rate is statistically above chance, but the random-direction baseline (same timing/sizing) performs comparably — suggests trade *timing* may carry some information but directional calls don't clearly add value beyond it. Investigate before trusting this.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe 0.153, total return +0.14%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## US100
- Symbol: `US100cash-1` (MT5) — 8000 H1 bars (2025-04-04 to 2026-08-14)
- Round-turn transaction cost used: 0.31 bps
- Yahoo cross-check: 2372 overlapping bars, hourly-return correlation = 0.2889
- Feature set: **enhanced** ({'normalization': 'rank', 'rank_lookback': 252, 'use_regime_filter': True, 'trend_lookback': 50, 'vol_lookback': 100, 'recency_halflife': 500})
- Parameter selection: 3-fold walk-forward CV over 16 configs on the first 4800 bars (development slice, never touches holdout)
- Selected: window=20, horizon=5, threshold=0.75 (mean fold Sharpe +0.036)

**Holdout results (3200 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 3200 |
| Bars with an active (non-zero) direction | 671 |
| Total return | +0.72% |
| CAGR | +1.33% |
| Sharpe (annualized) | 0.362 |
| Sortino (annualized) | 0.253 |
| Max drawdown | -2.47% |
| Profit factor | 1.037 |
| Win rate (active bars) | +40.31% |
| Hit rate (direction sign vs realized sign) | +51.35% (n=666, p=0.4855) |
| Random-direction MC baseline | mean final equity 0.989, real result at percentile +74.90% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe 0.650, total return +2.96%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## DJIA
- Symbol: `US30cash-1` (MT5) — 8000 H1 bars (2025-04-04 to 2026-08-14)
- Round-turn transaction cost used: 0.21 bps
- Yahoo cross-check: 2371 overlapping bars, hourly-return correlation = 0.2850
- Feature set: **enhanced** ({'normalization': 'rank', 'rank_lookback': 252, 'use_regime_filter': True, 'trend_lookback': 50, 'vol_lookback': 100, 'recency_halflife': 500})
- Parameter selection: 3-fold walk-forward CV over 16 configs on the first 4800 bars (development slice, never touches holdout)
- Selected: window=10, horizon=5, threshold=0.85 (mean fold Sharpe +0.036)

**Holdout results (3200 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 3200 |
| Bars with an active (non-zero) direction | 84 |
| Total return | -0.43% |
| CAGR | -0.79% |
| Sharpe (annualized) | -0.863 |
| Sortino (annualized) | -0.280 |
| Max drawdown | -0.49% |
| Profit factor | 0.767 |
| Win rate (active bars) | +27.34% |
| Hit rate (direction sign vs realized sign) | +45.24% (n=84, p=0.3827) |
| Random-direction MC baseline | mean final equity 0.999, real result at percentile +31.55% of 2000 sims |

**Read:** No statistically significant edge over chance on this holdout slice. Matches the project's own prior finding on synthetic data. Do not trade this configuration live as-is.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe -0.927, total return -0.83%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## EURUSD
- Symbol: `EURUSD` (MT5) — 8000 H1 bars (2025-05-06 to 2026-08-14)
- Round-turn transaction cost used: 0.17 bps
- Yahoo cross-check: 7839 overlapping bars, hourly-return correlation = 0.0947
- Feature set: **enhanced** ({'normalization': 'rank', 'rank_lookback': 252, 'use_regime_filter': True, 'trend_lookback': 50, 'vol_lookback': 100, 'recency_halflife': 500})
- Parameter selection: 3-fold walk-forward CV over 16 configs on the first 4800 bars (development slice, never touches holdout)
- Selected: window=20, horizon=10, threshold=0.8 (mean fold Sharpe +0.025)

**Holdout results (3200 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 3200 |
| Bars with an active (non-zero) direction | 39 |
| Total return | +0.12% |
| CAGR | +0.25% |
| Sharpe (annualized) | 2.288 |
| Sortino (annualized) | 0.497 |
| Max drawdown | -0.04% |
| Profit factor | 2.230 |
| Win rate (active bars) | +47.46% |
| Hit rate (direction sign vs realized sign) | +31.58% (n=38, p=0.0231) |
| Random-direction MC baseline | mean final equity 1.000, real result at percentile +97.35% of 2000 sims |

**Read:** Beat the random-direction baseline, but the hit-rate test isn't statistically significant (p >= 0.05) — with this few signals that's likely lower average transaction-cost drag from trading less, not real directional skill. Don't read the baseline percentile alone as an edge.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe 0.016, total return +0.00%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## XAUUSD
- Symbol: `XAUUSD` (MT5) — 8000 H1 bars (2025-04-22 to 2026-08-14)
- Round-turn transaction cost used: 0.78 bps
- Yahoo cross-check: 7358 overlapping bars, hourly-return correlation = 0.1260
- Feature set: **enhanced** ({'normalization': 'rank', 'rank_lookback': 252, 'use_regime_filter': True, 'trend_lookback': 50, 'vol_lookback': 100, 'recency_halflife': 500})
- Parameter selection: 3-fold walk-forward CV over 16 configs on the first 4800 bars (development slice, never touches holdout)
- Selected: window=10, horizon=5, threshold=0.75 (mean fold Sharpe +0.013)

**Holdout results (3200 bars the DB never trained on, walk-forward, cost-adjusted):**

| Metric | Value |
|---|---|
| Bars with a live signal | 3200 |
| Bars with an active (non-zero) direction | 425 |
| Total return | +0.42% |
| CAGR | +0.78% |
| Sharpe (annualized) | 0.245 |
| Sortino (annualized) | 0.134 |
| Max drawdown | -2.09% |
| Profit factor | 1.033 |
| Win rate (active bars) | +34.35% |
| Hit rate (direction sign vs realized sign) | +55.42% (n=424, p=0.0255) |
| Random-direction MC baseline | mean final equity 0.987, real result at percentile +76.75% of 2000 sims |

**Read:** Hit rate is statistically above chance, but the random-direction baseline (same timing/sizing) performs comparably — suggests trade *timing* may carry some information but directional calls don't clearly add value beyond it. Investigate before trusting this.

**For comparison — same config, online mode (continuously re-trained, no train/test split, like the original prototype's backtest): Sharpe -0.414, total return -1.65%.** A materially better online number than the holdout number above is itself a warning sign of overfitting to in-sample structure.

## Summary

| Instrument | Holdout Sharpe | Hit rate (p-value) | Beats random baseline? | Verdict |
|---|---|---|---|---|
| US500 | 0.150 | +61.74% (p=0.0118) | no | Hit rate is statistically above chance, but the random-direction baseline (same ... |
| US100 | 0.362 | +51.35% (p=0.4855) | no | No statistically significant edge over chance on this holdout slice. Matches the... |
| DJIA | -0.863 | +45.24% (p=0.3827) | no | No statistically significant edge over chance on this holdout slice. Matches the... |
| EURUSD | 2.288 | +31.58% (p=0.0231) | yes | Beat the random-direction baseline, but the hit-rate test isn't statistically si... |
| XAUUSD | 0.245 | +55.42% (p=0.0255) | no | Hit rate is statistically above chance, but the random-direction baseline (same ... |

## Honest caveats — read before trading any of this

- This is one holdout slice per instrument, not multiple independent out-of-sample periods across different market regimes. A single passing result is encouraging, not proof.
- Transaction costs used are current spread snapshots (or fallback assumptions where MT5 reported a stale/zero spread) — they don't model slippage, widened spreads during news/volatility, or commission.
- Position sizing (3x confidence, clipped to [-1,1]) is illustrative, not risk-managed. There is no stop-loss, max-drawdown circuit breaker, or correlation-aware sizing across instruments here.
- No instrument here was tested through a genuinely different regime (e.g. a volatility shock or trend reversal) unless one happened to fall in its holdout window by chance.
- Signals-only mode is what's implemented — nothing in this repository places live orders.
