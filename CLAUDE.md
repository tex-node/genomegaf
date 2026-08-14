# Project status: closed — no tradable edge found

This project is concluded as of 2026-08-14. Read this before doing any further work here, including if you're a future Claude session picking this back up.

## Bottom line

The GAF pattern-recognition indicator (Gramian Angular Field encoding + historical fingerprint matching + forward-return projection) was built, debugged, and validated against real MT5 market data across multiple timeframes, an enhanced feature set, and a cross-market pooling variant. **No configuration produced a statistically significant, replicable directional edge.** Do not deploy this for live trading. If you're asked to pick this project back up, don't start by re-running more parameter grids on the same premise — see "If you want to continue" below for what would actually be a new test.

## What was actually tested

1. **Baseline pipeline, 5 instruments (US500, US100, DJIA, EUR/USD, XAU/USD) × 3 timeframes (H1, M15, D1)**, real MT5 history, walk-forward parameter selection (train/holdout split, DB frozen during holdout), real transaction costs, binomial hit-rate significance test, random-direction Monte Carlo baseline. Result: no edge on any of 15 instrument×timeframe combinations (11 had enough signals to test at all).
2. **Enhanced feature set** (rank/quantile normalization, regime-conditional matching, recency-decay weighting, return skew — ported in from a separate review session, after fixing a same-bar look-ahead bug that review's own backtest still had). Result on H1: 3 of 5 instruments hit nominal p<0.05, but none survived a Bonferroni correction for the 5 tests in that one batch, and the independent Monte Carlo check only corroborated the one result that was inverted (below-chance accuracy, small n) — the signature of a false positive, not a real result.
3. **Cross-instrument/cross-timeframe pattern pooling** (one shared fingerprint database across all 5 instruments × 4 timeframes — M5/M15/H1/D1 — split at a single global calendar cutoff, tested pooled vs. same-instrument-only control). Result: 4 of 5 instruments showed nothing. The one that looked significant (DJIA, p=0.0002) decomposed cleanly into a drift artifact — DJIA rallied +10% over the holdout window, and the base rate of positive forward returns during that period alone was ~54%, matching the "edge." A trivial always-long strategy would have scored the same or better. This also surfaced two real methodological findings, independent of any specific result: (a) the binomial hit-rate test's 50/50 null is silently wrong whenever the underlying instrument has real drift over the test window — worth fixing (compare against the instrument's own realized base rate, not a flat 50%) before trusting any future hit-rate significance claim from this codebase; (b) pooling ~400K fingerprints into a 45-dimensional space made the 0.90 similarity threshold nearly non-selective (83-89% of bars fired a match, vs 2-3% for single-source search) — a sign of high-dimensional cosine similarity saturating at that density, not genuine rare-pattern recurrence.

Across all three rounds: **31+ independent hypothesis tests, zero replicated positive results.** That's the expected footprint of pure noise at this sample size, not a signal hiding in an untried corner of the parameter space.

Full detail, methodology, and numbers: [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md) (cross-round index) and the per-round reports it links to (`VALIDATION_REPORT_H1.md`, `_M15.md`, `_D1.md`, `_enhanced_H1.md`, `_cross_market.md`).

## What's in this repo

- Working, bug-fixed Python prototype of the full GAF pipeline (`gaf_core.py`, `pattern_db.py`, `projection.py`, `gaf_indicator.py`, `regime.py`) — mechanically correct, extensively tested for implementation bugs (two real ones found and fixed: a fixed-k GAF rescale bug, and a same-bar look-ahead bug in the P&L simulation loop that existed in *every* version of this code, including the external review's, until this project fixed it).
- Real market data connectors: `mt5_feed.py` (read-only MT5 terminal connector — no order-placement code exists anywhere in this repo) and `yahoo_feed.py` (cross-check source).
- `validation.py` / `run_validation.py` — the walk-forward CV + holdout + significance-testing harness used for rounds 1 and 2.
- `multi_source_pattern_db.py` / `run_cross_market_validation.py` — the cross-market pooling harness used for round 3.
- `live_signal.py` — a signals-only live watcher (prints/logs candidate signals from a running MT5 terminal; never places an order). Functional but there's no validated config to point it at.
- `web/dashboard.html` — self-contained browser dashboard for interactively exploring the pipeline on synthetic or uploaded data.
- `demo.py` — synthetic-data smoke test.

## If you want to continue

Don't just widen the existing parameter grids or add another feature — that's the same search that already produced 31 null results. Things that would actually be new information:
1. **Fix the hit-rate test's null hypothesis** to use each instrument's own realized base rate over the test window instead of a flat 50%, and re-check whether any prior "significant" result (especially the cross-market DJIA one) still looks meaningful once drift is properly accounted for. This is a real bug worth fixing regardless of what you do next.
2. **A genuinely different signal**, not a retuning of GAF matching — different feature representation, different asset class, or a different hypothesis about what's predictive.
3. **If you still believe in cross-market pooling specifically**: re-run it with a similarity threshold scaled to the pool size (the 400K-fingerprint pool needs a much higher bar than 0.90 to stay selective — that's a concrete, cheap thing to try before abandoning the idea, distinct from the drift-artifact problem above).

Whatever you do, keep the same discipline this project used throughout: walk-forward splits with the DB frozen during holdout, real transaction costs, one-bar-lagged position application, and an explicit significance test against a proper null — not just an equity curve.
