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

## Bottom line

Across 3 timeframes × 5 instruments, with real transaction costs, proper
walk-forward parameter selection, and significance testing — nothing here
clears the bar for live capital. This is a clean negative result, not a
partial one: it's not "close, needs tuning," it's "no directional edge
detected under any of the timeframes or parameter combinations tried."

See each timeframe report's own "Honest caveats" section for what this
methodology still doesn't cover (single holdout period per instrument,
no regime diversity, no slippage/commission modeling, illustrative
position sizing only).
