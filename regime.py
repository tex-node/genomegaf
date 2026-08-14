"""
regime.py
Regime tagging so the pattern database can be queried within-regime
rather than across all history indiscriminately.

Deliberately simple for a prototype: trend direction (up/down/flat) x
volatility percentile (low/mid/high) = 9 discrete regimes. An HMM-based
regime detector is a reasonable upgrade later, but it's a separate model
to fit, validate, and maintain — not justified until the simple version
is shown to matter empirically.
"""

import numpy as np
import pandas as pd

from gaf_core import atr as _atr


def compute_regime_labels(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                           trend_lookback: int = 50, vol_lookback: int = 100,
                           flat_band: float = 0.15) -> np.ndarray:
    """
    Returns an int array the same length as `close`, values 0-8
    (trend in {0=down,1=flat,2=up}) * 3 + (vol in {0=low,1=mid,2=high}),
    or -1 where there isn't enough history yet.

    trend: sign of the `trend_lookback`-bar price change, ATR-normalized,
    with a dead-band (`flat_band`) to avoid noisy flat markets being
    labeled as trending by accident.

    vol: percentile rank of the current ATR within the trailing
    `vol_lookback` window, bucketed into low/mid/high thirds.
    """
    close = np.asarray(close, dtype=float)
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n = len(close)

    atr_vals = _atr(high, low, close, period=14)

    trend_state = np.full(n, -1, dtype=int)
    price_change = np.full(n, np.nan)
    price_change[trend_lookback:] = close[trend_lookback:] - close[:-trend_lookback]
    with np.errstate(invalid="ignore"):
        normalized_change = price_change / (atr_vals * np.sqrt(trend_lookback))

    up = normalized_change > flat_band
    down = normalized_change < -flat_band
    flat = ~up & ~down & ~np.isnan(normalized_change)
    trend_state[up] = 2
    trend_state[flat] = 1
    trend_state[down] = 0

    vol_rank = (
        pd.Series(atr_vals)
        .rolling(window=vol_lookback, min_periods=vol_lookback)
        .rank(pct=True)
        .to_numpy()
    )
    vol_state = np.full(n, -1, dtype=int)
    valid_vol = ~np.isnan(vol_rank)
    vol_state[valid_vol] = np.digitize(vol_rank[valid_vol], bins=[1 / 3, 2 / 3])  # 0,1,2

    regime = np.full(n, -1, dtype=int)
    valid = (trend_state >= 0) & (vol_state >= 0)
    regime[valid] = trend_state[valid] * 3 + vol_state[valid]
    return regime


REGIME_NAMES = {
    0: "down_lowvol", 1: "down_midvol", 2: "down_highvol",
    3: "flat_lowvol", 4: "flat_midvol", 5: "flat_highvol",
    6: "up_lowvol", 7: "up_midvol", 8: "up_highvol",
    -1: "warmup",
}
