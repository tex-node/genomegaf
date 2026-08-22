"""T4.4A.1 -- append-only longitudinal evidence history.

This module consumes completed T4.4A report directories. It never parses
Pine state, rematches controls, tunes thresholds, or changes production
logic. Each accepted checkpoint is immutable once recorded so the
chronology of the research evidence cannot be silently rewritten.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CHECKPOINT_COLUMNS = [
    "checkpoint",
    "captured_at_utc",
    "source_generated_at_utc",
    "source_report_sha256",
    "source_manifest_sha256",
    "pair_total",
    "markets",
    "asset_classes",
    "records_retained",
    "dret",
    "delta_hit",
    "dmfe",
    "dmae",
    "positive_market_share",
    "median_market_dret",
    "maturity",
    "breadth",
    "classification",
    "research_verdict",
]

SOURCE_COLUMNS = [
    "checkpoint",
    "captured_at_utc",
    "group",
    "pairs",
    "markets",
    "dret",
    "delta_hit",
    "positive_market_share",
    "maturity",
    "breadth",
    "classification",
]

REQUIRED_REPORT_FILES = (
    "04_side_source_summary.csv",
    "07_overall_summary.csv",
    "10_report.md",
    "11_manifest.json",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _scalar(row: pd.Series, name: str, default=None):
    if name not in row.index:
        return default
    value = row[name]
    if pd.isna(value):
        return default
    return value


def _read_report(report_dir: Path) -> tuple[dict, list[dict]]:
    report_dir = Path(report_dir)
    missing = [name for name in REQUIRED_REPORT_FILES if not (report_dir / name).is_file()]
    if missing:
        raise ValueError(
            f"Not a complete T4.4A report directory: {report_dir}; missing: {', '.join(missing)}"
        )

    manifest_path = report_dir / "11_manifest.json"
    report_path = report_dir / "10_report.md"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    overall = pd.read_csv(report_dir / "07_overall_summary.csv")
    if len(overall) != 1:
        raise ValueError(f"Expected exactly one overall row in {report_dir / '07_overall_summary.csv'}")
    o = overall.iloc[0]

    checkpoint = {
        "source_generated_at_utc": manifest.get("generated_at_utc"),
        "source_report_sha256": _sha256(report_path),
        "source_manifest_sha256": _sha256(manifest_path),
        "pair_total": int(manifest.get("pair_total", 0)),
        "markets": int(_scalar(o, "N_MARKETS", len(manifest.get("markets", []))) or 0),
        "asset_classes": len(manifest.get("asset_classes", [])),
        "records_retained": int(manifest.get("records_retained", 0)),
        "dret": _scalar(o, "PAIR_WEIGHTED_DRET"),
        "delta_hit": _scalar(o, "PAIR_WEIGHTED_DELTA_HIT"),
        "dmfe": _scalar(o, "PAIR_WEIGHTED_DMFE"),
        "dmae": _scalar(o, "PAIR_WEIGHTED_DMAE"),
        "positive_market_share": _scalar(o, "DRET_POS_MARKET_SHARE"),
        "median_market_dret": _scalar(o, "MEDIAN_MARKET_DRET"),
        "maturity": _scalar(o, "MATURITY", "UNKNOWN"),
        "breadth": _scalar(o, "BREADTH", "UNKNOWN"),
        "classification": _scalar(o, "CLASSIFICATION", "UNKNOWN"),
    }

    # Keep verdict provenance deterministic without importing report.py and
    # creating a circular dependency. The report itself is authoritative.
    verdict = "UNKNOWN"
    for line in report_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("**") and line.endswith("**") and "Research Verdict" not in line:
            # The first bold-only line after the heading is the current report verdict.
            # Restrict the search to the tail of the document below the heading.
            pass
    text = report_path.read_text(encoding="utf-8")
    marker = "## Research Verdict"
    if marker in text:
        tail = text.split(marker, 1)[1]
        for line in tail.splitlines():
            line = line.strip()
            if line.startswith("**") and line.endswith("**") and len(line) > 4:
                verdict = line[2:-2]
                break
    checkpoint["research_verdict"] = verdict

    side_source = pd.read_csv(report_dir / "04_side_source_summary.csv")
    source_rows: list[dict] = []
    for _, row in side_source.iterrows():
        label = _scalar(row, "GROUP")
        if not label:
            continue
        source_rows.append({
            "group": str(label),
            "pairs": int(_scalar(row, "PAIR_TOTAL", 0) or 0),
            "markets": int(_scalar(row, "MARKETS", 0) or 0),
            "dret": _scalar(row, "PAIR_WEIGHTED_DRET"),
            "delta_hit": _scalar(row, "PAIR_WEIGHTED_DELTA_HIT"),
            "positive_market_share": _scalar(row, "DRET_POS_MARKET_SHARE"),
            "maturity": _scalar(row, "MATURITY", "UNKNOWN"),
            "breadth": _scalar(row, "BREADTH", "UNKNOWN"),
            "classification": _scalar(row, "CLASSIFICATION", "UNKNOWN"),
        })

    return checkpoint, source_rows


def _load_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path)
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    return df[columns]


def append_checkpoint(report_dir: Path, store_dir: Path, label: str) -> dict:
    """Append one immutable checkpoint to a longitudinal T4.4A.1 store.

    Re-running the exact same label with the exact same report is idempotent.
    Reusing a label for different evidence raises ValueError instead of
    rewriting history.
    """
    label = str(label).strip()
    if not label:
        raise ValueError("Checkpoint label must not be empty")

    checkpoint, source_rows = _read_report(Path(report_dir))
    store_dir = Path(store_dir)
    store_dir.mkdir(parents=True, exist_ok=True)

    checkpoints_path = store_dir / "01_checkpoints.csv"
    sources_path = store_dir / "02_source_trend.csv"
    checkpoints = _load_csv(checkpoints_path, CHECKPOINT_COLUMNS)
    sources = _load_csv(sources_path, SOURCE_COLUMNS)

    existing = checkpoints[checkpoints["checkpoint"].astype(str) == label]
    if len(existing):
        old = existing.iloc[0]
        same = (
            str(old["source_report_sha256"]) == checkpoint["source_report_sha256"]
            and str(old["source_manifest_sha256"]) == checkpoint["source_manifest_sha256"]
        )
        if same:
            write_history_report(checkpoints, sources, store_dir)
            return {"status": "UNCHANGED", "checkpoint": label, "count": len(checkpoints)}
        raise ValueError(
            f"Checkpoint '{label}' already exists with different evidence; history is append-only"
        )

    captured = datetime.now(timezone.utc).isoformat()
    checkpoint.update({"checkpoint": label, "captured_at_utc": captured})
    checkpoint_row = pd.DataFrame([checkpoint], columns=CHECKPOINT_COLUMNS)
    checkpoints = pd.concat([checkpoints, checkpoint_row], ignore_index=True)

    new_sources = []
    for row in source_rows:
        row = dict(row)
        row.update({"checkpoint": label, "captured_at_utc": captured})
        new_sources.append(row)
    if new_sources:
        sources = pd.concat(
            [sources, pd.DataFrame(new_sources, columns=SOURCE_COLUMNS)], ignore_index=True
        )

    checkpoints.to_csv(checkpoints_path, index=False)
    sources.to_csv(sources_path, index=False)
    write_history_report(checkpoints, sources, store_dir)
    write_history_manifest(checkpoints, store_dir)

    return {"status": "APPENDED", "checkpoint": label, "count": len(checkpoints)}


def _fmt(value, nd=4):
    if value is None or pd.isna(value):
        return "NA"
    if isinstance(value, (float, int)):
        return f"{float(value):.{nd}f}"
    return str(value)


def _pct(value):
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value) * 100:.1f}%"


def write_history_report(checkpoints: pd.DataFrame, sources: pd.DataFrame, store_dir: Path) -> None:
    lines: list[str] = []
    a = lines.append
    a("# T4.4A.1 Longitudinal Evidence Accumulation Report\n")
    a("This report preserves the chronology of successive T4.4A descriptive checkpoints. "
      "It is append-only research evidence: no thresholds are tuned, no market is excluded, "
      "and no result feeds back into the production model.\n")

    a("## Checkpoint History\n")
    a("| CHECKPOINT | PAIRS | MARKETS | DRET | ΔHIT | DMFE | DMAE | POS MKT % | MEDIAN MKT DRET | MATURITY | BREADTH | CLASSIFICATION | VERDICT |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|")
    for _, r in checkpoints.iterrows():
        a(
            f"| {r['checkpoint']} | {int(r['pair_total'])} | {int(r['markets'])} | "
            f"{_fmt(r['dret'])} | {_fmt(r['delta_hit'], 2)} | {_fmt(r['dmfe'])} | "
            f"{_fmt(r['dmae'])} | {_pct(r['positive_market_share'])} | "
            f"{_fmt(r['median_market_dret'])} | {r['maturity']} | {r['breadth']} | "
            f"{r['classification']} | {r['research_verdict']} |"
        )
    a("")

    a("## BAND vs DIV Through Time\n")
    a("The source split is shown because the current research question specifically requires "
      "tracking whether BAND and DIV behave as different event populations. This is descriptive "
      "monitoring only, not source selection.\n")
    a("| CHECKPOINT | GROUP | PAIRS | MARKETS | DRET | ΔHIT | POS MKT % | MATURITY | BREADTH | CLASSIFICATION |")
    a("|---|---|---:|---:|---:|---:|---:|---|---|---|")
    wanted = {"BAND", "DIV", "B_BAND", "B_DIV", "S_BAND", "S_DIV"}
    for _, r in sources.iterrows():
        if str(r["group"]) not in wanted:
            continue
        a(
            f"| {r['checkpoint']} | {r['group']} | {int(r['pairs'])} | {int(r['markets'])} | "
            f"{_fmt(r['dret'])} | {_fmt(r['delta_hit'], 2)} | {_pct(r['positive_market_share'])} | "
            f"{r['maturity']} | {r['breadth']} | {r['classification']} |"
        )
    a("")

    a("## Interpretation Guardrails\n")
    a("- Each row is a frozen descriptive checkpoint, not an independent statistical observation.")
    a("- T44C still contains aggregate matched-control cell means, not pair-level data.")
    a("- Do not compute p-values, confidence intervals, Sharpe ratios, or bootstrap inference from this history.")
    a("- Do not remove a market, source, side, or cell because it weakens the result.")
    a("- Do not promote BAND, DIV, or any other subgroup into model logic from this report.")
    a("- T4.4B remains the appropriate phase for pair-level export and legitimate paired inference.\n")

    a("## Current Research Status\n")
    if len(checkpoints):
        r = checkpoints.iloc[-1]
        a(
            f"Latest checkpoint **{r['checkpoint']}**: {int(r['pair_total'])} matched pairs across "
            f"{int(r['markets'])} markets; pooled DRET {_fmt(r['dret'])}; "
            f"classification **{r['classification']}**; verdict **{r['research_verdict']}**."
        )
    else:
        a("No checkpoints recorded.")

    (Path(store_dir) / "03_history.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_history_manifest(checkpoints: pd.DataFrame, store_dir: Path) -> None:
    payload = {
        "schema": "T4.4A.1-history-v1",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint_count": int(len(checkpoints)),
        "checkpoints": [
            {
                "checkpoint": str(r["checkpoint"]),
                "source_report_sha256": str(r["source_report_sha256"]),
                "source_manifest_sha256": str(r["source_manifest_sha256"]),
            }
            for _, r in checkpoints.iterrows()
        ],
        "policy": {
            "append_only": True,
            "no_threshold_tuning": True,
            "no_model_feedback": True,
            "non_inferential": True,
        },
    }
    (Path(store_dir) / "04_history_manifest.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
