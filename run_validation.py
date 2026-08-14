"""
run_validation.py
Driver: for each configured instrument, pull real historical data from MT5
(cross-checked against Yahoo Finance), run parameter selection via
walk-forward cross-validation on a development slice, evaluate the chosen
config exactly once on an untouched holdout slice, run statistical
significance tests, and write everything to a report file.

Run: py run_validation.py [--timeframe H1|M15|D1] [--bars 8000] [--out-prefix VALIDATION_REPORT]
"""

import argparse
import json
import sys
import time
import traceback

import numpy as np

import mt5_feed
import yahoo_feed
from gaf_indicator import GAFIndicatorConfig
from validation import (
    run_pipeline, compute_metrics, hit_rate_test, random_direction_baseline,
    select_best_config,
)

INSTRUMENTS = ["US500", "US100", "DJIA", "EURUSD", "XAUUSD"]
DEV_FRAC = 0.6           # first 60% of history: parameter selection only
CV_FOLDS = 3
MC_SIMS = 2000
FALLBACK_COST_FRAC = {   # used only if MT5 reports a zero/stale spread
    "US500": 0.0004, "US100": 0.0004, "DJIA": 0.0004,
    "EURUSD": 0.00006, "XAUUSD": 0.0004,
}

_args = None  # set in main(), read by run_one()/cross_check_with_yahoo()

# Deliberately smaller than validation.default_param_grid() to keep the
# full 5-instrument run tractable; widen this once you've seen which
# region of parameter space is promising.
#
# Thresholds are lower for 'enhanced' than 'baseline' on purpose: splitting
# the pattern DB across 9 regime buckets cuts the candidate pool for any
# given query by roughly 9x, so the same 0.90-0.95 threshold that worked
# unfiltered starved most instruments to 0-10 active signals in the first
# enhanced H1 run. 0.95 is dropped entirely for 'enhanced' since it's
# strictly more restrictive than 0.90, which already produced zero
# signals for 3 of 5 instruments.
PARAM_GRID_BY_FEATURE_SET = {
    "baseline": [
        dict(window=w, horizon=h, threshold=t)
        for w in (10, 20) for h in (5, 10) for t in (0.90, 0.95)
    ],
    "enhanced": [
        dict(window=w, horizon=h, threshold=t)
        for w in (10, 20) for h in (5, 10) for t in (0.75, 0.80, 0.85, 0.90)
    ],
}

# Feature sets ported from the v2 experiment (rank normalization, regime
# filtering, recency-decay weighting). 'baseline' matches GAFIndicatorConfig's
# own defaults exactly, so it's identical to the original H1/M15/D1 runs.
FEATURE_SETS = {
    "baseline": dict(),
    "enhanced": dict(
        normalization="rank", rank_lookback=252,
        use_regime_filter=True, trend_lookback=50, vol_lookback=100,
        recency_halflife=500,
    ),
}


def make_cfg(window, horizon, threshold, base, extra=None):
    return GAFIndicatorConfig(window=window, atr_period=base.atr_period, horizon=horizon,
                               method=base.method, similarity_threshold=threshold,
                               min_matches=base.min_matches, max_db_size=base.max_db_size,
                               **(extra or {}))


def fmt_pct(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:+.2f}%"


def fmt(x, nd=3):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


YAHOO_PERIOD = {"M15": "60d", "H1": "730d", "D1": "max"}
_ALIGN_BUCKET = {"M15": 900, "H1": 3600, "D1": 86400}


