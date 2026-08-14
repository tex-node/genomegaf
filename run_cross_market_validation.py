"""
run_cross_market_validation.py
Tests whether pooling GAF pattern fingerprints across instruments AND
timeframes into one shared database produces better forward-return
signal than restricting matches to an instrument's own history (which is
what every other report in this repo tests).

Global point-in-time discipline: every (instrument, timeframe) source is
split at the SAME calendar cutoff timestamp, not each source's own
60/40 fraction -- see multi_source_pattern_db.py's docstring for why
that matters once fingerprints are pooled across sources.

For each instrument, evaluates its own H1 holdout bars two ways against
the *same* frozen shared database (apples-to-apples control):
  - pooled:  search all sources (every instrument x every timeframe)
  - control: search only that instrument's own H1-sourced fingerprints
             within the same pool (isolates whether pooling adds
             anything beyond what single-source H1 matching already had)

Run: py run_cross_market_validation.py [--instruments US500,EURUSD] [--timeframes M15,H1]
"""

import argparse
import time
from datetime import datetime, timezone

import numpy as np

import mt5_feed
from multi_source_pattern_db import MultiSourceDB, ingest_source, normalize_target_series, live_fingerprint_at
from projection import project_resolved
from validation import apply_positions, compute_metrics, hit_rate_test, random_direction_baseline

ALL_INSTRUMENTS = ["US500", "US100", "DJIA", "EURUSD", "XAUUSD"]
ALL_TIMEFRAMES = ["M5", "M15", "H1", "D1"]
QUERY_TIMEFRAME = "H1"   # evaluate using each instrument's own H1 series

WINDOW = 10
HORIZON = 10             # bars, native to each source's own timeframe
NORMALIZATION = "rank"
RANK_LOOKBACK = 252
METHOD = "gasf"
SIMILARITY_THRESHOLD = 0.90
MIN_MATCHES = 5
DEV_FRAC = 0.6
MC_SIMS = 2000
FALLBACK_COST_FRAC = {
    "US500": 0.0004, "US100": 0.0004, "DJIA": 0.0004, "EURUSD": 0.00006, "XAUUSD": 0.0004,
}

GLOBAL_START = datetime(2025, 4, 16, tzinfo=timezone.utc)
GLOBAL_END = datetime(2026, 8, 14, tzinfo=timezone.utc)


def fmt(x, nd=3):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def fmt_pct(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:+.2f}%"


def fetch_all_sources(instruments, timeframes):
    """Fetch every (instrument, timeframe) combo for the full global range.
    Returns {(instrument, timeframe): mt5_feed.Bars}."""
    mt5_feed.connect()
    try:
        out = {}
        for kw in instruments:
            for tf in timeframes:
                t0 = time.time()
                bars = mt5_feed.fetch_history_range_chunked(kw, tf, GLOBAL_START, GLOBAL_END)
                out[(kw, tf)] = bars
                print(f"  fetched {kw:8s} {tf:4s}: {len(bars.close):6d} bars ({time.time()-t0:.1f}s)")
        return out
    finally:
        mt5_feed.disconnect()


def get_cost_fracs(instruments):
    mt5_feed.connect()
    try:
        costs = {}
        for kw in instruments:
            symbol = mt5_feed.resolve_symbol(kw)
            info = mt5_feed.symbol_cost_info(symbol)
            costs[kw] = info
        return costs
    finally:
        mt5_feed.disconnect()


def build_shared_db(sources: dict, cutoff_ts: int) -> tuple:
    """Ingests every source into one MultiSourceDB. Returns (db, source_id_map)
    where source_id_map[(instrument, timeframe)] -> int id."""
    fp_len = WINDOW * (WINDOW - 1) // 2
    db = MultiSourceDB(fingerprint_len=fp_len, max_size=1_000_000)
    source_id_map = {}
    for i, (key, bars) in enumerate(sources.items()):
        source_id_map[key] = i
        t0 = time.time()
        n_added = ingest_source(
            db, i, bars.high, bars.low, bars.close, bars.time,
            window=WINDOW, horizon=HORIZON, normalization=NORMALIZATION,
            rank_lookback=RANK_LOOKBACK, method=METHOD, cutoff_ts=cutoff_ts,
        )
        print(f"  ingested {key[0]:8s} {key[1]:4s}: {n_added:7d} fingerprints ({time.time()-t0:.1f}s)")
    print(f"  total DB size: {len(db)}")
    return db, source_id_map


