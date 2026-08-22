"""
report.py
Writes the 11 output files (Section 14) into t44a_report/, including the
human-readable markdown report (Section 15), the reproducibility
manifest (Section 21), and the optional compact console summary
(Section 16).

Nothing here computes or displays anything resembling a trading
instruction (VALIDATED / PROVEN / SIGNIFICANT / TRADEABLE / a buy-sell
directive). The "Research Verdict" is a deterministic descriptive label
derived only from the pooled cohort-level classification -- see
`research_verdict()` below for the exact, auditable mapping.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .aggregate import (
    ARITH_TOLERANCE_DEFAULT, SIGN_EPSILON_DEFAULT,
    cell_summary, side_source_summary, source_summary, side_summary,
    asset_class_summary, market_summary, overall_summary,
    market_cell_matrices, eligible_dataframe,
)

OUTPUT_DIR_NAME = "t44a_report"
SCHEMA_VERSION = "1.0"

# Research-only verdict labels. Never a trading instruction. See the
# mapping comment in research_verdict() for exactly how each is derived.
VERDICT_LABELS = {
    "INSUFFICIENT": "INSUFFICIENT_CROSS_MARKET_EVIDENCE",
    "EARLY_MIXED": "MIXED",
    "EARLY_CONSISTENT_POS": "ACCUMULATE",
    "EARLY_CONSISTENT_NEG": "ACCUMULATE",
    "CROSS_MARKET_POS": "DESCRIPTIVE_POSITIVE",
    "CROSS_MARKET_NEG": "DESCRIPTIVE_NEGATIVE",
}


def research_verdict(pooled_classification: str) -> str:
    """Deterministic map from the pooled cohort-level CLASSIFICATION
    (Section 13) to one of the five verdict labels Section 15 names.
    'ACCUMULATE' here means accumulate more matched-pair evidence before
    a direction can be described with cross-market breadth -- it is not
    a portfolio instruction, and this tool never gates or feeds the
    production model regardless of what it outputs."""
    return VERDICT_LABELS.get(pooled_classification, "MIXED")


# ------------------------------------------------------------ 01 / 02

AUDIT_COLUMNS = [
    "record_index", "source_file", "sym", "asset_class", "cohort", "cell", "pair",
    "parse_ok", "valid", "retained", "eligible", "is_duplicate_dropped", "is_snapshot_conflict",
    "ret_delta_ok", "mfe_delta_ok", "mae_delta_ok", "parse_errors", "warnings", "raw_text",
]


def build_audit_dataframe(records: list) -> pd.DataFrame:
    rows = []
    for r in records:
        rows.append({
            "record_index": r.record_index,
            "source_file": r.source_file,
            "sym": r.sym, "asset_class": r.asset_class, "cohort": r.cohort, "cell": r.cell,
            "pair": r.pair,
            "parse_ok": r.parse_ok,
            "valid": r.valid,
            "retained": r.retained,
            "eligible": r.eligible,
            "is_duplicate_dropped": r.is_duplicate_dropped,
            "is_snapshot_conflict": r.is_snapshot_conflict,
            "ret_delta_ok": r.ret_delta_ok,
            "mfe_delta_ok": r.mfe_delta_ok,
            "mae_delta_ok": r.mae_delta_ok,
            "parse_errors": "; ".join(r.parse_errors) if r.parse_errors else "",
            "warnings": "; ".join(r.warnings) if r.warnings else "",
            "raw_text": r.raw_text,
        })
    # Explicit columns even when rows is empty (zero input records must
    # still produce a well-formed, if empty, audit table -- not crash).
    return pd.DataFrame(rows, columns=AUDIT_COLUMNS)


# --------------------------------------------------------------- write

def write_outputs(records: list, out_dir: Path, input_paths: list, file_hashes: dict,
                   arithmetic_tolerance: float = ARITH_TOLERANCE_DEFAULT,
                   sign_epsilon: float = SIGN_EPSILON_DEFAULT) -> dict:
    """Runs the full aggregation and writes all 11 files. Returns a dict
    of summary figures reused by the console printer (Section 16)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = eligible_dataframe(records)

    # 01
    df.to_csv(out_dir / "01_records.csv", index=False)

    # 02
    audit_df = build_audit_dataframe(records)
    audit_df.to_csv(out_dir / "02_audit.csv", index=False)

    # 03-07
    cells = cell_summary(df)
    side_source = side_source_summary(df)
    sources = source_summary(df)
    sides = side_summary(df)
    classes = asset_class_summary(df)
    markets = market_summary(df)
    overall = overall_summary(df)

    cells.to_csv(out_dir / "03_cell_summary.csv", index=False)
    side_source.to_csv(out_dir / "04_side_source_summary.csv", index=False)
    classes.to_csv(out_dir / "05_asset_class_summary.csv", index=False)
    markets.to_csv(out_dir / "06_market_summary.csv", index=False)
    overall.to_csv(out_dir / "07_overall_summary.csv", index=False)

    # 08-09
    dret_matrix, pair_matrix = market_cell_matrices(df)
    dret_matrix.to_csv(out_dir / "08_market_cell_matrix.csv", index=False)
    pair_matrix.to_csv(out_dir / "09_pair_count_matrix.csv", index=False)

    # integrity counters
    records_discovered = len(records)
    records_retained = int(audit_df["eligible"].sum())
    records_invalid = int((~audit_df["valid"]).sum())
    snapshot_duplicates = int(audit_df["is_duplicate_dropped"].sum())
    snapshot_conflicts = int(audit_df["is_snapshot_conflict"].sum())
    cohorts = sorted(df["cohort"].dropna().unique().tolist())
    markets_list = sorted(df["sym"].dropna().unique().tolist())
    classes_list = sorted(df["asset_class"].dropna().unique().tolist())
    pair_total = int(df["pair"].sum()) if not df.empty else 0

    integrity = dict(
        records_discovered=records_discovered, records_retained=records_retained,
        records_invalid=records_invalid, snapshot_duplicates=snapshot_duplicates,
        snapshot_conflicts=snapshot_conflicts, cohorts=cohorts, markets=markets_list,
        asset_classes=classes_list, pair_total=pair_total,
    )

    pooled = overall.iloc[0].to_dict() if len(overall) else None
    verdict = research_verdict(pooled["CLASSIFICATION"]) if pooled else "INSUFFICIENT_CROSS_MARKET_EVIDENCE"

    # 10
    report_text = build_markdown_report(
        df, cells, side_source, sources, sides, classes, markets, overall, integrity, verdict,
        arithmetic_tolerance, sign_epsilon,
    )
    (out_dir / "10_report.md").write_text(report_text, encoding="utf-8")

    # 11
    manifest = build_manifest(input_paths, file_hashes, integrity, arithmetic_tolerance, sign_epsilon)
    (out_dir / "11_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return dict(integrity=integrity, pooled=pooled, verdict=verdict, cells=cells)


# ------------------------------------------------------------- manifest

def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).resolve().parent, timeout=5)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def build_manifest(input_paths, file_hashes, integrity, arithmetic_tolerance, sign_epsilon) -> dict:
    from . import __version__
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_version": __version__,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_files": list(input_paths),
        "input_sha256": file_hashes,
        "records_discovered": integrity["records_discovered"],
        "records_retained": integrity["records_retained"],
        "records_invalid": integrity["records_invalid"],
        "snapshot_duplicates": integrity["snapshot_duplicates"],
        "snapshot_conflicts": integrity["snapshot_conflicts"],
        "cohorts": integrity["cohorts"],
        "markets": integrity["markets"],
        "asset_classes": integrity["asset_classes"],
        "pair_total": integrity["pair_total"],
        "configuration": {
            "arithmetic_tolerance": arithmetic_tolerance,
            "sign_epsilon": sign_epsilon,
        },
        "git_commit": _git_commit(),
    }


