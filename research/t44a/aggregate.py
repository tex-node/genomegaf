"""
aggregate.py
Duplicate/snapshot handling (Section 3), semantic validation (Section 5),
derived metrics (Section 7), and every aggregation level -- cell, side x
source, source, side, asset class, market, cohort (Sections 8-13).

STATISTICAL LIMITATION (Section 6): T44C records are aggregate cell
means, not individual matched-pair observations. Nothing in this module
computes standard deviation, standard error, t-tests, bootstrap
confidence intervals, p-values, or Sharpe ratios -- that would require
treating aggregate means as if they were raw observations, which they
are not. This module is a descriptive cross-market consistency analysis
only. See report.py's "Limitations" section for the same statement in
the generated report.
"""

import statistics
from typing import Optional

import pandas as pd

from .parser import METRIC_ATTR_MAP, CANONICAL_CELLS, SOURCE_VALUES

ARITH_TOLERANCE_DEFAULT = 1e-3
SIGN_EPSILON_DEFAULT = 1e-9

MARKET_CONCENTRATION_THRESHOLD = 0.50
CLASS_CONCENTRATION_THRESHOLD = 0.70

CONSISTENCY_METRICS = ["dret", "delta_hit", "dmfe", "dmae"]


def sign(value: Optional[float], epsilon: float = SIGN_EPSILON_DEFAULT) -> int:
    if value is None:
        return 0
    if value > epsilon:
        return 1
    if value < -epsilon:
        return -1
    return 0


# ------------------------------------------------------------- Section 3

def _metrics_equal(a, b, tol: float = 1e-9) -> bool:
    for attr in METRIC_ATTR_MAP.values():
        va, vb = getattr(a, attr), getattr(b, attr)
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            return False
        if abs(va - vb) > tol:
            return False
    return True


def dedupe_snapshots(records: list) -> list:
    """Groups structurally-parsed records by (COHORT, SYM, CLASS, CELL)
    -- a T44C record is a cumulative cell snapshot, not an individual
    pair journal, so repeated exports of the same cell must never be
    summed. Keeps the highest-PAIR record per group; on a PAIR tie with
    differing metrics, flags SNAPSHOT_CONFLICT and keeps the LAST
    encountered record. Mutates records in place (sets retained /
    is_duplicate_dropped / is_snapshot_conflict / warnings) and also
    returns the same list for convenience."""
    groups = {}
    for r in records:
        if not r.parse_ok:
            continue
        key = (r.cohort, r.sym, r.asset_class, r.cell)
        groups.setdefault(key, []).append(r)

    for key, group in groups.items():
        if len(group) == 1:
            group[0].retained = True
            continue

        max_pair = max(r.pair for r in group)
        winners = [r for r in group if r.pair == max_pair]
        for r in group:
            if r.pair != max_pair:
                r.is_duplicate_dropped = True
                r.warnings.append(
                    f"snapshot duplicate: PAIR={r.pair} superseded by a later/larger "
                    f"snapshot with PAIR={max_pair} for the same COHORT/SYM/CLASS/CELL"
                )

        if len(winners) == 1:
            winners[0].retained = True
            continue

        conflict = any(not _metrics_equal(winners[0], other) for other in winners[1:])
        chosen = winners[-1]  # last encountered, per spec
        for r in winners:
            if r is not chosen:
                r.is_duplicate_dropped = True
            if conflict:
                r.is_snapshot_conflict = True
                r.warnings.append(
                    f"snapshot conflict: {len(winners)} records share PAIR={max_pair} for the "
                    f"same COHORT/SYM/CLASS/CELL with differing metrics; retained the last "
                    f"encountered (record_index={chosen.record_index})"
                )
        chosen.retained = True
    return records


# ------------------------------------------------------------- Section 5

def _check_delta(event, control, delta, tol) -> Optional[bool]:
    if event is None or control is None or delta is None:
        return None
    return abs((event - control) - delta) <= tol


