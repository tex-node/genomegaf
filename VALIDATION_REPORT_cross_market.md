# Cross-market validation — GenomeGAF

Generated 2026-08-14 14:47 UTC. Pooled sources: ['US500', 'US100', 'DJIA', 'EURUSD', 'XAUUSD'] x ['M5', 'M15', 'H1', 'D1']. Query timeframe: H1. window=10, horizon=10 (bars, native to each source), normalization=rank, threshold=0.9.

Global calendar cutoff: **2026-02-01** (2025-04-16 to 2026-08-14, 60/40 split). Every source is split at this SAME timestamp regardless of instrument or timeframe, not each source's own fraction -- see multi_source_pattern_db.py for why that matters once fingerprints are pooled.

Shared database size after ingestion: **401658** fingerprints across 20 sources.

Each instrument is evaluated on its own H1 holdout bars two ways against the identical frozen database: **pooled** (search everything) vs **control** (search only that instrument's own H1-sourced fingerprints within the same pool) — the control isolates whether pooling adds anything beyond single-source H1 matching.

## US500

**pooled** (2667 active signals of 3159 holdout bars):

| Metric | Value |
|---|---|
| Total return | -1.82% |
| Sharpe (annualized) | -0.829 |
| Max drawdown | -3.61% |
| Profit factor | 0.960 |
| Hit rate | +51.30% (n=2655, p=0.1805) |
| Random-direction MC baseline | real result at percentile +92.20% of 2000 sims |

**control_own_h1_only** (90 active signals of 3159 holdout bars):

| Metric | Value |
|---|---|
| Total return | +0.04% |
| Sharpe (annualized) | 0.206 |
| Max drawdown | -0.22% |
| Profit factor | 1.053 |
| Hit rate | +53.93% (n=89, p=0.4581) |
| Random-direction MC baseline | real result at percentile +76.10% of 2000 sims |

## US100

**pooled** (2635 active signals of 3159 holdout bars):

| Metric | Value |
|---|---|
| Total return | -3.89% |
| Sharpe (annualized) | -1.196 |
| Max drawdown | -6.98% |
| Profit factor | 0.940 |
| Hit rate | +51.35% (n=2625, p=0.1658) |
| Random-direction MC baseline | real result at percentile +40.90% of 2000 sims |

**control_own_h1_only** (71 active signals of 3159 holdout bars):

| Metric | Value |
|---|---|
| Total return | -0.49% |
| Sharpe (annualized) | -1.433 |
| Max drawdown | -0.66% |
| Profit factor | 0.682 |
| Hit rate | +54.41% (n=68, p=0.4669) |
| Random-direction MC baseline | real result at percentile +17.05% of 2000 sims |

## DJIA

**pooled** (2629 active signals of 3160 holdout bars):

| Metric | Value |
|---|---|
| Total return | +2.06% |
| Sharpe (annualized) | 1.002 |
| Max drawdown | -2.53% |
| Profit factor | 1.053 |
| Hit rate | +53.67% (n=2616, p=0.0002) |
| Random-direction MC baseline | real result at percentile +98.20% of 2000 sims |

**control_own_h1_only** (74 active signals of 3160 holdout bars):

| Metric | Value |
|---|---|
| Total return | -0.55% |
| Sharpe (annualized) | -2.253 |
| Max drawdown | -0.55% |
| Profit factor | 0.510 |
| Hit rate | +54.05% (n=74, p=0.4855) |
| Random-direction MC baseline | real result at percentile +9.90% of 2000 sims |

## EURUSD

**pooled** (2816 active signals of 3338 holdout bars):

| Metric | Value |
|---|---|
| Total return | +1.66% |
| Sharpe (annualized) | 1.761 |
| Max drawdown | -0.73% |
| Profit factor | 1.098 |
| Hit rate | +49.52% (n=2809, p=0.6104) |
| Random-direction MC baseline | real result at percentile +97.75% of 2000 sims |

**control_own_h1_only** (69 active signals of 3338 holdout bars):

| Metric | Value |
|---|---|
| Total return | +0.09% |
| Sharpe (annualized) | 1.524 |
| Max drawdown | -0.05% |
| Profit factor | 1.589 |
| Hit rate | +52.17% (n=69, p=0.7180) |
| Random-direction MC baseline | real result at percentile +89.80% of 2000 sims |

## XAUUSD

**pooled** (2724 active signals of 3164 holdout bars):

| Metric | Value |
|---|---|
| Total return | -5.32% |
| Sharpe (annualized) | -1.110 |
| Max drawdown | -8.77% |
| Profit factor | 0.942 |
| Hit rate | +50.41% (n=2714, p=0.6728) |
| Random-direction MC baseline | real result at percentile +65.60% of 2000 sims |

**control_own_h1_only** (61 active signals of 3164 holdout bars):

| Metric | Value |
|---|---|
| Total return | -0.94% |
| Sharpe (annualized) | -2.706 |
| Max drawdown | -1.27% |
| Profit factor | 0.467 |
| Hit rate | +36.07% (n=61, p=0.0295) |
| Random-direction MC baseline | real result at percentile +4.05% of 2000 sims |

## Summary

| Instrument | Pooled Sharpe (p) | Control Sharpe (p) | Pooled n active | Control n active |
|---|---|---|---|---|
| US500 | -0.829 (p=0.1805) | 0.206 (p=0.4581) | 2667 | 90 |
| US100 | -1.196 (p=0.1658) | -1.433 (p=0.4669) | 2635 | 71 |
| DJIA | 1.002 (p=0.0002) | -2.253 (p=0.4855) | 2629 | 74 |
| EURUSD | 1.761 (p=0.6104) | 1.524 (p=0.7180) | 2816 | 69 |
| XAUUSD | -1.110 (p=0.6728) | -2.706 (p=0.0295) | 2724 | 61 |
