import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from research.t44a.history import append_checkpoint


class T44AHistoryTests(unittest.TestCase):
    def make_report(self, root: Path, dret=0.25):
        report = root / "report"
        report.mkdir()
        pd.DataFrame([{
            "N_MARKETS": 3,
            "PAIR_WEIGHTED_DRET": dret,
            "PAIR_WEIGHTED_DELTA_HIT": 10.0,
            "PAIR_WEIGHTED_DMFE": 0.2,
            "PAIR_WEIGHTED_DMAE": 0.1,
            "DRET_POS_MARKET_SHARE": 2 / 3,
            "MEDIAN_MARKET_DRET": 0.1,
            "MATURITY": "EARLY",
            "BREADTH": "MULTI_MARKET",
            "CLASSIFICATION": "EARLY_CONSISTENT_POS",
        }]).to_csv(report / "07_overall_summary.csv", index=False)
        pd.DataFrame([
            {"GROUP": "BAND", "PAIR_TOTAL": 4, "MARKETS": 3, "PAIR_WEIGHTED_DRET": -0.2,
             "PAIR_WEIGHTED_DELTA_HIT": -5.0, "DRET_POS_MARKET_SHARE": 1/3,
             "MATURITY": "EARLY", "BREADTH": "MULTI_MARKET", "CLASSIFICATION": "EARLY_MIXED"},
            {"GROUP": "DIV", "PAIR_TOTAL": 5, "MARKETS": 3, "PAIR_WEIGHTED_DRET": 0.5,
             "PAIR_WEIGHTED_DELTA_HIT": 20.0, "DRET_POS_MARKET_SHARE": 1.0,
             "MATURITY": "EARLY", "BREADTH": "MULTI_MARKET", "CLASSIFICATION": "EARLY_CONSISTENT_POS"},
        ]).to_csv(report / "04_side_source_summary.csv", index=False)
        (report / "10_report.md").write_text(
            "# Report\n\n## Research Verdict\n\n**ACCUMULATE**\n", encoding="utf-8"
        )
        (report / "11_manifest.json").write_text(json.dumps({
            "generated_at_utc": "2026-08-22T18:00:00+00:00",
            "pair_total": 9,
            "records_retained": 6,
            "markets": ["A", "B", "C"],
            "asset_classes": ["X", "Y"],
        }), encoding="utf-8")
        return report

    def test_append_writes_history_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = self.make_report(root)
            store = root / "history"
            result = append_checkpoint(report, store, "REAL-1")
            self.assertEqual(result["status"], "APPENDED")
            self.assertTrue((store / "01_checkpoints.csv").exists())
            self.assertTrue((store / "02_source_trend.csv").exists())
            self.assertTrue((store / "03_history.md").exists())
            self.assertTrue((store / "04_history_manifest.json").exists())
            cp = pd.read_csv(store / "01_checkpoints.csv")
            self.assertEqual(cp.loc[0, "checkpoint"], "REAL-1")
            self.assertEqual(int(cp.loc[0, "pair_total"]), 9)

    def test_same_checkpoint_same_evidence_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = self.make_report(root)
            store = root / "history"
            append_checkpoint(report, store, "REAL-1")
            result = append_checkpoint(report, store, "REAL-1")
            self.assertEqual(result["status"], "UNCHANGED")
            self.assertEqual(len(pd.read_csv(store / "01_checkpoints.csv")), 1)

    def test_same_label_different_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = self.make_report(root)
            store = root / "history"
            append_checkpoint(report, store, "REAL-1")
            (report / "10_report.md").write_text(
                "# changed\n\n## Research Verdict\n\n**MIXED**\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                append_checkpoint(report, store, "REAL-1")

    def test_incomplete_report_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = root / "report"
            report.mkdir()
            with self.assertRaises(ValueError):
                append_checkpoint(report, root / "history", "REAL-1")


if __name__ == "__main__":
    unittest.main()