def validate_semantics(records: list, arithmetic_tolerance: float = ARITH_TOLERANCE_DEFAULT) -> list:
    """Refines `valid` for every structurally-parsed record (records
    that already failed structural parsing stay invalid). Arithmetic
    consistency (RET/MFE/MAE _delta_ok) is recorded for audit but does
    NOT affect eligibility -- a record whose own numbers don't quite
    reconcile is still usable data, just flagged. Missing required
    fields for a PAIR>0 record, or an EHIT/CHIT outside [0,100], DO make
    the record ineligible for aggregation."""
    for r in records:
        if not r.parse_ok:
            r.valid = False
            continue

        issues = []
        if r.pair is not None and r.pair > 0:
            for key in METRIC_ATTR_MAP:
                if not r.field_present.get(key, False):
                    issues.append(f"{key} missing for a PAIR>0 record")

        for hit_attr, hit_name in [("ehit", "EHIT"), ("chit", "CHIT")]:
            v = getattr(r, hit_attr)
            if v is not None and not (0 <= v <= 100):
                issues.append(f"{hit_name}={v} outside expected range [0,100]")

        r.ret_delta_ok = _check_delta(r.eret, r.cret, r.dret, arithmetic_tolerance)
        r.mfe_delta_ok = _check_delta(r.emfe, r.cmfe, r.dmfe, arithmetic_tolerance)
        r.mae_delta_ok = _check_delta(r.emae, r.cmae, r.dmae, arithmetic_tolerance)
        for ok, label in [(r.ret_delta_ok, "DRET"), (r.mfe_delta_ok, "DMFE"), (r.mae_delta_ok, "DMAE")]:
            if ok is False:
                r.warnings.append(f"{label} does not reconcile with event-control within tolerance "
                                   f"({arithmetic_tolerance}) -- retained, flagged for audit only")

        if issues:
            r.valid = False
            r.warnings.extend(issues)
        else:
            r.valid = True
    return records


# ------------------------------------------------------------- Section 7

def add_derived_fields(records: list, epsilon: float = SIGN_EPSILON_DEFAULT) -> list:
    for r in records:
        r.delta_hit = (r.ehit - r.chit) if (r.ehit is not None and r.chit is not None) else None
        r.dret_sign = sign(r.dret, epsilon)
        r.dmfe_sign = sign(r.dmfe, epsilon)
        r.dmae_sign = sign(r.dmae, epsilon)
    return records


# --------------------------------------------------------- DataFrame view

RECORD_COLUMNS = [
    "record_index", "source_file", "sym", "asset_class", "cohort", "cell",
    "side", "source", "age_bucket", "pair",
    "eret", "cret", "dret", "ehit", "chit", "delta_hit",
    "emfe", "cmfe", "dmfe", "emae", "cmae", "dmae",
    "dret_sign", "dmfe_sign", "dmae_sign",
    "ret_delta_ok", "mfe_delta_ok", "mae_delta_ok",
]


def eligible_dataframe(records: list) -> pd.DataFrame:
    """Records that survived dedup AND semantic validation -- the only
    ones any aggregation level or the market/cell matrices ever see."""
    rows = [{col: getattr(r, col) for col in RECORD_COLUMNS} for r in records if r.eligible]
    return pd.DataFrame(rows, columns=RECORD_COLUMNS)


# ------------------------------------------------------- Sections 8-13

def maturity_label(pair_total: int) -> str:
    if pair_total < 5:
        return "EMBRYONIC"
    if pair_total < 10:
        return "EARLY"
    if pair_total < 20:
        return "DEVELOPING"
    return "MATURE"


def breadth_label(n_markets: int) -> str:
    if n_markets <= 1:
        return "SINGLE_MARKET"
    if n_markets == 2:
        return "LIMITED_BREADTH"
    if n_markets <= 4:
        return "MULTI_MARKET"
    return "BROAD"


