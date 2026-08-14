"""
multi_source_pattern_db.py
Cross-instrument, cross-timeframe pattern database: pools normalized GAF
fingerprints from many (instrument, timeframe) source streams into one
shared pool, matched purely on shape/directionality -- not filtered by
source instrument or timeframe. Tests the hypothesis that a price-shape's
forward outcome might generalize across markets and timescales, rather
than being specific to one instrument's own history (which is all
pattern_db.PatternDB and everything in VALIDATION_REPORT*.md tests).

Why this needs different bookkeeping than pattern_db.PatternDB: that
class resolves a match's forward return by indexing close[bar_index +
horizon] in the CALLING stream's own price array, and gates "is this
match's outcome known yet" by comparing bar indices on a single shared
timeline. Neither holds once fingerprints come from different streams --
bar_index means something different in every source. This module instead
precomputes each record's forward return AT INGESTION TIME (we have the
full historical array available upfront, so there's no need to defer
that lookup), and stores a real UNIX timestamp so "has this record's
outcome actually happened as of query time" is a genuine calendar
comparison, valid across sources of any timeframe.

Point-in-time discipline: to build a genuinely leak-free shared database,
every source must be split at the SAME calendar cutoff, not each source's
own fraction -- a record from instrument B added to the DB before cutoff
T is legitimate training data regardless of instrument, because "now"
(T) is a single moment shared by every market in this pooled world. See
run_cross_market_validation.py for how that cutoff is chosen and applied.

window (bar count) must be identical across every pooled source, since
fingerprint length depends on it -- this is intentional, not a
limitation: comparing a 10-bar shape from M5 against a 10-bar shape from
D1 *is* the cross-scale hypothesis being tested (a 10-bar shape means
50 minutes on M5 and 10 days on D1; whether that self-similar-regardless-
of-scale comparison carries real information is exactly the open
question).
"""

from dataclasses import dataclass, field

import numpy as np

from gaf_core import rank_normalize_series, normalize_series, build_fingerprint


@dataclass
class SourceMeta:
    source_id: int
    instrument: str
    timeframe: str
    n_ingested: int = 0