# --------------------------------------------------------------- format

def _f(x, nd=4):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "NA"
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def _pct(x, nd=1):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "NA"
    return f"{x * 100:.{nd}f}%"


# ------------------------------------------------------------- markdown

def build_markdown_report(df, cells, side_source, sources, sides, classes, markets, overall,
                           integrity, verdict, arithmetic_tolerance, sign_epsilon) -> str:
    lines = []
    a = lines.append

    a("# T4.4A Cross-Market Matched-Control Evidence Report\n")

    a("## Research Question\n")
    a("Does the T4 tail trigger provide incremental information relative to a "
      "prospectively selected prior-resolved matched control?\n")

    a("## Method\n")
    a("- Matching happened inside Pine, not here: same market, same side, same tail-age "
      "bucket, nearest frozen HTF geometry.")
    a("- The control was already resolved *before* the event was accepted -- no "
      "look-ahead in the control selection.")
    a("- Matching is without replacement.")
    a("- T4.4A receives only the resulting aggregate T44C snapshots emitted by that "
      "process. It performs no rematching, no re-selection, and no access to raw Pine "
      "state.\n")

    a("## Integrity\n")
    a(f"- Records discovered: **{integrity['records_discovered']}**")
    a(f"- Records retained (deduplicated + valid): **{integrity['records_retained']}**")
    a(f"- Records invalid (excluded from aggregation): **{integrity['records_invalid']}**")
    a(f"- Snapshot duplicates dropped: **{integrity['snapshot_duplicates']}**")
    a(f"- Snapshot conflicts (equal PAIR, differing metrics): **{integrity['snapshot_conflicts']}**")
    a(f"- Markets: **{len(integrity['markets'])}** ({', '.join(integrity['markets']) or 'none'})")
    a(f"- Asset classes: **{len(integrity['asset_classes'])}** ({', '.join(integrity['asset_classes']) or 'none'})")
    a(f"- Cohorts: **{', '.join(integrity['cohorts']) or 'none'}**")
    a(f"- Pair total: **{integrity['pair_total']}**\n")

    a("## Overall Result\n")
    if len(overall):
        o = overall.iloc[0].to_dict()
        a("| Metric | Value |\n|---|---|")
        a(f"| Event return | {_f(o['PAIR_WEIGHTED_ERET'])} |")
        a(f"| Control return | {_f(o['PAIR_WEIGHTED_CRET'])} |")
        a(f"| Delta return | {_f(o['PAIR_WEIGHTED_DRET'])} |")
        a(f"| Event hit | {_f(o['PAIR_WEIGHTED_EHIT'], 2)} |")
        a(f"| Control hit | {_f(o['PAIR_WEIGHTED_CHIT'], 2)} |")
        a(f"| Delta hit | {_f(o['PAIR_WEIGHTED_DELTA_HIT'], 2)} |")
        a(f"| Event MFE | {_f(o['PAIR_WEIGHTED_EMFE'])} |")
        a(f"| Control MFE | {_f(o['PAIR_WEIGHTED_CMFE'])} |")
        a(f"| Delta MFE | {_f(o['PAIR_WEIGHTED_DMFE'])} |")
        a(f"| Event MAE | {_f(o['PAIR_WEIGHTED_EMAE'])} |")
        a(f"| Control MAE | {_f(o['PAIR_WEIGHTED_CMAE'])} |")
        a(f"| Delta MAE (raw; see interpretation note below) | {_f(o['PAIR_WEIGHTED_DMAE'])} |")
        a("")
        a(f"- Positive-market share (DRET): {_pct(o['DRET_POS_MARKET_SHARE'])} "
          f"({o['POS_DRET_MARKETS']} of {o['N_MARKETS']} markets)")
        a(f"- Median market DRET: {_f(o['MEDIAN_MARKET_DRET'])}")
        a(f"- Largest single-market pair share: {_pct(o['PAIR_SHARE_MAX_MARKET'])}"
          f"{' (MARKET_CONCENTRATED)' if o['MARKET_CONCENTRATED'] else ''}")
        a(f"- Largest single-class pair share: {_pct(o['PAIR_SHARE_MAX_CLASS'])}"
          f"{' (CLASS_CONCENTRATED)' if o['CLASS_CONCENTRATED'] else ''}")
        a(f"- Maturity: **{o['MATURITY']}**  |  Breadth: **{o['BREADTH']}**")
        a(f"- Descriptive classification: **{o['CLASSIFICATION']}**\n")
    else:
        a("No eligible records to summarize.\n")

    a("**DMAE interpretation note:** DMAE = EMAE - CMAE, reported as-is, sign "
      "un-inverted. Whether a positive DMAE is 'good' (less adverse excursion) or "
      "'bad' depends on the sign convention MAE uses in the source Pine script -- "
      "if MAE is stored as an adverse-signed (normally negative) value, a positive "
      "DMAE means the event's adverse excursion was smaller than its control's. "
      "This report does not assume that convention; read DMAE alongside the Pine "
      "MAE definition before interpreting its direction.\n")

    a("## Cell Evidence\n")
    a("All 16 possible cells, sorted by PAIR_TOTAL descending.\n")
    a("| CELL | SIDE | SOURCE | AGE | PAIRS | MARKETS | CLASSES | ERET | CRET | DRET | "
      "EHIT | CHIT | ΔHIT | DMFE | DMAE | POS MARKET % | MEDIAN MKT DRET | "
      "MATURITY | BREADTH | CLASSIFICATION |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, c in cells.sort_values("PAIR_TOTAL", ascending=False).iterrows():
        a(f"| {c['CELL']} | {c['SIDE']} | {c['SOURCE']} | {c['AGE_BUCKET']} | "
          f"{c['PAIR_TOTAL']} | {c['MARKETS']} | {c['ASSET_CLASSES']} | "
          f"{_f(c['PAIR_WEIGHTED_ERET'])} | {_f(c['PAIR_WEIGHTED_CRET'])} | {_f(c['PAIR_WEIGHTED_DRET'])} | "
          f"{_f(c['PAIR_WEIGHTED_EHIT'],1)} | {_f(c['PAIR_WEIGHTED_CHIT'],1)} | {_f(c['PAIR_WEIGHTED_DELTA_HIT'],1)} | "
          f"{_f(c['PAIR_WEIGHTED_DMFE'])} | {_f(c['PAIR_WEIGHTED_DMAE'])} | "
          f"{_pct(c['DRET_POS_MARKET_SHARE'])} | {_f(c['MEDIAN_MARKET_DRET'])} | "
          f"{c['MATURITY']} | {c['BREADTH']} | {c['CLASSIFICATION']} |")
    a("")

    a("### Side / Source Breakdown\n")
    a("| GROUP | PAIRS | MARKETS | DRET | ΔHIT | POS MARKET % | MATURITY | BREADTH | CLASSIFICATION |")
    a("|---|---|---|---|---|---|---|---|---|")
    for group_df in (side_source, sources, sides):
        for _, s in group_df.iterrows():
            a(f"| {s['GROUP']} | {s['PAIR_TOTAL']} | {s['MARKETS']} | {_f(s['PAIR_WEIGHTED_DRET'])} | "
              f"{_f(s['PAIR_WEIGHTED_DELTA_HIT'],1)} | {_pct(s['DRET_POS_MARKET_SHARE'])} | "
              f"{s['MATURITY']} | {s['BREADTH']} | {s['CLASSIFICATION']} |")
    a("")

    a("## Cross-Market Consistency\n")
    a(_cross_market_narrative(cells, overall))

    a("## Asset-Class Evidence\n")
    if len(classes):
        a("| ASSET CLASS | PAIRS | MARKETS | DRET | ΔHIT | POS MARKET % | MATURITY | BREADTH | CLASSIFICATION |")
        a("|---|---|---|---|---|---|---|---|---|")
        for _, c in classes.sort_values("PAIR_TOTAL", ascending=False).iterrows():
            a(f"| {c['ASSET_CLASS']} | {c['PAIR_TOTAL']} | {c['MARKETS']} | {_f(c['PAIR_WEIGHTED_DRET'])} | "
              f"{_f(c['PAIR_WEIGHTED_DELTA_HIT'],1)} | {_pct(c['DRET_POS_MARKET_SHARE'])} | "
              f"{c['MATURITY']} | {c['BREADTH']} | {c['CLASSIFICATION']} |")
    else:
        a("No eligible records.")
    a("")

    a("## Market Contributions\n")
    if len(markets):
        total_pairs = int(df["pair"].sum()) if not df.empty else 0
        a("| MARKET | CLASS | PAIRS | PAIR SHARE | DRET | ΔHIT | MATURITY | CLASSIFICATION |")
        a("|---|---|---|---|---|---|---|---|")
        for _, m in markets.sort_values("PAIR_TOTAL", ascending=False).iterrows():
            share = (m["PAIR_TOTAL"] / total_pairs) if total_pairs else None
            a(f"| {m['SYM']} | {m['ASSET_CLASS']} | {m['PAIR_TOTAL']} | {_pct(share)} | "
              f"{_f(m['PAIR_WEIGHTED_DRET'])} | {_f(m['PAIR_WEIGHTED_DELTA_HIT'],1)} | "
              f"{m['MATURITY']} | {m['CLASSIFICATION']} |")
    else:
        a("No eligible records.")
    a("")

    a("## Limitations\n")
    a("1. T44C contains aggregate cell means, not individual matched pairs.")
    a("2. Statistical inference (standard errors, t-tests, bootstrap confidence "
      "intervals, p-values, Sharpe ratios) is therefore intentionally **not** "
      "performed anywhere in this report -- computing it from aggregate means "
      "would require pretending each mean is a single observation, which it is not.")
    a("3. Small samples remain descriptive only, regardless of how the classification "
      "labels read.")
    a("4. Markets are not guaranteed statistically independent (correlated moves "
      "across correlated instruments are still possible).")
    a("5. Pair-weighted results can be influenced by markets that simply generate "
      "more eligible observations, independent of any real cross-market effect.")
    a("6. The matched-control design reduces confounding relative to an unconditional "
      "baseline, but it does not establish causality.")
    a("7. No result in this report changes, gates, or feeds back into the production "
      "model.\n")

    a(f"(Arithmetic tolerance: {arithmetic_tolerance} | Sign epsilon: {sign_epsilon})\n")

    a("## Research Verdict\n")
    a(f"**{verdict}**\n")
    a("This is a descriptive research label, not a trading instruction. T4.4A does "
      "not gate, size, filter, or otherwise influence any live decision.\n")

    return "\n".join(lines) + "\n"


def _cross_market_narrative(cells: pd.DataFrame, overall: pd.DataFrame) -> str:
    represented = cells[cells["PAIR_TOTAL"] > 0]
    lines = []
    if represented.empty:
        return "No cells have any eligible pair data.\n"

    lines.append(f"- Cells with any eligible data: {len(represented)} of 16.")

    most_broad = represented.sort_values("MARKETS", ascending=False).iloc[0]
    lines.append(f"- Most broadly represented cell: **{most_broad['CELL']}** "
                 f"({most_broad['MARKETS']} markets, {most_broad['PAIR_TOTAL']} pairs).")

    with_dret = represented.dropna(subset=["PAIR_WEIGHTED_DRET"])
    if not with_dret.empty:
        strongest_pos = with_dret.sort_values("PAIR_WEIGHTED_DRET", ascending=False).iloc[0]
        strongest_neg = with_dret.sort_values("PAIR_WEIGHTED_DRET", ascending=True).iloc[0]
        if strongest_pos["PAIR_WEIGHTED_DRET"] > 0:
            lines.append(f"- Strongest positive cell by weighted DRET: **{strongest_pos['CELL']}** "
                         f"({_f(strongest_pos['PAIR_WEIGHTED_DRET'])}, {strongest_pos['MARKETS']} markets).")
        if strongest_neg["PAIR_WEIGHTED_DRET"] < 0:
            lines.append(f"- Strongest negative cell by weighted DRET: **{strongest_neg['CELL']}** "
                         f"({_f(strongest_neg['PAIR_WEIGHTED_DRET'])}, {strongest_neg['MARKETS']} markets).")

    if len(overall):
        o = overall.iloc[0]
        lines.append(f"- Across the pooled cohort: {o['POS_DRET_MARKETS']} of {o['N_MARKETS']} "
                     f"markets show positive DRET, {o['NEG_DRET_MARKETS']} negative, "
                     f"{o['ZERO_DRET_MARKETS']} at/near zero.")
        if o["MARKET_CONCENTRATED"]:
            lines.append(f"- **MARKET_CONCENTRATED**: one market accounts for more than "
                         f"{_pct(0.50)} of pooled pairs -- treat the pooled result as that "
                         f"market's result more than a cross-market one.")
        if o["CLASS_CONCENTRATED"]:
            lines.append(f"- **CLASS_CONCENTRATED**: one asset class accounts for more than "
                         f"{_pct(0.70)} of pooled pairs.")

    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------- console

def print_console_summary(results: dict, cohort_label: str = None) -> None:
    integrity = results["integrity"]
    pooled = results["pooled"]
    verdict = results["verdict"]

    print("T4.4A MATCHED-CONTROL AGGREGATION")
    print("-" * 34)
    print(f"Cohort: {', '.join(integrity['cohorts']) or 'n/a'}")
    print(f"Markets: {len(integrity['markets'])}")
    print(f"Classes: {len(integrity['asset_classes'])}")
    print(f"Pairs: {integrity['pair_total']}")
    represented = int((results["cells"]["PAIR_TOTAL"] > 0).sum())
    print(f"Cells represented: {represented}/16")
    print()
    if pooled:
        print(f"Weighted Event Return : {_f(pooled['PAIR_WEIGHTED_ERET'])}")
        print(f"Weighted Control Return: {_f(pooled['PAIR_WEIGHTED_CRET'])}")
        print(f"Weighted Delta Return  : {_f(pooled['PAIR_WEIGHTED_DRET'])}")
        print()
        print(f"Positive markets       : {pooled['POS_DRET_MARKETS']}/{pooled['N_MARKETS']}")
        print(f"Median market delta    : {_f(pooled['MEDIAN_MARKET_DRET'])}")
        print(f"Max market pair share  : {_pct(pooled['PAIR_SHARE_MAX_MARKET'])}")
        print()
        print(f"Evidence: {pooled['CLASSIFICATION']}")
    print(f"Verdict : {verdict}")
    print()
    print("Report: t44a_report/10_report.md")
