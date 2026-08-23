# T4.4A.1 Longitudinal Evidence Accumulation Report

This report preserves the chronology of successive T4.4A descriptive checkpoints. It is append-only research evidence: no thresholds are tuned, no market is excluded, and no result feeds back into the production model.

## Checkpoint History

| CHECKPOINT | PAIRS | MARKETS | DRET | ΔHIT | DMFE | DMAE | POS MKT % | MEDIAN MKT DRET | MATURITY | BREADTH | CLASSIFICATION | VERDICT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|
| REAL-1 | 12 | 6 | -0.2071 | 0.00 | -0.1321 | -0.8677 | 50.0% | 0.0542 | DEVELOPING | BROAD | EARLY_MIXED | MIXED |

## BAND vs DIV Through Time

The source split is shown because the current research question specifically requires tracking whether BAND and DIV behave as different event populations. This is descriptive monitoring only, not source selection.

| CHECKPOINT | GROUP | PAIRS | MARKETS | DRET | ΔHIT | POS MKT % | MATURITY | BREADTH | CLASSIFICATION |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| REAL-1 | B_BAND | 3 | 2 | 0.4481 | 0.00 | 50.0% | EMBRYONIC | LIMITED_BREADTH | INSUFFICIENT |
| REAL-1 | B_DIV | 3 | 2 | 0.1784 | 0.00 | 50.0% | EMBRYONIC | LIMITED_BREADTH | INSUFFICIENT |
| REAL-1 | S_BAND | 4 | 2 | -1.3225 | -25.00 | 0.0% | EMBRYONIC | LIMITED_BREADTH | INSUFFICIENT |
| REAL-1 | S_DIV | 2 | 2 | 0.4624 | 50.00 | 100.0% | EMBRYONIC | LIMITED_BREADTH | INSUFFICIENT |
| REAL-1 | BAND | 7 | 4 | -0.5637 | -14.29 | 25.0% | EARLY | MULTI_MARKET | EARLY_CONSISTENT_NEG |
| REAL-1 | DIV | 5 | 3 | 0.2920 | 20.00 | 66.7% | EARLY | MULTI_MARKET | EARLY_CONSISTENT_POS |

## Interpretation Guardrails

- Each row is a frozen descriptive checkpoint, not an independent statistical observation.
- T44C still contains aggregate matched-control cell means, not pair-level data.
- Do not compute p-values, confidence intervals, Sharpe ratios, or bootstrap inference from this history.
- Do not remove a market, source, side, or cell because it weakens the result.
- Do not promote BAND, DIV, or any other subgroup into model logic from this report.
- T4.4B remains the appropriate phase for pair-level export and legitimate paired inference.

## Current Research Status

Latest checkpoint **REAL-1**: 12 matched pairs across 6 markets; pooled DRET -0.2071; classification **EARLY_MIXED**; verdict **MIXED**.
