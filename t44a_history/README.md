# t44a_history/ — T4.4A.1 Evidence Ledger

This directory is **version-controlled, append-only research evidence** —
not regenerable application output. Unlike `t44a_report/` (gitignored,
rebuildable at any time from the raw exports), the checkpoints recorded
here are the historical record of what the T4.4 matched-control evidence
looked like at each `REAL-n` capture. That record must persist exactly as
captured, even if a later checkpoint reverses the relationships seen here
entirely — a reversal is itself scientifically meaningful evidence, and it
only stays legible if the path to it hasn't been overwritten.

## Rules

- **Never edit, delete, or re-record a committed `REAL-n` checkpoint with
  different evidence.** `append_checkpoint()` enforces this at the code
  level — reusing a label with a different source-report/manifest hash
  raises `ValueError` instead of rewriting the row. This file states the
  same rule at the human level. Git is the second, independent audit
  trail: if a git diff ever shows a change to an existing checkpoint row
  that the code-level hash check didn't catch, treat that as a
  research-integrity incident, not something to quietly patch over.
- **A new observation period is always a new checkpoint label**
  (`REAL-2`, `REAL-3`, ...), never a rewrite of an existing one.
- **Commit checkpoint creation separately from code changes.** Fixes to
  `research/t44a/` land in their own commits; each accepted `REAL-n`
  capture lands in its own `evidence: record T4.4 REAL-n` commit. This
  keeps the research chronology auditable independently of tooling
  history.
- **This directory is non-inferential.** Nothing here should ever have
  p-values, confidence intervals, bootstrap inference, or Sharpe ratios
  computed on it — see `03_history.md`'s own guardrails section and the
  top-level `README.md`'s statistical limitation notes.

## Files

- `01_checkpoints.csv` — one row per checkpoint, pooled metrics.
- `02_source_trend.csv` — BAND/DIV and side×source rows per checkpoint.
- `03_history.md` — human-readable longitudinal report. Regenerated in
  full on every `append_checkpoint()` call, but the underlying checkpoint
  rows it's built from are themselves immutable once committed.
- `04_history_manifest.json` — checkpoint labels plus source report/
  manifest SHA-256 hashes, for provenance and tamper detection.

## Provenance

Each checkpoint's `source_report_sha256` / `source_manifest_sha256` in
`04_history_manifest.json` ties it back to the exact `t44a_report/`
output — and therefore the exact raw T44C exports — that produced it. Raw
exports are preserved alongside this history in `exports/` for as long as
they stay small and contain nothing sensitive; if that changes, switch to
archived storage with hashes recorded here instead.
