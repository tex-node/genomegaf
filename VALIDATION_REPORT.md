# Validation summary — GenomeGAF

Full methodology and per-instrument detail live in the timeframe-specific
reports this indexes: [`VALIDATION_REPORT_H1.md`](VALIDATION_REPORT_H1.md),
[`VALIDATION_REPORT_M15.md`](VALIDATION_REPORT_M15.md),
[`VALIDATION_REPORT_D1.md`](VALIDATION_REPORT_D1.md). All three run the same
walk-forward CV / holdout / cost-adjusted / significance-tested pipeline
(see `run_validation.py`) against real MT5 history for US500, US100, DJIA,
EUR/USD, and XAU/USD.

## Combined result across all three timeframes

| Instrument | H1 Sharpe (p) | M15 Sharpe (p) | D1 Sharpe (p) |
|---|---|---|---|
| US500  | -1.21 (p=0.29) | -3.42 (p=0.32) | -0.99 (p=0.56, n=12, inconclusive) |
| US100  | -1.13 (p=0.16) | -1.03 (p=0.30) | -0.52 (p=0.74, n=9, inconclusive) |
| DJIA   | +1.37 (p=0.14) | -0.64 (p=0.007)| +0.75 (p=1.00, n=18, inconclusive) |
| EUR/USD| -1.55 (p=0.44) | -4.33 (p=0.76) | -0.25 (p=0.50) |
| XAU/USD| +1.22 (p=1.00) | -2.46 (p=0.82) | +0.93 (p=0.56, n=3, inconclusive) |

**None of these show a statistically robust edge.** Positive Sharpe ratios
show up in a few cells (DJIA/H1, XAU-USD/H1 and D1) but every one of them
has a directional hit-rate p-value nowhere near significant — the Sharpe
is coming from a handful of lucky-sized wins, not from calling direction
correctly more often than chance.

**The one p<0.05 cell (DJIA/M15, p=0.007) is very likely a false positive,
not a real inverted edge.** Across the three timeframes, 11 instrument-tests
had enough holdout signals to test at all (D1 mostly didn't — see below).
Running 11 hypothesis tests at α=0.05 gives roughly a 43% chance of at
least one p<0.05 purely from noise, and 0.007 doesn't clear a
Bonferroni-corrected threshold (0.05/11 ≈ 0.0045, close but no). Also note
its hit rate is 41.6% — *below* chance, not above — so even taking it at
face value it would mean this specific config gets direction wrong more
than right, not a tradeable "flip the sign" edge (that kind of post-hoc
sign-flip is itself a classic overfitting trap: the sign was picked by
looking at the same holdout data being used to justify it).

**D1 was mostly inconclusive, not clean — read that as "needs more data,"
not "passes."** With ~1400-2000 daily bars and a 95% similarity threshold,
most instruments' holdout slices had fewer than 20 active signals — too
few for the significance tests to say anything. Only EUR/USD had enough
(n=109) to test, and it also showed no edge. Widening the DB history or
loosening `similarity_threshold` would be needed before D1 conclusions
mean anything either way.

## Round 2: rank normalization + regime filtering + recency decay (H1 only)

A separate Claude session proposed four additions on top of the original
prototype: rank/quantile normalization as an alternative to ATR division,
regime-conditional matching (9-state trend×volatility buckets), recency-
decay weighting, and return-distribution skew. The mechanisms were sound
but built on a fork that predates this repo's look-ahead-bug fix and had
no real-market testing — see the "v2 review" note in `README.md`. The
good parts (`gaf_core.rank_normalize_series`, `regime.py`,
`PatternDB`'s regime filter, `projection.py`'s recency/skew) were ported
into this validated codebase (keeping the `learn`-flag true walk-forward
freeze instead of the fork's leakier burn-in) and tested the same way as
everything else here: `run_validation.py --feature-set enhanced`.

First attempt (same 0.90/0.95 thresholds as baseline) mostly failed to
fire at all — splitting the pattern DB across 9 regimes cuts the
candidate pool ~9x, so 3 of 5 instruments got **zero** active signals in
3200 holdout bars. Re-run with lower thresholds (0.75-0.90) fixed that
and produced the most interesting numbers in this project so far:

| Instrument | Hit rate | p-value | Direction |
|---|---|---|---|
| US500 | 61.74% (n=115) | 0.0118 | correct more than chance |
| EUR/USD | 31.58% (n=38) | 0.0231 | **inverted** — wrong more than chance |
| XAU/USD | 55.42% (n=424) | 0.0255 | correct more than chance |

Three of five nominally significant (p<0.05) is a step up from every
prior batch in this project, where none were. **But none of the three
survive a Bonferroni correction for just this one batch of 5 tests**
(threshold would need p<0.01 — closest is 0.0118). The random-direction
Monte Carlo baseline — a second, independent significance check — only
corroborates EUR/USD (97th percentile), and EUR/USD is the inverted,
small-n result, which is a shape more typical of an overfit false
positive than a real edge. US500 and XAU/USD sit at the 82nd and 77th
percentile of their null distributions respectively — encouraging, not
conclusive, and below the 90th-percentile bar used everywhere else in
this project. Full detail in `VALIDATION_REPORT_enhanced_H1.md`.

**Read this as: more interesting than anything before, still not enough
to trade.** The honest next step, if this is worth pursuing further, is
a genuinely independent second holdout period (not just a stricter
correction on the same one) — that's the actual test of whether this
replicates or was noise that happened to clear a threshold on one slice.

## Bottom line

Across 3 timeframes × 5 instruments with the original feature set, and
H1 with an enhanced feature set (rank normalization + regime filtering),
with real transaction costs, proper walk-forward parameter selection,
and significance testing — nothing here clears the bar for live capital
yet. The enhanced feature set produced the first batch of nominally
significant results in this project, which is genuinely worth further
investigation, but they don't survive even a simple correction for
having run 5 tests, and a second statistical test (the random-direction
baseline) only agrees on the one result that looks most like a false
positive (small n, wrong-direction). Encouraging enough to warrant one
more independent check before either pursuing or discarding it — not
enough, on its own, to trade.

See each timeframe report's own "Honest caveats" section for what this
methodology still doesn't cover (single holdout period per instrument,
no regime diversity, no slippage/commission modeling, illustrative
position sizing only).