def cross_check_with_yahoo(keyword, mt5_bars):
    try:
        yh = yahoo_feed.fetch_history(keyword, _args.timeframe, period=YAHOO_PERIOD[_args.timeframe])
    except Exception as e:
        return f"Yahoo cross-check failed: {e}"
    bucket = _ALIGN_BUCKET[_args.timeframe]
    mt5_t = (mt5_bars.time // bucket).astype(np.int64)
    yh_t = (yh.time // bucket).astype(np.int64)
    common, i1, i2 = np.intersect1d(mt5_t, yh_t, return_indices=True)
    if len(common) < 50:
        return f"Yahoo cross-check: only {len(common)} overlapping hourly bars, skipped."
    r_mt5 = np.diff(mt5_bars.close[i1]) / mt5_bars.close[i1][:-1]
    r_yh = np.diff(yh.close[i2]) / yh.close[i2][:-1]
    corr = float(np.corrcoef(r_mt5, r_yh)[0, 1])
    return f"Yahoo cross-check: {len(common)} overlapping bars, hourly-return correlation = {corr:.4f}"


def run_one(keyword: str, report_lines: list):
    print(f"\n=== {keyword} ===")
    report_lines.append(f"\n## {keyword}\n")

    mt5_feed.connect()
    try:
        bars = mt5_feed.fetch_history(keyword, _args.timeframe, count=_args.bars)
        symbol = mt5_feed.resolve_symbol(keyword)
        cost = mt5_feed.symbol_cost_info(symbol)
    finally:
        mt5_feed.disconnect()

    n = len(bars.close)
    mid = float(np.mean(bars.close))
    cost_frac = cost["spread_price"] / mid if cost["spread_price"] > 0 else FALLBACK_COST_FRAC.get(keyword, 0.0005)
    cost_note = "" if cost["spread_price"] > 0 else " (MT5 reported 0 spread — used a conservative fallback assumption instead)"

    print(f"{n} {_args.timeframe} bars from MT5 symbol {symbol}. Round-turn cost ~{cost_frac*10000:.2f} bps{cost_note}.")
    report_lines.append(f"- Symbol: `{symbol}` (MT5) — {n} {_args.timeframe} bars "
                         f"({time.strftime('%Y-%m-%d', time.gmtime(bars.time[0]))} to "
                         f"{time.strftime('%Y-%m-%d', time.gmtime(bars.time[-1]))})\n")
    report_lines.append(f"- Round-turn transaction cost used: {cost_frac*10000:.2f} bps{cost_note}\n")
    report_lines.append(f"- {cross_check_with_yahoo(keyword, bars)}\n")

    dev_end = int(n * DEV_FRAC)
    base_cfg = GAFIndicatorConfig()
    extra = FEATURE_SETS[_args.feature_set]
    param_grid = PARAM_GRID_BY_FEATURE_SET[_args.feature_set]
    grid = [make_cfg(g["window"], g["horizon"], g["threshold"], base_cfg, extra) for g in param_grid]
    report_lines.append(f"- Feature set: **{_args.feature_set}** ({extra or 'library defaults'})\n")

    print(f"Selecting config via {CV_FOLDS}-fold walk-forward CV on first {dev_end} bars (development slice)...")
    t0 = time.time()
    best_cfg, all_scores = select_best_config(bars.high, bars.low, bars.close, dev_end, grid, CV_FOLDS, cost_frac)
    print(f"  done in {time.time()-t0:.1f}s. Best: window={best_cfg.window} horizon={best_cfg.horizon} "
          f"threshold={best_cfg.similarity_threshold} (mean fold Sharpe {all_scores[0][0]:+.3f})")
    report_lines.append(f"- Parameter selection: {CV_FOLDS}-fold walk-forward CV over "
                         f"{len(grid)} configs on the first {dev_end} bars (development slice, never touches holdout)\n")
    report_lines.append(f"- Selected: window={best_cfg.window}, horizon={best_cfg.horizon}, "
                         f"threshold={best_cfg.similarity_threshold} (mean fold Sharpe {all_scores[0][0]:+.3f})\n")

    # ---- Final, once-only evaluation on the untouched holdout slice ----
    print("Evaluating chosen config once on the untouched holdout slice...")
    t0 = time.time()
    result = run_pipeline(bars.high, bars.low, bars.close, best_cfg, train_end_idx=dev_end, cost_frac=cost_frac)
    holdout_equity = result.equity[dev_end:]
    holdout_time = bars.time[dev_end:]
    metrics = compute_metrics(holdout_equity, holdout_time)
    hit = hit_rate_test(result.directions[dev_end:], bars.close[dev_end:], best_cfg.horizon)
    mc = random_direction_baseline(result.directions[dev_end:], result.has_signal[dev_end:],
                                    bars.close[dev_end:], cost_frac, n_sims=MC_SIMS)
    print(f"  done in {time.time()-t0:.1f}s.")

    n_signals = int(result.has_signal[dev_end:].sum())
    n_active = int((result.directions[dev_end:] != 0).sum())
    report_lines.append(f"\n**Holdout results ({n - dev_end} bars the DB never trained on, walk-forward, "
                         f"cost-adjusted):**\n\n")
    report_lines.append(f"| Metric | Value |\n|---|---|\n")
    report_lines.append(f"| Bars with a live signal | {n_signals} |\n")
    report_lines.append(f"| Bars with an active (non-zero) direction | {n_active} |\n")
    report_lines.append(f"| Total return | {fmt_pct(metrics['total_return'])} |\n")
    report_lines.append(f"| CAGR | {fmt_pct(metrics['cagr'])} |\n")
    report_lines.append(f"| Sharpe (annualized) | {fmt(metrics['sharpe'])} |\n")
    report_lines.append(f"| Sortino (annualized) | {fmt(metrics['sortino'])} |\n")
    report_lines.append(f"| Max drawdown | {fmt_pct(metrics['max_drawdown'])} |\n")
    report_lines.append(f"| Profit factor | {fmt(metrics['profit_factor'])} |\n")
    report_lines.append(f"| Win rate (active bars) | {fmt_pct(metrics['win_rate'])} |\n")
    report_lines.append(f"| Hit rate (direction sign vs realized sign) | "
                         f"{fmt_pct(hit['hit_rate'])} (n={hit['n']}, p={fmt(hit['p_value'], 4)}) |\n")
    report_lines.append(f"| Random-direction MC baseline | mean final equity {fmt(mc['null_mean'])}, "
                         f"real result at percentile {fmt_pct(mc['percentile_of_real'])} of {mc['n_sims']} sims |\n")

    verdict = interpret(metrics, hit, mc)
    report_lines.append(f"\n**Read:** {verdict}\n")
    print(f"  Verdict: {verdict}")

    # ---- Reference: online mode (no train/test split) for comparison ----
    print("Running online-mode reference (no walk-forward split) for comparison...")
    online = run_pipeline(bars.high, bars.low, bars.close, best_cfg, train_end_idx=None, cost_frac=cost_frac)
    online_metrics = compute_metrics(online.equity, bars.time)
    report_lines.append(f"\n**For comparison — same config, online mode (continuously re-trained, no "
                         f"train/test split, like the original prototype's backtest): Sharpe "
                         f"{fmt(online_metrics['sharpe'])}, total return {fmt_pct(online_metrics['total_return'])}.** "
                         f"A materially better online number than the holdout number above is itself a warning sign "
                         f"of overfitting to in-sample structure.\n")

    return {
        "keyword": keyword, "metrics": metrics, "hit": hit, "mc": mc,
        "best_cfg": best_cfg, "online_metrics": online_metrics,
    }


def interpret(metrics, hit, mc):
    p = hit["p_value"]
    pct = mc["percentile_of_real"]
    sharpe = metrics["sharpe"]
    if np.isnan(p) or hit["n"] < 30:
        return "Too few holdout signals to draw a statistical conclusion — needs more history or looser thresholds."
    significant = p < 0.05 and hit["hit_rate"] > 0.5
    beats_random = pct > 0.90
    if significant and beats_random and sharpe > 0:
        return ("Directional accuracy is statistically distinguishable from chance AND beats the random-direction "
                "baseline, with a positive cost-adjusted Sharpe on unseen data. Promising enough to justify demo "
                "forward-testing — still not sufficient alone for live capital.")
    if significant and not beats_random:
        return ("Hit rate is statistically above chance, but the random-direction baseline (same timing/sizing) "
                "performs comparably — suggests trade *timing* may carry some information but directional calls "
                "don't clearly add value beyond it. Investigate before trusting this.")
    if not significant and beats_random:
        return ("Beat the random-direction baseline, but the hit-rate test isn't statistically significant "
                "(p >= 0.05) — with this few signals that's likely lower average transaction-cost drag from "
                "trading less, not real directional skill. Don't read the baseline percentile alone as an edge.")
    return ("No statistically significant edge over chance on this holdout slice. Matches the project's own "
            "prior finding on synthetic data. Do not trade this configuration live as-is.")


def main():
    global _args
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=["M15", "H1", "D1"], default="H1")
    parser.add_argument("--bars", type=int, default=8000, help="max bars to request from MT5")
    parser.add_argument("--feature-set", choices=list(FEATURE_SETS.keys()), default="baseline")
    parser.add_argument("--out-prefix", default="VALIDATION_REPORT",
                         help="output files: <prefix>_<timeframe>[_<feature-set>].md")
    _args = parser.parse_args()
    _args.out_prefix = _args.out_prefix if _args.feature_set == "baseline" else f"{_args.out_prefix}_{_args.feature_set}"

    report_lines = [
        f"# Validation report — GenomeGAF ({_args.timeframe}, {_args.feature_set} feature set)\n\n",
        f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}. "
        f"Timeframe: {_args.timeframe}. Feature set: {_args.feature_set} "
        f"({FEATURE_SETS[_args.feature_set] or 'library defaults'}). Bar budget: {_args.bars}. "
        f"Development/holdout split: {int(DEV_FRAC*100)}/{int((1-DEV_FRAC)*100)}. "
        f"Walk-forward CV folds: {CV_FOLDS}. Monte Carlo sims: {MC_SIMS}.\n\n",
        "**Methodology:** for each instrument, the first "
        f"{int(DEV_FRAC*100)}% of history is a development slice used only to pick pipeline parameters via "
        f"walk-forward cross-validation (pattern DB trained on progressively larger prefixes, tested on the "
        "next held-out chunk, DB frozen during each test chunk). The chosen parameters are then evaluated "
        "exactly once on the final holdout slice, which neither the parameter search nor the pattern DB has "
        "ever seen. All P&L figures include a real, broker-quoted round-turn transaction cost and lag every "
        "position decision by one bar (no same-bar look-ahead). Statistical significance is assessed two ways: "
        "a binomial test on directional hit rate, and a Monte Carlo comparison against a random-direction "
        "baseline with identical trade timing and sizing.\n",
    ]

    results = []
    for kw in INSTRUMENTS:
        try:
            results.append(run_one(kw, report_lines))
        except Exception as e:
            print(f"FAILED on {kw}: {e}", file=sys.stderr)
            traceback.print_exc()
            report_lines.append(f"\n## {kw}\n\nFAILED: {e}\n")

    report_lines.append("\n## Summary\n\n")
    report_lines.append("| Instrument | Holdout Sharpe | Hit rate (p-value) | Beats random baseline? | Verdict |\n")
    report_lines.append("|---|---|---|---|---|\n")
    for r in results:
        beats = "yes" if r["mc"]["percentile_of_real"] > 0.90 else "no"
        report_lines.append(
            f"| {r['keyword']} | {fmt(r['metrics']['sharpe'])} | "
            f"{fmt_pct(r['hit']['hit_rate'])} (p={fmt(r['hit']['p_value'], 4)}) | {beats} | "
            f"{interpret(r['metrics'], r['hit'], r['mc'])[:80]}... |\n"
        )

    report_lines.append(
        "\n## Honest caveats — read before trading any of this\n\n"
        "- This is one holdout slice per instrument, not multiple independent out-of-sample periods across "
        "different market regimes. A single passing result is encouraging, not proof.\n"
        "- Transaction costs used are current spread snapshots (or fallback assumptions where MT5 reported a "
        "stale/zero spread) — they don't model slippage, widened spreads during news/volatility, or commission.\n"
        "- Position sizing (3x confidence, clipped to [-1,1]) is illustrative, not risk-managed. There is no "
        "stop-loss, max-drawdown circuit breaker, or correlation-aware sizing across instruments here.\n"
        "- No instrument here was tested through a genuinely different regime (e.g. a volatility shock or trend "
        "reversal) unless one happened to fall in its holdout window by chance.\n"
        "- Signals-only mode is what's implemented — nothing in this repository places live orders.\n"
    )

    report_path = f"{_args.out_prefix}_{_args.timeframe}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.writelines(report_lines)
    print(f"\nWrote {report_path}")

    best_configs = {
        r["keyword"]: {
            "window": r["best_cfg"].window, "atr_period": r["best_cfg"].atr_period,
            "horizon": r["best_cfg"].horizon, "method": r["best_cfg"].method,
            "similarity_threshold": r["best_cfg"].similarity_threshold,
            "min_matches": r["best_cfg"].min_matches, "max_db_size": r["best_cfg"].max_db_size,
            "holdout_sharpe": r["metrics"]["sharpe"], "hit_rate": r["hit"]["hit_rate"],
            "hit_rate_p_value": r["hit"]["p_value"],
            "beats_random_baseline": r["mc"]["percentile_of_real"] > 0.90,
        }
        for r in results
    }
    config_path = f"best_configs_{_args.timeframe}.json" if _args.feature_set == "baseline" \
        else f"best_configs_{_args.feature_set}_{_args.timeframe}.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(best_configs, f, indent=2, default=lambda x: None if isinstance(x, float) and np.isnan(x) else x)
    print(f"Wrote {config_path} (consumed by live_signal.py)")


if __name__ == "__main__":
    main()