def classify_evidence(pair_total: int, n_markets: int, weighted_dret: Optional[float],
                       dret_stats: dict) -> str:
    """Research-only descriptive label. Never VALIDATED / PROVEN /
    SIGNIFICANT / TRADEABLE -- this is not a trading gate."""
    if pair_total < 5 or n_markets < 2:
        return "INSUFFICIENT"

    pos_share = dret_stats.get("pos_share") or 0.0
    neg_share = (dret_stats["neg"] / n_markets) if n_markets else 0.0

    if pair_total >= 20 and n_markets >= 5 and weighted_dret is not None:
        if weighted_dret > 0 and pos_share >= 0.60:
            return "CROSS_MARKET_POS"
        if weighted_dret < 0 and neg_share >= 0.60:
            return "CROSS_MARKET_NEG"

    if weighted_dret is not None:
        if weighted_dret > 0 and pos_share > 0.60:
            return "EARLY_CONSISTENT_POS"
        if weighted_dret < 0 and neg_share > 0.60:
            return "EARLY_CONSISTENT_NEG"

    return "EARLY_MIXED"


def _weighted_mean(df: pd.DataFrame, col: str) -> Optional[float]:
    sub = df.dropna(subset=[col, "pair"])
    sub = sub[sub["pair"] > 0]
    if sub.empty:
        return None
    total = sub["pair"].sum()
    if total <= 0:
        return None
    return float((sub[col] * sub["pair"]).sum() / total)


def _weighted_mean_diff(df: pd.DataFrame, col_a: str, col_b: str) -> Optional[float]:
    sub = df.dropna(subset=[col_a, col_b, "pair"])
    sub = sub[sub["pair"] > 0]
    if sub.empty:
        return None
    total = sub["pair"].sum()
    if total <= 0:
        return None
    return float(((sub[col_a] - sub[col_b]) * sub["pair"]).sum() / total)


def _market_consistency(df: pd.DataFrame, metric_col: str, epsilon: float = SIGN_EPSILON_DEFAULT) -> dict:
    """Collapses to one pair-weighted value per market within this group
    (handles the case of multiple cohorts contributing to the same
    market), then counts how many markets are positive/negative/zero."""
    sub = df.dropna(subset=[metric_col, "pair"])
    sub = sub[sub["pair"] > 0]
    if sub.empty:
        return {"pos": 0, "neg": 0, "zero": 0, "pos_share": None, "median": None, "min": None, "max": None}

    per_market = {}
    for market, g in sub.groupby("sym"):
        total = g["pair"].sum()
        if total > 0:
            per_market[market] = float((g[metric_col] * g["pair"]).sum() / total)

    values = list(per_market.values())
    n = len(values)
    if n == 0:
        return {"pos": 0, "neg": 0, "zero": 0, "pos_share": None, "median": None, "min": None, "max": None}

    pos = sum(1 for v in values if v > epsilon)
    neg = sum(1 for v in values if v < -epsilon)
    zero = n - pos - neg
    return {
        "pos": pos, "neg": neg, "zero": zero,
        "pos_share": pos / n,
        "median": float(statistics.median(values)),
        "min": float(min(values)), "max": float(max(values)),
    }


def asset_class_direction_table(df: pd.DataFrame) -> dict:
    """Per-class pair-weighted DRET and its sign, for the narrative
    'is this broad-based or one class carrying the result' discussion."""
    out = {}
    for cls, g in df.groupby("asset_class"):
        w = _weighted_mean(g, "dret")
        out[cls] = {"pair_total": int(g["pair"].sum()), "weighted_dret": w, "sign": sign(w)}
    return out


