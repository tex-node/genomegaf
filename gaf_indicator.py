"""
gaf_indicator.py
The full pipeline as a single stateful indicator you feed bar-by-bar,
exactly the way an MQL5 OnCalculate() loop would.

Usage:
    ind = GAFIndicator(window=20, atr_period=14, horizon=10)
    for i in range(len(bars)):
        signal = ind.on_bar(i, high[i], low[i], close[i])
        # signal is None until enough history has built up
"""

from dataclasses import dataclass
import numpy as np

from gaf_core import normalize_series, build_fingerprint
from pattern_db import PatternDB
from projection import project, Signal


@dataclass
class GAFIndicatorConfig:
    window: int = 20          # N bars per fingerprint ("fractal" length)
    atr_period: int = 14
    horizon: int = 10         # bars ahead to project
    method: str = "gasf"      # or "gadf"
    k: float = 1.0            # GAF rescale constant
    similarity_threshold: float = 0.95
    min_matches: int = 5
    max_db_size: int = 20000


class GAFIndicator:
    """
    Stateful, streaming version — call on_bar() once per new closed bar.
    Internally buffers all history needed for ATR + normalization, so you
    don't need to pre-slice windows yourself.
    """

    def __init__(self, config: GAFIndicatorConfig = None):
        self.cfg = config or GAFIndicatorConfig()
        self.high = []
        self.low = []
        self.close = []
        self._fp_len = self.cfg.window * (self.cfg.window - 1) // 2
        self.db = PatternDB(fingerprint_len=self._fp_len, max_size=self.cfg.max_db_size)
        self._norm_cache = None  # recomputed lazily each bar (see note below)

    def on_bar(self, bar_index: int, high: float, low: float, close: float, learn: bool = True) -> Signal | None:
        """
        learn=False freezes the pattern DB: the bar is still used to update
        the rolling normalization/ATR state (needed for continuity), and
        still queried against whatever's already in the DB, but its
        fingerprint is NOT added. Used for walk-forward validation, where
        a DB trained only on a past period must be evaluated against a
        strictly later, unseen period without leaking test-period patterns
        into the matcher.
        """
        self.high.append(high)
        self.low.append(low)
        self.close.append(close)

        n = len(self.close)
        needed = self.cfg.atr_period + self.cfg.window + 1
        if n < needed:
            return None

        h = np.asarray(self.high)
        l = np.asarray(self.low)
        c = np.asarray(self.close)

        # NOTE on efficiency: recomputing normalize_series() over the full
        # history every bar is O(n) per bar => O(n^2) total. Fine for
        # prototyping / backtests up to ~50k bars. For a live MQL5
        # indicator, port normalize_series to an incremental Wilder-ATR
        # update (O(1) per bar) — see PORTING_NOTES.md.
        x = normalize_series(c, h, l, atr_period=self.cfg.atr_period)

        window = x[-self.cfg.window:]
        if np.isnan(window).any():
            return None

        fp = build_fingerprint(window, method=self.cfg.method, k=self.cfg.k)

        # Query BEFORE adding current bar (can't match against itself)
        matches = self.db.query(
            fp, current_bar=bar_index, horizon=self.cfg.horizon,
            threshold=self.cfg.similarity_threshold,
        )
        signal = project(matches, c, horizon=self.cfg.horizon, min_matches=self.cfg.min_matches)

        if learn:
            self.db.add(fp, bar_index=bar_index, close=close)
        return signal