def evaluate_instrument(keyword: str, bars, db: MultiSourceDB, source_id_map: dict,
                         cutoff_ts: int, cost_frac: float, report_lines: list):
    x = normalize_target_series(bars.high, bars.low, bars.close,
                                 normalization=NORMALIZATION, rank_lookback=RANK_LOOKBACK)
    n = len(bars.close)
    holdout_start = int(np.searchsorted(bars.time, cutoff_ts))
    own_source_id = source_id_map[(keyword, QUERY_TIMEFRAME)]

    results = {}
    for label, restrict in [("pooled", None), ("control_own_h1_only", own_source_id)]:
        directions = np.zeros(n)
        has_signal = np.zeros(n, dtype=bool)
        for i in range(holdout_start, n):
            fp = live_fingerprint_at(x, i, WINDOW, method=METHOD)
            if fp is None:
                continue
            matches = db.query(fp, int(bars.time[i]), SIMILARITY_THRESHOLD, only_source_id=restrict)
            sig = project_resolved(matches, min_matches=MIN_MATCHES)
            has_signal[i] = True
            directions[i] = sig.direction

        equity = apply_positions(directions, has_signal, bars.close, cost_frac=cost_frac)
        holdout_equity = equity[holdout_start:]
        holdout_time = bars.time[holdout_start:]
        metrics = compute_metrics(holdout_equity, holdout_time)
        hit = hit_rate_test(directions[holdout_start:], bars.close[holdout_start:], HORIZON)
        mc = random_direction_baseline(directions[holdout_start:], has_signal[holdout_start:],
                                        bars.close[holdout_start:], cost_frac, n_sims=MC_SIMS)
        n_active = int((directions[holdout_start:] != 0).sum())
        results[label] = dict(metrics=metrics, hit=hit, mc=mc, n_active=n_active)

        report_lines.append(f"\n**{label}** ({n_active} active signals of {n - holdout_start} holdout bars):\n\n")
        report_lines.append("| Metric | Value |\n|---|---|\n")
        report_lines.append(f"| Total return | {fmt_pct(metrics['total_return'])} |\n")
        report_lines.append(f"| Sharpe (annualized) | {fmt(metrics['sharpe'])} |\n")
        report_lines.append(f"| Max drawdown | {fmt_pct(metrics['max_drawdown'])} |\n")
        report_lines.append(f"| Profit factor | {fmt(metrics['profit_factor'])} |\n")
        report_lines.append(f"| Hit rate | {fmt_pct(hit['hit_rate'])} (n={hit['n']}, p={fmt(hit['p_value'], 4)}) |\n")
        report_lines.append(f"| Random-direction MC baseline | real result at percentile "
                             f"{fmt_pct(mc['percentile_of_real'])} of {mc['n_sims']} sims |\n")

    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruments", default=",".join(ALL_INSTRUMENTS))
    parser.add_argument("--timeframes", default=",".join(ALL_TIMEFRAMES))
    parser.add_argument("--out", default="VALIDATION_REPORT_cross_market.md")
    args = parser.parse_args()
    instruments = [s.strip() for s in args.instruments.split(",") if s.strip()]
    timeframes = [s.strip() for s in args.timeframes.split(",") if s.strip()]

    print(f"Instruments: {instruments}")
    print(f"Timeframes: {timeframes}")
    print(f"Global range: {GLOBAL_START.date()} to {GLOBAL_END.date()}")

    print("\nFetching all sources...")
    sources = fetch_all_sources(instruments, timeframes)

    global_start_ts = int(GLOBAL_START.timestamp())
    global_end_ts = int(GLOBAL_END.timestamp())
    cutoff_ts = int(global_start_ts + DEV_FRAC * (global_end_ts - global_start_ts))
    cutoff_str = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).date()
    print(f"\nGlobal calendar cutoff: {cutoff_str} ({int(DEV_FRAC*100)}% through the range)")

    print("\nBuilding shared cross-market database...")
    t0 = time.time()
    db, source_id_map = build_shared_db(sources, cutoff_ts)
    print(f"  done in {time.time()-t0:.1f}s")

    print("\nGetting transaction costs...")
    costs = get_cost_fracs(instruments)

    report_lines = [
        "# Cross-market validation — GenomeGAF\n\n",
        f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}. "
        f"Pooled sources: {instruments} x {timeframes}. Query timeframe: {QUERY_TIMEFRAME}. "
        f"window={WINDOW}, horizon={HORIZON} (bars, native to each source), "
        f"normalization={NORMALIZATION}, threshold={SIMILARITY_THRESHOLD}.\n\n",
        f"Global calendar cutoff: **{cutoff_str}** ({GLOBAL_START.date()} to {GLOBAL_END.date()}, "
        f"{int(DEV_FRAC*100)}/{int((1-DEV_FRAC)*100)} split). Every source is split at this SAME "
        f"timestamp regardless of instrument or timeframe, not each source's own fraction -- "
        f"see multi_source_pattern_db.py for why that matters once fingerprints are pooled.\n\n",
        f"Shared database size after ingestion: **{len(db)}** fingerprints across "
        f"{len(source_id_map)} sources.\n\n",
        "Each instrument is evaluated on its own H1 holdout bars two ways against the identical "
        "frozen database: **pooled** (search everything) vs **control** (search only that "
        "instrument's own H1-sourced fingerprints within the same pool) — the control isolates "
        "whether pooling adds anything beyond single-source H1 matching.\n",
    ]

    print("\nEvaluating each instrument (pooled vs control)...")
    all_results = {}
    for kw in instruments:
        print(f"\n=== {kw} ===")
        bars = sources[(kw, QUERY_TIMEFRAME)]
        cost = costs[kw]
        mid = float(np.mean(bars.close))
        cost_frac = cost["spread_price"] / mid if cost["spread_price"] > 0 else FALLBACK_COST_FRAC.get(kw, 0.0005)

        report_lines.append(f"\n## {kw}\n")
        t0 = time.time()
        res = evaluate_instrument(kw, bars, db, source_id_map, cutoff_ts, cost_frac, report_lines)
        all_results[kw] = res
        print(f"  pooled: Sharpe={fmt(res['pooled']['metrics']['sharpe'])} "
              f"hit_rate={fmt_pct(res['pooled']['hit']['hit_rate'])} (p={fmt(res['pooled']['hit']['p_value'],4)})")
        print(f"  control: Sharpe={fmt(res['control_own_h1_only']['metrics']['sharpe'])} "
              f"hit_rate={fmt_pct(res['control_own_h1_only']['hit']['hit_rate'])} "
              f"(p={fmt(res['control_own_h1_only']['hit']['p_value'],4)})")
        print(f"  ({time.time()-t0:.1f}s)")

    report_lines.append("\n## Summary\n\n")
    report_lines.append("| Instrument | Pooled Sharpe (p) | Control Sharpe (p) | Pooled n active | Control n active |\n")
    report_lines.append("|---|---|---|---|---|\n")
    for kw, res in all_results.items():
        p, c = res["pooled"], res["control_own_h1_only"]
        report_lines.append(
            f"| {kw} | {fmt(p['metrics']['sharpe'])} (p={fmt(p['hit']['p_value'],4)}) | "
            f"{fmt(c['metrics']['sharpe'])} (p={fmt(c['hit']['p_value'],4)}) | "
            f"{p['n_active']} | {c['n_active']} |\n"
        )

    with open(args.out, "w", encoding="utf-8") as f:
        f.writelines(report_lines)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
