"""
validation.py
Rigorous validation for the GAF indicator, addressing exactly the gaps the
project's own README flags as missing before trusting real signals:

  1. Walk-forward split — pattern DB trained ONLY on a past period, tested
     on a strictly later, unseen period (no online re-training during test).
  2. Transaction costs — real broker spread applied on every position change.
  3. Statistical significance — is directional accuracy distinguishable
     from chance, and does the result beat a random-direction baseline
     with the same trade timing?
  4. Parameter sensitivity — grid search selected via cross-validation on
     a development slice, evaluated ONCE on an untouched final holdout
     slice, so the reported result isn't itself overfit to the test data.

Also fixes a same-bar look-ahead bug in the toy P&L simulation found while
building this: applying a bar's own signal to that same bar's
already-realized return. Positions here are always lagged one bar.
"""

import math
import time
from dataclasses import dataclass, field
from itertools import product

import numpy as np

from gaf_indicator import GAFIndicator, GAFIndicatorConfig


# ---------------------------------------------------------------- P&L engine

def apply_positions(directions: np.ndarray, has_signal: np.ndarray, close: np.ndarray,
                     cost_frac: float = 0.0, size_mult: float = 3.0) -> np.ndarray:
    """Turn a per-bar direction stream into an equity curve. Position decided
    at bar i (from information through bar i) is applied to bar i+1's
    return, never to bar i's own already-known return. `cost_frac` is a
    round-turn transaction cost as a fraction of price, charged on the bar
    a position change is decided."""
    n = len(close)
    equity = np.empty(n)
    equity[0] = 1.0
    position = 0.0
    for i in range(1, n):
        bar_ret = (close[i] - close[i - 1]) / close[i - 1]
        equity[i] = equity[i - 1] * (1 + position * bar_ret)
        new_position = np.clip(directions[i] * size_mult, -1, 1) if has_signal[i] else position
        if cost_frac > 0 and new_position != position:
            equity[i] *= (1 - cost_frac * abs(new_position - position))
        position = new_position
    return equity


# ------------------------------------------------------------------- engine

@dataclass
class RunResult:
    equity: np.ndarray
    directions: np.ndarray
    confidences: np.ndarray
    n_matches: np.ndarray
    has_signal: np.ndarray
    raw_returns: list = field(default_factory=list)  # per-bar list of sig.raw_returns (or None)


def run_pipeline(high, low, close, cfg: GAFIndicatorConfig, train_end_idx: int = None,
                  cost_frac: float = 0.0, size_mult: float = 3.0) -> RunResult:
    """Run the GAF pipeline once. If train_end_idx is given, the pattern DB
    stops learning at that index (walk-forward test mode); otherwise it
    learns continuously (online mode, matches the original demo.py)."""
    n = len(close)
    ind = GAFIndicator(cfg)
    directions = np.zeros(n)
    confidences = np.zeros(n)
    n_matches = np.zeros(n, dtype=int)
    has_signal = np.zeros(n, dtype=bool)
    raw_returns = [None] * n

    for i in range(n):
        learn = True if train_end_idx is None else (i < train_end_idx)
        sig = ind.on_bar(i, high[i], low[i], close[i], learn=learn)
        if sig is not None:
            has_signal[i] = True
            directions[i] = sig.direction
            confidences[i] = sig.confidence
            n_matches[i] = sig.n_matches
            raw_returns[i] = sig.raw_returns

    equity = apply_positions(directions, has_signal, close, cost_frac=cost_frac, size_mult=size_mult)
    return RunResult(equity, directions, confidences, n_matches, has_signal, raw_returns)


# ----------------------------------------------------------------- metrics

def compute_metrics(equity: np.ndarray, timestamps: np.ndarray) -> dict:
    equity = np.asarray(equity, dtype=float)
    returns = np.diff(equity) / equity[:-1]
    elapsed_years = max((timestamps[-1] - timestamps[0]) / (365.25 * 24 * 3600), 1e-9)
    bars_per_year = (len(equity) - 1) / elapsed_years

    total_return = equity[-1] / equity[0] - 1
    cagr = (equity[-1] / equity[0]) ** (1 / elapsed_years) - 1

    std = returns.std(ddof=1) if len(returns) > 1 else 0.0
    sharpe = (returns.mean() / std * math.sqrt(bars_per_year)) if std > 0 else float("nan")

    downside = returns[returns < 0]
    dstd = downside.std(ddof=1) if len(downside) > 1 else 0.0
    sortino = (returns.mean() / dstd * math.sqrt(bars_per_year)) if dstd > 0 else float("nan")

    running_max = np.maximum.accumulate(equity)
    max_dd = (equity / running_max - 1).min()

    gains = returns[returns > 0].sum()
    losses = -returns[returns < 0].sum()
    profit_factor = (gains / losses) if losses > 0 else float("inf")

    active = returns[returns != 0]
    win_rate = (active > 0).mean() if len(active) else float("nan")

    return {
        "total_return": total_return, "cagr": cagr, "sharpe": sharpe, "sortino": sortino,
        "max_drawdown": max_dd, "profit_factor": profit_factor, "win_rate": win_rate,
        "n_bars": len(equity), "elapsed_years": elapsed_years,
    }


