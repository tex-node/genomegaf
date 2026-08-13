"""
projection.py
Step 5 — Projection & Statistical Inference.

Given a set of matched historical bar indices, look up what price did
`horizon` bars later, build the distribution of forward returns, and
turn it into a single actionable signal (direction, confidence, count).
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class Signal:
    direction: float        # -1..+1, sign = bearish/bullish, magnitude unused for now
    mean_return: float
    std_return: float
    n_matches: int
    confidence: float       # 0..1, higher = tighter agreement among matches
    raw_returns: np.ndarray


def project(matches, closes: np.ndarray, horizon: int, min_matches: int = 5) -> Signal:
    """
    matches: list of (bar_index, similarity, close_at_match) from PatternDB.query
    closes:  full historical close array (indexable by bar_index + horizon)
    """
    returns = []
    for bar_index, _sim, close_at_match in matches:
        target_idx = bar_index + horizon
        if target_idx >= len(closes):
            continue  # outcome not actually available yet, skip
        r = (closes[target_idx] - close_at_match) / close_at_match
        returns.append(r)

    if len(returns) < min_matches:
        return Signal(0.0, 0.0, 0.0, len(returns), 0.0, np.array(returns))

    returns = np.array(returns)
    mean_r = returns.mean()
    std_r = returns.std()

    # Confidence: signal-to-noise ratio of the return distribution,
    # squashed into [0,1] with a smooth saturating function, scaled by
    # sample size (more matches = more statistical trust).
    snr = abs(mean_r) / (std_r + 1e-9)
    snr_component = snr / (snr + 1.0)          # 0..1, saturates smoothly
    size_component = min(len(returns) / 30.0, 1.0)  # saturates at 30 matches
    confidence = snr_component * size_component

    direction = np.sign(mean_r) * confidence

    return Signal(
        direction=float(direction),
        mean_return=float(mean_r),
        std_return=float(std_r),
        n_matches=len(returns),
        confidence=float(confidence),
        raw_returns=returns,
    )
