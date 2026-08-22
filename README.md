# T4.4A — External Cross-Market Matched-Control Aggregator

A lightweight, standalone Python research utility that parses the T44C
records emitted by the frozen Pine T4.4 matched-control experiment and
produces a reproducible, descriptive cross-market evidence report.

**This is an OFFLINE DIAGNOSTIC research tool.** It does not modify Pine
model logic, trigger definitions, matching rules, thresholds, gates,
forecasts, analogue libraries, or production trading logic, and it
creates no feedback path from its output back into the model.

## Research question

After controlling for tail age and frozen HTF geometry using the
prospectively matched T4.4 controls, do actual BAND/DIV tail events show
incremental outcome information relative to their controls, and is that
relationship consistent across markets?

## Quick start

```bash
python t44a.py records.txt          # one file
python t44a.py ./exports/           # a directory of *.txt/*.log/*.csv
python t44a.py dow.txt wti.txt ndx.txt   # multiple files
cat records.txt | python t44a.py -  # stdin
```

Produces `t44a_report/` containing 11 files: cleaned records, a full
parse/validation audit trail, six aggregation-level summaries (cell,
side×source, asset class, market, cohort), two market×cell matrices,
a human-readable markdown report, and a reproducibility manifest. See
`t44a_report/10_report.md` after running.

Options:

```bash
python t44a.py records.txt --out my_report_dir
python t44a.py records.txt --arithmetic-tolerance 0.005
python t44a.py records.txt --sign-epsilon 1e-6
python t44a.py records.txt --quiet   # suppress the console summary
```

## Statistical limitation — read before interpreting any output

T44C records contain **aggregate cell means**, not individual
matched-pair observations. This tool intentionally does **not** compute
standard deviation, standard error, t-tests, Wilcoxon tests, bootstrap
confidence intervals, p-values, or Sharpe ratios anywhere — doing so
would require treating an aggregate mean as if it were a single raw
observation, which it is not. T4.4A is a **cross-market descriptive
consistency analysis** only. A future T4.4B could export pair-level
observations if statistical inference is ever needed.

Nothing this tool outputs is a trading instruction. The "Research
Verdict" values (`ACCUMULATE`, `INSUFFICIENT_CROSS_MARKET_EVIDENCE`,
`MIXED`, `DESCRIPTIVE_POSITIVE`, `DESCRIPTIVE_NEGATIVE`) are research
labels only — never `VALIDATED`, `PROVEN`, `SIGNIFICANT`, or
`TRADEABLE`, and never a buy/sell directive.

## Architecture

```
t44a.py                        thin CLI entry point
research/t44a/
    parser.py                  text -> structured T44Record (extraction + structural parse)
    aggregate.py                dedup, semantic validation, weighted aggregation, classification
    report.py                  writes the 11 t44a_report/ output files
    cli.py                     argument parsing + orchestration
tests/
    test_t44a_parser.py
    test_t44a_aggregate.py
    test_t44a_report.py
    fixtures/sample_t44c.txt   synthetic fixture data -- NOT real research evidence
```

Dependencies: Python standard library + pandas (already present in this
environment). No numpy/scipy/statsmodels/sklearn are used, deliberately
— this phase doesn't need or want inferential statistics.

## Running the tests

```bash
python -m unittest discover -s tests -t .
```

44 tests covering parsing, NA handling, malformed-record rejection, cell
decomposition, weighted-mean math, duplicate/conflict snapshot handling,
DRET/DMFE/DMAE arithmetic validation, positive-market-share, market/class
concentration flags, maturity/breadth labels, evidence classification,
unrelated-text tolerance, zero-pair safety, and end-to-end report
generation.

## Safety / freeze requirements

This phase must not, and does not: modify Pine code, modify thresholds,
optimize cells, select best parameters, suppress negative markets,
exclude valid observations because they weaken the result, feed T4.4
evidence into production decisions, or alter matching after seeing
outcomes. Every market supplied to the aggregator remains in the
report, including markets with zero eligible pairs.

---

**T4.4A is an external descriptive aggregation layer only. The T4.4
Pine experiment and baseline model remain unchanged.**
