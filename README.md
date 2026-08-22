# T4.4A — External Cross-Market Matched-Control Aggregator

A lightweight, standalone Python research utility that parses the T44C records emitted by the frozen Pine T4.4 matched-control experiment and produces a reproducible, descriptive cross-market evidence report.

**This is an OFFLINE DIAGNOSTIC research tool.** It does not modify Pine model logic, trigger definitions, matching rules, thresholds, gates, forecasts, analogue libraries, or production trading logic, and it creates no feedback path from its output back into the model.

## Research question

After controlling for tail age and frozen HTF geometry using the prospectively matched T4.4 controls, do actual BAND/DIV tail events show incremental outcome information relative to their controls, and is that relationship consistent across markets?

## T4.4A quick start

```bash
python t44a.py records.txt
python t44a.py ./exports/
python t44a.py dow.txt wti.txt ndx.txt
cat records.txt | python t44a.py -
```

Produces `t44a_report/` containing the cleaned records, audit trail, aggregation summaries, market×cell matrices, human-readable report, and reproducibility manifest.

## T4.4A.1 — longitudinal evidence accumulation

T4.4A.1 preserves successive real-data reports as immutable checkpoints so the evidence chronology cannot be silently rewritten after later results are observed. It also keeps BAND and DIV as first-class descriptive reporting dimensions without selecting, promoting, suppressing, or tuning either source.

After producing a normal T4.4A report, append it to the history:

```bash
python t44a_history.py t44a_report --label REAL-1
python t44a_history.py t44a_report --label REAL-2
```

The default `t44a_history/` store contains:

- `01_checkpoints.csv` — pooled metrics at every frozen checkpoint
- `02_source_trend.csv` — BAND/DIV and side×source evidence through time
- `03_history.md` — compact longitudinal research report
- `04_history_manifest.json` — checkpoint hashes and append-only policy

Checkpoint labels are immutable. Re-running the same label with the same source report is idempotent; attempting to reuse a label for different evidence is rejected. The source report and manifest SHA-256 hashes are retained for provenance.

This phase is deliberately **non-inferential**. A history row is a cumulative descriptive checkpoint, not an independent observation. Do not run p-values, confidence intervals, bootstrap inference, Sharpe ratios, or significance tests on these checkpoint rows.

## Statistical limitation — read before interpreting any output

T44C records contain **aggregate cell means**, not individual matched-pair observations. T4.4A and T4.4A.1 intentionally do **not** compute standard deviation, standard error, t-tests, Wilcoxon tests, bootstrap confidence intervals, p-values, or Sharpe ratios. Doing so would require pair-level observations that T44C does not provide.

T4.4B is reserved for a future immutable pair-level export and legitimate paired inference.

Nothing this tool outputs is a trading instruction. Research verdicts are descriptive labels only and never `VALIDATED`, `PROVEN`, `SIGNIFICANT`, `TRADEABLE`, or a buy/sell directive.

## Architecture

```text
t44a.py                         T4.4A report CLI
t44a_history.py                 T4.4A.1 append-only history CLI
research/t44a/
    parser.py                   extraction + structural parse
    aggregate.py                dedup, validation, weighted aggregation, classification
    report.py                   T4.4A report writer
    cli.py                      T4.4A orchestration
    history.py                  T4.4A.1 immutable checkpoint accumulation
tests/
    test_t44a_parser.py
    test_t44a_aggregate.py
    test_t44a_report.py
    test_t44a_history.py
    fixtures/sample_t44c.txt
```

Dependencies: Python standard library + pandas. No scipy/statsmodels/sklearn inference layer is used.

## Running the tests

```bash
python -m unittest discover -s tests -t .
```

## Research freeze requirements

This phase must not: modify Pine code; modify thresholds; optimize cells; select best parameters; suppress BAND, DIV, negative markets, or inconvenient observations; exclude valid observations because they weaken the result; feed T4.4 evidence into production decisions; or alter matching after seeing outcomes.

The current research lead — possible BAND/DIV population separation — is tracked descriptively only. It is a hypothesis to accumulate evidence for, not a model change.

---

**T4.4A/T4.4A.1 are external descriptive research layers only. The T4.4 Pine experiment and baseline model remain unchanged.**
