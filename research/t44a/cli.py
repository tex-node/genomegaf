"""
cli.py
Command-line entry point.

    python t44a.py records.txt
    python t44a.py ./exports/
    python t44a.py dow.txt wti.txt ndx.txt
    cat records.txt | python t44a.py -

This is an OFFLINE DIAGNOSTIC research tool. It never modifies Pine
model logic, thresholds, gates, or production trading logic, and it
creates no feedback path back into the model.
"""

import argparse
from pathlib import Path

from .parser import load_records
from .aggregate import (
    ARITH_TOLERANCE_DEFAULT, SIGN_EPSILON_DEFAULT,
    dedupe_snapshots, validate_semantics, add_derived_fields,
)
from .report import write_outputs, print_console_summary, OUTPUT_DIR_NAME


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="t44a",
        description="T4.4A -- external cross-market matched-control aggregator "
                     "(offline diagnostic research tool; does not modify Pine model logic).",
    )
    p.add_argument("paths", nargs="+",
                    help="Input file(s), a directory of *.txt/*.log/*.csv, or '-' for stdin.")
    p.add_argument("--out", default=OUTPUT_DIR_NAME,
                    help=f"Output directory (default: {OUTPUT_DIR_NAME}/)")
    p.add_argument("--arithmetic-tolerance", type=float, default=ARITH_TOLERANCE_DEFAULT,
                    help=f"Tolerance for DRET/DMFE/DMAE reconciliation checks (default: {ARITH_TOLERANCE_DEFAULT})")
    p.add_argument("--sign-epsilon", type=float, default=SIGN_EPSILON_DEFAULT,
                    help=f"Epsilon for treating a delta as positive/negative vs. zero (default: {SIGN_EPSILON_DEFAULT})")
    p.add_argument("--quiet", action="store_true", help="Suppress the console summary.")
    return p


def run(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    records, file_hashes = load_records(args.paths)
    dedupe_snapshots(records)
    validate_semantics(records, arithmetic_tolerance=args.arithmetic_tolerance)
    add_derived_fields(records, epsilon=args.sign_epsilon)

    for r in records:
        if not r.parse_ok:
            print(f"WARNING: malformed T44C record (record_index={r.record_index}, "
                  f"source={r.source_file}): {'; '.join(r.parse_errors)}")
        elif not r.valid:
            print(f"WARNING: invalid T44C record excluded from aggregation "
                  f"(record_index={r.record_index}, SYM={r.sym}, CELL={r.cell}): "
                  f"{'; '.join(r.warnings)}")
        elif r.is_snapshot_conflict:
            print(f"WARNING: SNAPSHOT_CONFLICT (record_index={r.record_index}, "
                  f"SYM={r.sym}, CELL={r.cell}): {'; '.join(r.warnings)}")

    results = write_outputs(
        records, Path(args.out), args.paths, file_hashes,
        arithmetic_tolerance=args.arithmetic_tolerance, sign_epsilon=args.sign_epsilon,
    )

    if not args.quiet:
        print()
        print_console_summary(results)

    return 0


def main():
    raise SystemExit(run())


if __name__ == "__main__":
    main()