def summarize_group(df: pd.DataFrame, group_label: str, group_level: str) -> dict:
    """Computes every metric Sections 8-13 require for one group (an
    exact cell, a side x source pair, an asset class, a market, ...).
    `df` must already be filtered to just this group's eligible rows."""
    pair_total = int(df["pair"].sum()) if not df.empty else 0
    # A market/class whose only rows are PAIR=0 (unmatched) contributes no
    # actual evidence -- excluding it from MARKETS/ASSET_CLASSES keeps this
    # count consistent with POS/NEG_DRET_MARKETS and DRET_POS_MARKET_SHARE
    # below, which are necessarily pair>0 already (a weighted mean over
    # zero pairs is undefined). Counting it here would silently inflate
    # apparent breadth without any data backing it.
    with_pairs = df[df["pair"] > 0] if not df.empty else df
    markets = sorted(with_pairs["sym"].dropna().unique()) if not with_pairs.empty else []
    classes = sorted(with_pairs["asset_class"].dropna().unique()) if not with_pairs.empty else []
    n_markets = len(markets)
    n_classes = len(classes)

    w_eret = _weighted_mean(df, "eret")
    w_cret = _weighted_mean(df, "cret")
    w_dret = _weighted_mean(df, "dret")
    w_ehit = _weighted_mean(df, "ehit")
    w_chit = _weighted_mean(df, "chit")
    w_delta_hit = _weighted_mean_diff(df, "ehit", "chit")
    w_emfe = _weighted_mean(df, "emfe")
    w_cmfe = _weighted_mean(df, "cmfe")
    w_dmfe = _weighted_mean(df, "dmfe")
    w_emae = _weighted_mean(df, "emae")
    w_cmae = _weighted_mean(df, "cmae")
    w_dmae = _weighted_mean(df, "dmae")

    consistency = {m: _market_consistency(df, m) for m in CONSISTENCY_METRICS}

    if pair_total > 0 and not df.empty:
        pair_by_market = df.groupby("sym")["pair"].sum()
        pair_share_max_market = float(pair_by_market.max() / pair_total) if len(pair_by_market) else 0.0
        pair_by_class = df.groupby("asset_class")["pair"].sum()
        pair_share_max_class = float(pair_by_class.max() / pair_total) if len(pair_by_class) else 0.0
    else:
        pair_share_max_market = 0.0
        pair_share_max_class = 0.0

    maturity = maturity_label(pair_total)
    breadth = breadth_label(n_markets)
    classification = classify_evidence(pair_total, n_markets, w_dret, consistency["dret"])

    row = {
        "GROUP_LEVEL": group_level, "GROUP": group_label,
        "MARKETS": n_markets, "ASSET_CLASSES": n_classes, "PAIR_TOTAL": pair_total,
        "PAIR_WEIGHTED_ERET": w_eret, "PAIR_WEIGHTED_CRET": w_cret, "PAIR_WEIGHTED_DRET": w_dret,
        "PAIR_WEIGHTED_EHIT": w_ehit, "PAIR_WEIGHTED_CHIT": w_chit, "PAIR_WEIGHTED_DELTA_HIT": w_delta_hit,
        "PAIR_WEIGHTED_EMFE": w_emfe, "PAIR_WEIGHTED_CMFE": w_cmfe, "PAIR_WEIGHTED_DMFE": w_dmfe,
        "PAIR_WEIGHTED_EMAE": w_emae, "PAIR_WEIGHTED_CMAE": w_cmae, "PAIR_WEIGHTED_DMAE": w_dmae,
        "N_MARKETS": n_markets,
        "POS_DRET_MARKETS": consistency["dret"]["pos"], "NEG_DRET_MARKETS": consistency["dret"]["neg"],
        "ZERO_DRET_MARKETS": consistency["dret"]["zero"],
        "DRET_POS_MARKET_SHARE": consistency["dret"]["pos_share"],
        "MEDIAN_MARKET_DRET": consistency["dret"]["median"],
        "MIN_MARKET_DRET": consistency["dret"]["min"], "MAX_MARKET_DRET": consistency["dret"]["max"],
        "POS_DELTA_HIT_MARKETS": consistency["delta_hit"]["pos"], "NEG_DELTA_HIT_MARKETS": consistency["delta_hit"]["neg"],
        "MEDIAN_MARKET_DELTA_HIT": consistency["delta_hit"]["median"],
        "POS_DMFE_MARKETS": consistency["dmfe"]["pos"], "NEG_DMFE_MARKETS": consistency["dmfe"]["neg"],
        "MEDIAN_MARKET_DMFE": consistency["dmfe"]["median"],
        "POS_DMAE_MARKETS": consistency["dmae"]["pos"], "NEG_DMAE_MARKETS": consistency["dmae"]["neg"],
        "MEDIAN_MARKET_DMAE": consistency["dmae"]["median"],
        "PAIR_SHARE_MAX_MARKET": pair_share_max_market, "PAIR_SHARE_MAX_CLASS": pair_share_max_class,
        "MARKET_CONCENTRATED": pair_share_max_market > MARKET_CONCENTRATION_THRESHOLD,
        "CLASS_CONCENTRATED": pair_share_max_class > CLASS_CONCENTRATION_THRESHOLD,
        "MATCH_COVERAGE": "NOT_AVAILABLE",
        "MATURITY": maturity, "BREADTH": breadth,
        "CLASSIFICATION": classification,
    }
    return row


