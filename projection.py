"""
projection.py
Step 5 — Projection & Statistical Inference.

Given a set of matched historical bar indices, look up what price did
`horizon` bars later, build the distribution of forward returns, and
turn it into a single actionable signal (direction, confidence, count).

Two optional additions:
- Recency-weighted stats: a match from last week can be weighted more
  than one from years ago, via exponential decay. Off by default
  (recency_halflife=None) since a good halflife is instrument/horizon-
  specific, not a safe default to guess.
- Skew of the forward-return distribution: mean/std alone can hide a
  distribution that's actually small-loss-most-of-the-time/big-win-
  occasionally (positive skew) or the more dangerous inverse. Direction
  and confidence don't capture this; skew does.
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
    skew: float              # 0.0 if not enough matches to estimate
    raw_returns: np.ndarray


def _skewness(x: np.ndarray) -> float:
    """Sample skewness (Fisher-Pearson), 0.0 if variance is ~0 or n<3."""
    n = len(x)
    if n < 3:
        return 0.0
    std = x.std()
    if std < 1e-12:
        return 0.0
    m3 = np.mean((x - x.mean()) ** 3)
    return float(m3 / std ** 3)


def project(matches, closes: np.ndarray, horizon: int, min_matches: int = 5,
            current_bar: int = None, recency_halflife: float = None) -> Signal:
    """
    matches: list of (bar_index, similarity, close_at_match) from PatternDB.query
    closes:  full historical close array (indexable by bar_index + horizon)
    current_bar, recency_halflife: if both given, weight each match's
        contribution to mean/std by 0.5 ** ((current_bar - bar_index) / recency_halflife)
        — a match `recency_halflife` bars old counts half as much as a
        fresh one. Leave recency_halflife=None to weight all matches
        equally (the original, simpler behavior).
    """
    returns, weights = [], []
    for bar_index, _sim, close_at_match in matches:
        target_idx = bar_index + horizon
        if target_idx >= len(closes):
            continue  # outcome not actually available yet, skip
        r = (closes[target_idx] - close_at_match) / close_at_match
        returns.append(r)

        if current_bar is not None and recency_halflife:
            age = current_bar - bar_index
            weights.append(0.5 ** (age / recency_halflife))
        else:
            weights.append(1.0)

    if len(returns) < min_matches:
        return Signal(0.0, 0.0, 0.0, len(returns), 0.0, 0.0, np.array(returns))

    returns = np.array(returns)
    weights = np.array(weights)
    weights = weights / weights.sum()

    mean_r = float(np.sum(weights * returns))
    variance = float(np.sum(weights * (returns - mean_r) ** 2))
    std_r = float(np.sqrt(variance))
    skew_r = _skewness(returns)  # unweighted; weighting the 3rd moment gets noisy fast on small n

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
        mean_return=mean_r,
        std_return=std_r,
        n_matches=len(returns),
        confidence=float(confidence),
        skew=skew_r,
        raw_returns=returns,
    )
