"""
demo.py
End-to-end smoke test + simple backtest on synthetic OHLC data (no
external data feed needed to validate the pipeline). Swap `make_synthetic_data`
for a real CSV loader (MT5 export, etc.) once you're ready to test on
real instruments.
"""

import argparse

import numpy as np
import matplotlib.pyplot as plt

from gaf_core import normalize_series, generate_gaf
from gaf_indicator import GAFIndicator, GAFIndicatorConfig
from data_loader import load_ohlc_csv


def make_synthetic_data(n=3000, seed=7):
    """
    Synthetic price series with injected repeating 'fractal' motifs so we
    can sanity-check that the matcher actually finds structurally similar
    patterns at different volatility scales — this is NOT meant to
    resemble real market statistics, just to exercise the pipeline.
    """
    rng = np.random.default_rng(seed)
    close = np.zeros(n)
    close[0] = 100.0

    motif = np.array([0.004, -0.001, 0.006, -0.003, 0.005, -0.002, 0.003, -0.004, 0.002, 0.001])

    i = 1
    while i < n:
        if rng.random() < 0.08 and i + len(motif) < n:
            scale = rng.uniform(0.5, 2.0)  # different volatility regime, same shape
            for step in motif:
                close[i] = close[i - 1] * (1 + step * scale)
                i += 1
        else:
            close[i] = close[i - 1] * (1 + rng.normal(0, 0.003))
            i += 1

    noise = rng.normal(0, 0.0008, n)
    high = close * (1 + np.abs(noise) + 0.0005)
    low = close * (1 - np.abs(noise) - 0.0005)
    return high, low, close


def run_backtest(high=None, low=None, close=None):
    if close is None:
        high, low, close = make_synthetic_data()

    cfg = GAFIndicatorConfig(window=10, atr_period=14, horizon=5,
                              similarity_threshold=0.90, min_matches=5)
    ind = GAFIndicator(cfg)

    signals, confidences, directions = [], [], []
    equity = [1.0]
    position = 0.0

    for i in range(len(close)):
        sig = ind.on_bar(i, high[i], low[i], close[i])
        if sig is not None:
            signals.append(sig)
            confidences.append(sig.confidence)
            directions.append(sig.direction)
            position = np.clip(sig.direction * 3, -1, 1)  # simple sizing
        else:
            confidences.append(0.0)
            directions.append(0.0)

        if i > 0:
            bar_ret = (close[i] - close[i - 1]) / close[i - 1]
            equity.append(equity[-1] * (1 + position * bar_ret))

    print(f"Total bars: {len(close)}")
    print(f"Bars with a live signal: {sum(1 for s in signals)}")
    non_zero = [s for s in signals if s.n_matches >= cfg.min_matches]
    print(f"Bars with usable matches (>= {cfg.min_matches}): {len(non_zero)}")
    if non_zero:
        avg_conf = np.mean([s.confidence for s in non_zero])
        avg_matches = np.mean([s.n_matches for s in non_zero])
        print(f"Avg confidence on active signals: {avg_conf:.3f}")
        print(f"Avg match count on active signals: {avg_matches:.1f}")
    print(f"Final equity (toy sizing, no costs): {equity[-1]:.4f}")

    return high, low, close, directions, confidences, equity


def plot_results(high, low, close, directions, confidences, equity):
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)

    axes[0].plot(close, color="#2563eb", linewidth=1)
    axes[0].set_title("Synthetic price series")
    axes[0].set_ylabel("Price")

    axes[1].plot(directions, color="#16a34a", linewidth=1)
    axes[1].axhline(0, color="gray", linewidth=0.5)
    axes[1].set_title("Signal direction (confidence-weighted)")
    axes[1].set_ylabel("Direction")

    axes[2].plot(equity, color="#dc2626", linewidth=1)
    axes[2].set_title("Toy equity curve (illustrative only — no costs, slippage, or risk mgmt)")
    axes[2].set_ylabel("Equity")
    axes[2].set_xlabel("Bar index")

    plt.tight_layout()
    plt.savefig("backtest_overview.png", dpi=130)
    print("Saved backtest_overview.png")


def plot_gaf_example():
    high, low, close = make_synthetic_data(n=200, seed=3)
    x = normalize_series(close, high, low, atr_period=14)
    window = x[50:70]
    window = np.nan_to_num(window, nan=0.0)
    M = generate_gaf(window, method="gasf")

    fig, ax = plt.subplots(figsize=(5, 5))
    im = ax.imshow(M, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_title("GASF matrix — one 20-bar fingerprint")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig("gaf_example.png", dpi=130)
    print("Saved gaf_example.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", help="Path to a real OHLC CSV export (needs high/low/close columns). "
                                       "Omit to use synthetic data.")
    args = parser.parse_args()

    if args.csv:
        high, low, close = load_ohlc_csv(args.csv)
        high, low, close, directions, confidences, equity = run_backtest(high, low, close)
    else:
        high, low, close, directions, confidences, equity = run_backtest()

    plot_results(high, low, close, directions, confidences, equity)
    plot_gaf_example()