@dataclass
class MultiSourceDB:
    fingerprint_len: int
    max_size: int = 700_000
    fingerprints: np.ndarray = field(init=False, repr=False)
    forward_returns: np.ndarray = field(init=False, repr=False)
    source_ids: np.ndarray = field(init=False, repr=False)
    timestamps: np.ndarray = field(init=False, repr=False)
    resolution_ts: np.ndarray = field(init=False, repr=False)
    source_ranges: dict = field(default_factory=dict, init=False)  # source_id -> (start, end)
    _count: int = field(default=0, init=False)

    def __post_init__(self):
        self.fingerprints = np.zeros((self.max_size, self.fingerprint_len), dtype=np.float32)
        self.forward_returns = np.zeros(self.max_size, dtype=np.float64)
        self.source_ids = np.zeros(self.max_size, dtype=np.int32)
        self.timestamps = np.zeros(self.max_size, dtype=np.int64)
        self.resolution_ts = np.zeros(self.max_size, dtype=np.int64)

    def __len__(self):
        return min(self._count, self.max_size)

    def add_batch(self, fingerprints: np.ndarray, forward_returns: np.ndarray,
                  source_id: int, timestamps: np.ndarray, resolution_ts: np.ndarray):
        """Bulk-add (used by ingest_source below). Overwrites oldest slots
        ring-buffer style if max_size is exceeded, same discipline as
        pattern_db.PatternDB. Records a contiguous (start, end) range per
        source_id (true as long as max_size is never exceeded across the
        whole ingestion run, which the caller sizes for) so query() can
        slice a single source directly instead of scanning + masking the
        whole pool for same-source-only queries."""
        n = len(forward_returns)
        norms = np.linalg.norm(fingerprints, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        unit_fps = (fingerprints / norms).astype(np.float32)

        start = self._count
        end = start + n
        if end <= self.max_size:
            self.fingerprints[start:end] = unit_fps
            self.forward_returns[start:end] = forward_returns
            self.source_ids[start:end] = source_id
            self.timestamps[start:end] = timestamps
            self.resolution_ts[start:end] = resolution_ts
            self.source_ranges[source_id] = (start, end)
            self._count = end
        else:
            # wraparound path: rare (only if total ingestion exceeds max_size)
            # -- falls back to per-row writes and gives up contiguous-range
            # slicing for this source since it may now span the wrap point.
            self.source_ranges.pop(source_id, None)
            for i in range(n):
                slot = self._count % self.max_size
                self.fingerprints[slot] = unit_fps[i]
                self.forward_returns[slot] = forward_returns[i]
                self.source_ids[slot] = source_id
                self.timestamps[slot] = timestamps[i]
                self.resolution_ts[slot] = resolution_ts[i]
                self._count += 1

    def query(self, live_fingerprint: np.ndarray, query_ts: int, threshold: float,
              top_k: int = None, only_source_id: int = None):
        """
        Returns list of (forward_return, similarity, source_id), sorted by
        similarity desc, restricted to records whose outcome had actually
        resolved as of query_ts (defensive -- true by construction once
        the DB is frozen and queried only during a later holdout period,
        but real gating for the boundary case of the earliest holdout
        queries).

        only_source_id: pass to restrict to a single source (the
        same-instrument-only control comparison) -- None searches the
        whole pool. When a contiguous range is known for that source
        (the common case), only that slice is ever touched, so a control
        query costs proportional to one source's size, not the whole pool.
        """
        norm = np.linalg.norm(live_fingerprint)
        live_unit = (live_fingerprint / norm if norm > 0 else live_fingerprint).astype(np.float32)

        if only_source_id is not None and only_source_id in self.source_ranges:
            start, end = self.source_ranges[only_source_id]
            fps_view = self.fingerprints[start:end]
            fr_view = self.forward_returns[start:end]
            rts_view = self.resolution_ts[start:end]
            src_view = self.source_ids[start:end]
        else:
            n = len(self)
            if n == 0:
                return []
            fps_view = self.fingerprints[:n]
            fr_view = self.forward_returns[:n]
            rts_view = self.resolution_ts[:n]
            src_view = self.source_ids[:n]

        sims = fps_view @ live_unit  # single BLAS matvec over a view, no copy
        mask = sims >= threshold
        mask &= rts_view <= query_ts
        if only_source_id is not None and src_view is not None and only_source_id not in self.source_ranges:
            mask &= (src_view == only_source_id)
        if not mask.any():
            return []

        idx = np.nonzero(mask)[0]
        order = idx[np.argsort(-sims[idx])]
        if top_k is not None:
            order = order[:top_k]

        return list(zip(fr_view[order].tolist(), sims[order].tolist(), src_view[order].tolist()))


def ingest_source(db: MultiSourceDB, source_id: int, high, low, close, timestamps,
                   window: int, horizon: int, atr_period: int = 14,
                   normalization: str = "rank", rank_lookback: int = 252,
                   method: str = "gasf", cutoff_ts: int = None):
    """
    Vectorized batch ingestion of one (instrument, timeframe) source's full
    history into the shared DB. Only bars whose own timestamp is strictly
    before cutoff_ts are added (the point-in-time discipline) -- their
    forward return may use price data at or slightly after cutoff_ts (the
    outcome of a dev-period pattern resolving a few bars later is still
    legitimate training information, same principle as this project's
    single-instrument walk-forward split).

    Returns the number of fingerprints added.
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    timestamps = np.asarray(timestamps, dtype=np.int64)
    n = len(close)

    if normalization == "rank":
        x = rank_normalize_series(close, lookback=rank_lookback)
    else:
        x = normalize_series(close, high, low, atr_period=atr_period)

    added = 0
    fps, frs, tss, rts = [], [], [], []
    for i in range(window - 1, n - horizon):
        t = timestamps[i]
        if cutoff_ts is not None and t >= cutoff_ts:
            break  # timestamps are increasing; nothing later qualifies either
        win = x[i - window + 1: i + 1]
        if np.isnan(win).any():
            continue
        fp = build_fingerprint(win, method=method)
        fr = (close[i + horizon] - close[i]) / close[i]
        fps.append(fp)
        frs.append(fr)
        tss.append(t)
        rts.append(timestamps[i + horizon])

    if fps:
        db.add_batch(np.array(fps, dtype=np.float32), np.array(frs, dtype=np.float64),
                     source_id, np.array(tss, dtype=np.int64), np.array(rts, dtype=np.int64))
        added = len(fps)
    return added


def normalize_target_series(high, low, close, atr_period: int = 14,
                             normalization: str = "rank", rank_lookback: int = 252):
    """
    Precompute the full normalized series ONCE for a target (evaluation)
    instrument, so per-bar fingerprint lookups are O(window) slices
    instead of re-running a rolling-rank/ATR calc over growing history on
    every query bar (which would make evaluation O(n^2) again).
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    if normalization == "rank":
        return rank_normalize_series(close, lookback=rank_lookback)
    return normalize_series(close, high, low, atr_period=atr_period)


def live_fingerprint_at(x: np.ndarray, i: int, window: int, method: str = "gasf"):
    """
    Build the fingerprint for query bar i from a precomputed normalized
    series x (see normalize_target_series). Returns None if there isn't
    enough history yet. Does NOT need horizon bars of future data (unlike
    ingestion) since we're not resolving this bar's own outcome here --
    that's what the DB match's stored forward_return is for.
    """
    if i < window - 1:
        return None
    win = x[i - window + 1: i + 1]
    if np.isnan(win).any():
        return None
    return build_fingerprint(win, method=method)