# ------------------------------------------------------- statistical tests

def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def hit_rate_test(directions: np.ndarray, close: np.ndarray, horizon: int) -> dict:
    """Binomial test: among bars with a non-zero directional call, does the
    predicted sign match the sign of the actual forward return more often
    than 50/50 chance?"""
    n = len(close)
    idx = np.where(directions != 0)[0]
    idx = idx[idx + horizon < n]
    if len(idx) == 0:
        return {"n": 0, "hit_rate": float("nan"), "z": float("nan"), "p_value": float("nan")}

    realized = (close[idx + horizon] - close[idx]) / close[idx]
    pred_sign = np.sign(directions[idx])
    actual_sign = np.sign(realized)
    valid = actual_sign != 0
    n_valid = int(valid.sum())
    if n_valid == 0:
        return {"n": 0, "hit_rate": float("nan"), "z": float("nan"), "p_value": float("nan")}

    hits = int((pred_sign[valid] == actual_sign[valid]).sum())
    hit_rate = hits / n_valid
    z = (hits - n_valid * 0.5) / math.sqrt(n_valid * 0.25)
    p_value = 2 * (1 - _norm_cdf(abs(z)))
    return {"n": n_valid, "hit_rate": hit_rate, "z": z, "p_value": p_value}


def random_direction_baseline(directions: np.ndarray, has_signal: np.ndarray, close: np.ndarray,
                               cost_frac: float, size_mult: float = 3.0,
                               n_sims: int = 2000, seed: int = 0) -> dict:
    """Null baseline: same bars, same trade frequency, same position
    magnitude — but the DIRECTION is randomized. If the real strategy's
    result isn't well outside this distribution, its edge (if any) isn't
    coming from calling direction correctly."""
    rng = np.random.default_rng(seed)
    active_idx = np.where(has_signal & (directions != 0))[0]
    magnitudes = np.abs(directions[active_idx])
    real_equity = apply_positions(directions, has_signal, close, cost_frac, size_mult)
    real_final = real_equity[-1]

    sims = np.empty(n_sims)
    for s in range(n_sims):
        rand_signs = rng.choice(np.array([-1.0, 1.0]), size=len(active_idx))
        sim_directions = np.zeros(len(close))
        sim_directions[active_idx] = rand_signs * magnitudes
        eq = apply_positions(sim_directions, has_signal, close, cost_frac, size_mult)
        sims[s] = eq[-1]

    percentile = float((sims < real_final).mean())
    return {
        "real_final_equity": float(real_final), "n_sims": n_sims,
        "null_mean": float(sims.mean()), "null_std": float(sims.std()),
        "percentile_of_real": percentile,
    }


# --------------------------------------------------- walk-forward / grid CV

def walk_forward_folds(n_dev: int, k: int):
    test_len = n_dev // (k + 1)
    folds = []
    for j in range(1, k + 1):
        train_end = j * test_len
        test_end = min((j + 1) * test_len, n_dev)
        folds.append((0, train_end, train_end, test_end))
    return folds


def select_best_config(high, low, close, dev_end: int, param_grid: list, k: int,
                        cost_frac: float, verbose: bool = True) -> tuple:
    """Cross-validate each config on rolling walk-forward folds within the
    development slice ([0:dev_end)), score by mean test-fold Sharpe. Never
    touches data beyond dev_end."""
    folds = walk_forward_folds(dev_end, k)
    scores = []
    for cfg in param_grid:
        fold_sharpes = []
        t0 = time.time()
        for (tr_s, tr_e, te_s, te_e) in folds:
            h, l, c = high[tr_s:te_e], low[tr_s:te_e], close[tr_s:te_e]
            train_end_local = tr_e - tr_s
            result = run_pipeline(h, l, c, cfg, train_end_idx=train_end_local, cost_frac=cost_frac)
            test_equity = result.equity[train_end_local:]
            if len(test_equity) < 3:
                continue
            test_returns = np.diff(test_equity) / test_equity[:-1]
            std = test_returns.std(ddof=1) if len(test_returns) > 1 else 0.0
            sharpe = (test_returns.mean() / std) if std > 0 else 0.0
            fold_sharpes.append(sharpe)
        mean_sharpe = float(np.mean(fold_sharpes)) if fold_sharpes else float("-inf")
        scores.append((mean_sharpe, cfg))
        if verbose:
            print(f"    window={cfg.window:2d} horizon={cfg.horizon:2d} thresh={cfg.similarity_threshold:.2f} "
                  f"-> mean fold Sharpe {mean_sharpe:+.3f}  ({time.time()-t0:.1f}s)")
    scores.sort(key=lambda x: x[0], reverse=True)
    return scores[0][1], scores


def default_param_grid(base: GAFIndicatorConfig) -> list:
    grid = []
    for window, horizon, threshold in product([10, 15, 20], [5, 10, 20], [0.90, 0.95]):
        cfg = GAFIndicatorConfig(
            window=window, atr_period=base.atr_period, horizon=horizon, method=base.method,
            similarity_threshold=threshold, min_matches=base.min_matches, max_db_size=base.max_db_size,
        )
        grid.append(cfg)
    return grid
