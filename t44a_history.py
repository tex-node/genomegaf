#!/usr/bin/env python3
"""Thin CLI for T4.4A.1 longitudinal checkpoint accumulation."""

import argparse
from pathlib import Path

from research.t44a.history import append_checkpoint


def main() -> None:
    p = argparse.ArgumentParser(
        description="T4.4A.1 append-only longitudinal evidence accumulator"
    )
    p.add_argument("report_dir", help="Completed T4.4A report directory")
    p.add_argument("--label", required=True, help="Immutable checkpoint label, e.g. REAL-1")
    p.add_argument("--store", default="t44a_history", help="History output directory")
    args = p.parse_args()

    result = append_checkpoint(Path(args.report_dir), Path(args.store), args.label)
    print(
        f"T4.4A.1 {result['status']}: {result['checkpoint']} "
        f"({result['count']} checkpoint(s) in history)"
    )


if __name__ == "__main__":
    main()
