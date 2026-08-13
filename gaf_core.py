"""
gaf_core.py
Core signal-processing primitives for the GAF pattern-recognition engine:
  1. Volatility-normalized log returns (the "Vibration" step)
  2. Gramian Angular Field encoding (GASF / GADF)
  3. Fingerprint extraction (flattened upper triangle)

All functions are pure numpy and vectorized so they map cleanly onto
MQL5 arrays later (no hidden Python-only tricks like pandas rolling
apply with lambdas).
"""

import numpy as np


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Classic Wilder ATR, vectorized. Returns an array the same length as
    input, with the first `period` values as NaN (not enough data yet).
    """
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    prev_close = close[:-1]
    tr[1:] = np.maximum(
        high[1:] - low[1:],
        np.maximum(np.abs(high[1:] - prev_close), np.abs(low[1:] - prev_close)),
    )

    atr_vals = np.full(n, np.nan)
    if n < period:
        return atr_vals

    atr_vals[period - 1] = tr[:period].mean()
    for i in range(period, n):
        atr_vals[i] = (atr_vals[i - 1] * (period - 1) + tr[i]) / period
    return atr_vals


def normalize_series(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                      atr_period: int = 14) -> np.ndarray:
    """
    Step 1 — Pre-Processing & Normalization.

    x_t = ln(P_t / P_t-1) / ATR_t

    Returns an array the same length as `close`; leading values that
    depend on an unavailable ATR are NaN.
    """
    close = np.asarray(close, dtype=float)
    log_ret = np.empty_like(close)
    log_ret[0] = np.nan
    log_ret[1:] = np.log(close[1:] / close[:-1])

    atr_vals = atr(high, low, close, atr_period)
    with np.errstate(divide="ignore", invalid="ignore"):
        x = log_ret / atr_vals
    return x


def _rescale(x: np.ndarray, k: float = 1.0, mode: str = "minmax") -> np.ndarray:
    """
    Rescale the window into [-1, 1] before taking arccos.

    mode='minmax' (default, standard GAF practice): rescale THIS window's
    own min/max to [-1, 1]. This is what actually delivers the
    volatility-independence property — a window is compared to itself,
    so a calm-regime window and a volatile-regime window with the same
    *shape* land on the same matrix regardless of their absolute scale.
    A fixed multiplicative constant (mode='fixed') can't do this: ATR-
    normalized returns are typically ~0.01 in magnitude, so a fixed k
    either clips almost everything to +-1 (k too large) or collapses
    everything into a narrow band near arccos(0) (k too small) — in
    both cases every window looks alike and matching breaks silently.
    """
    x = np.asarray(x, dtype=float)
    if mode == "fixed":
        return np.clip(x * k, -1.0, 1.0)

    xmin, xmax = x.min(), x.max()
    rng = xmax - xmin
    if rng < 1e-12:
        return np.zeros_like(x)  # flat window (no movement) -> neutral angle
    return 2.0 * (x - xmin) / rng - 1.0


def generate_gaf(window: np.ndarray, method: str = "gasf", k: float = 1.0,
                  rescale_mode: str = "minmax") -> np.ndarray:
    """
    Step 2 — Gramian Angular Field encoding.

    window: 1D array of length N (already normalized, may contain no NaNs)
    method: 'gasf' (summation, cos(phi_i + phi_j)) or
            'gadf' (difference, sin(phi_i - phi_j))
    rescale_mode: 'minmax' (recommended, self-calibrating per window) or
                  'fixed' (uses k as a literal multiplier — mainly kept
                  for parity with the original blueprint's formula).

    Returns an N x N matrix.
    """
    x = _rescale(np.asarray(window, dtype=float), k=k, mode=rescale_mode)
    phi = np.arccos(x)  # angle per time step

    if method == "gasf":
        M = np.cos(phi[:, None] + phi[None, :])
    elif method == "gadf":
        M = np.sin(phi[:, None] - phi[None, :])
    else:
        raise ValueError("method must be 'gasf' or 'gadf'")
    return M


def extract_fingerprint(matrix: np.ndarray) -> np.ndarray:
    """
    Step 3 (part 1) — Flatten the upper triangle (excluding diagonal,
    since GASF's diagonal is just the original series and GADF's
    diagonal is always zero — neither adds discriminative info beyond
    what's already in the off-diagonal terms).

    Returns a 1D vector of length N*(N-1)/2.
    """
    n = matrix.shape[0]
    iu = np.triu_indices(n, k=1)
    return matrix[iu]


def build_fingerprint(window: np.ndarray, method: str = "gasf", k: float = 1.0,
                       rescale_mode: str = "minmax") -> np.ndarray:
    """Convenience: normalized window -> GAF matrix -> flattened fingerprint."""
    M = generate_gaf(window, method=method, k=k, rescale_mode=rescale_mode)
    return extract_fingerprint(M)
