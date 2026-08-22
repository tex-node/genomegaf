"""T4.4A -- external cross-market matched-control research utilities.

Offline diagnostic research tooling only. Parses T44C records emitted by
the frozen Pine T4.4 matched-control experiment, produces descriptive
cross-market evidence reports, and preserves successive reports in an
append-only T4.4A.1 longitudinal history. Does not modify, gate, or feed
back into any Pine model logic.
"""

__version__ = "1.1.0"