def cell_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cell in CANONICAL_CELLS:
        side_code, source, age = cell.split("_", 2)
        sub = df[df["cell"] == cell]
        row = summarize_group(sub, group_label=cell, group_level="CELL")
        row.update({"CELL": cell, "SIDE": "BUY" if side_code == "B" else "SELL",
                    "SOURCE": source, "AGE_BUCKET": age})
        rows.append(row)
    return pd.DataFrame(rows)


def side_source_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for side_label, side_code in [("BUY", "B"), ("SELL", "S")]:
        for source in SOURCE_VALUES:
            label = f"{side_code}_{source}"
            sub = df[(df["side"] == side_label) & (df["source"] == source)]
            row = summarize_group(sub, group_label=label, group_level="SIDE_SOURCE")
            row.update({"SIDE": side_label, "SOURCE": source})
            rows.append(row)
    return pd.DataFrame(rows)


def source_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for source in SOURCE_VALUES:
        sub = df[df["source"] == source]
        row = summarize_group(sub, group_label=source, group_level="SOURCE")
        row["SOURCE"] = source
        rows.append(row)
    return pd.DataFrame(rows)


def side_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for side_label in ("BUY", "SELL"):
        sub = df[df["side"] == side_label]
        row = summarize_group(sub, group_label=side_label, group_level="SIDE")
        row["SIDE"] = side_label
        rows.append(row)
    return pd.DataFrame(rows)


def asset_class_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cls in sorted(df["asset_class"].dropna().unique()):
        sub = df[df["asset_class"] == cls]
        row = summarize_group(sub, group_label=cls, group_level="ASSET_CLASS")
        row["ASSET_CLASS"] = cls
        rows.append(row)
    return pd.DataFrame(rows)


def market_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sym in sorted(df["sym"].dropna().unique()):
        sub = df[df["sym"] == sym]
        row = summarize_group(sub, group_label=sym, group_level="MARKET")
        classes = sub["asset_class"].dropna().unique()
        row["SYM"] = sym
        row["ASSET_CLASS"] = classes[0] if len(classes) else None
        rows.append(row)
    return pd.DataFrame(rows)


def overall_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cohort in sorted(df["cohort"].dropna().unique()):
        sub = df[df["cohort"] == cohort]
        row = summarize_group(sub, group_label=cohort, group_level="COHORT")
        row["COHORT"] = cohort
        rows.append(row)
    if not rows:
        rows = [summarize_group(df, group_label="(no cohort)", group_level="COHORT")]
    return pd.DataFrame(rows)


def market_cell_matrices(df: pd.DataFrame):
    """Returns (dret_matrix, pair_matrix), both rows=market, columns=the
    16 canonical cells. A market/cell combination with no eligible data
    is left blank (DRET) or 0 (PAIR) rather than omitted, so the shape
    of coverage is visible even where there's nothing to report."""
    markets = sorted(df["sym"].dropna().unique())
    dret_rows, pair_rows = [], []
    for market in markets:
        msub = df[df["sym"] == market]
        dret_row = {"MARKET": market}
        pair_row = {"MARKET": market}
        for cell in CANONICAL_CELLS:
            csub = msub[msub["cell"] == cell]
            pair_sum = int(csub["pair"].sum()) if not csub.empty else 0
            pair_row[cell] = pair_sum
            dret_row[cell] = _weighted_mean(csub, "dret") if pair_sum > 0 else None
        dret_rows.append(dret_row)
        pair_rows.append(pair_row)
    dret_df = pd.DataFrame(dret_rows, columns=["MARKET"] + CANONICAL_CELLS)
    pair_df = pd.DataFrame(pair_rows, columns=["MARKET"] + CANONICAL_CELLS)
    return dret_df, pair_df
