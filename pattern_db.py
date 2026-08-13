"""
pattern_db.py
Step 3 (part 2) + Step 4 — Rolling historical database of GAF fingerprints,
and vectorized nearest-neighbor search via cosine similarity.

Design notes:
- Fingerprints are stored L2-normalized, so cosine similarity between the
  live fingerprint and every stored fingerprint reduces to a single
  matrix-vector dot product (fast, and trivially portable to MQL5's
  matrix type in MQL5 build 3000+; a manual dot-product loop works on
  older builds).
- A match is only usable for projection once its forward outcome (h bars
  later) is actually known. `usable_matches()` enforces that so you never
  leak future information into a live signal.
"""

from dataclasses import dataclass, field
import numpy as np


@dataclass
class PatternDB:
    fingerprint_len: int
    max_size: int = 20000          # ring-buffer cap; None = unbounded
    fingerprints: np.ndarray = field(init=False, repr=False)
    bar_indices: np.ndarray = field(init=False, repr=False)
    closes: np.ndarray = field(init=False, repr=False)
    _count: int = field(default=0, init=False)

    def __post_init__(self):
        cap = self.max_size or 100000
        self.fingerprints = np.zeros((cap, self.fingerprint_len), dtype=np.float32)
        self.bar_indices = np.zeros(cap, dtype=np.int64)
        self.closes = np.zeros(cap, dtype=np.float64)

    def __len__(self):
        return self._count

    def add(self, fingerprint: np.ndarray, bar_index: int, close: float):
        """Append one fingerprint record. Overwrites oldest slot when full
        (ring buffer), so memory stays bounded during live trading."""
        norm = np.linalg.norm(fingerprint)
        unit_fp = fingerprint / norm if norm > 0 else fingerprint

        slot = self._count % len(self.fingerprints)
        self.fingerprints[slot] = unit_fp
        self.bar_indices[slot] = bar_index
        self.closes[slot] = close
        self._count += 1

    def _active_view(self):
        """Return the populated slice of the ring buffer, oldest-first."""
        n = min(self._count, len(self.fingerprints))
        if self._count <= len(self.fingerprints):
            return (self.fingerprints[:n], self.bar_indices[:n], self.closes[:n])
        # wrapped: reorder so it's chronological
        start = self._count % len(self.fingerprints)
        idx = np.concatenate([np.arange(start, len(self.fingerprints)), np.arange(0, start)])
        return (self.fingerprints[idx], self.bar_indices[idx], self.closes[idx])

    def query(self, live_fingerprint: np.ndarray, current_bar: int,
              horizon: int, top_k: int = None, threshold: float = 0.95):
        """
        Step 4 — Similarity Matching, restricted to entries whose forward
        outcome (current_bar - bar_index >= horizon) is already realized.

        Returns a structured array of matches sorted by similarity desc:
        [(bar_index, similarity, close)]
        """
        fps, bar_idx, closes = self._active_view()
        if len(fps) == 0:
            return []

        usable = (current_bar - bar_idx) >= horizon
        if not usable.any():
            return []

        fps_u, bar_idx_u, closes_u = fps[usable], bar_idx[usable], closes[usable]

        norm = np.linalg.norm(live_fingerprint)
        live_unit = (live_fingerprint / norm) if norm > 0 else live_fingerprint

        sims = fps_u @ live_unit.astype(np.float32)  # vectorized cosine similarity

        mask = sims >= threshold
        if not mask.any():
            return []

        order = np.argsort(-sims[mask])
        if top_k is not None:
            order = order[:top_k]

        matched_bars = bar_idx_u[mask][order]
        matched_sims = sims[mask][order]
        matched_closes = closes_u[mask][order]
        return list(zip(matched_bars.tolist(), matched_sims.tolist(), matched_closes.tolist()))
