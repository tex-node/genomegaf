"""Report-generation smoke test. See Section 17 item 20 of the T4.4A
spec, and the reproducibility manifest (Section 21)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from research.t44a.parser import load_records
from research.t44a.aggregate import dedupe_snapshots, validate_semantics, add_derived_fields
from research.t44a.report import write_outputs, research_verdict

FIXTURE = Path(__file__).parent / "fixtures" / "sample_t44c.txt"

EXPECTED_FILES = [
    "01_records.csv", "02_audit.csv", "03_cell_summary.csv", "04_side_source_summary.csv",
    "05_asset_class_summary.csv", "06_market_summary.csv", "07_overall_summary.csv",
    "08_market_cell_matrix.csv", "09_pair_count_matrix.csv", "10_report.md", "11_manifest.json",
]


class TestReportGeneration(unittest.TestCase):
    # Section 17, item 20: report generation smoke test
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_all_eleven_files_produced(self):
        records, hashes = load_records([str(FIXTURE)])
        dedupe_snapshots(records)
        validate_semantics(records)
        add_derived_fields(records)
        results = write_outputs(records, self.tmp_dir, [str(FIXTURE)], hashes)

        for fname in EXPECTED_FILES:
            path = self.tmp_dir / fname
            self.assertTrue(path.exists(), f"missing output file: {fname}")
            self.assertGreater(path.stat().st_size, 0, f"empty output file: {fname}")

        self.assertIn("integrity", results)
        self.assertIn("verdict", results)
        self.assertGreater(results["integrity"]["records_discovered"], 0)

    def test_report_never_contains_forbidden_words(self):
        records, hashes = load_records([str(FIXTURE)])
        dedupe_snapshots(records)
        validate_semantics(records)
        add_derived_fields(records)
        write_outputs(records, self.tmp_dir, [str(FIXTURE)], hashes)

        text = (self.tmp_dir / "10_report.md").read_text(encoding="utf-8")
        for word in ("VALIDATED", "PROVEN", "SIGNIFICANT", "TRADEABLE"):
            self.assertNotIn(word, text)
        # never a buy/sell instruction
        self.assertNotIn("BUY NOW", text.upper())
        self.assertNotIn("SELL NOW", text.upper())

    def test_manifest_is_valid_json_with_required_keys(self):
        records, hashes = load_records([str(FIXTURE)])
        dedupe_snapshots(records)
        validate_semantics(records)
        add_derived_fields(records)
        write_outputs(records, self.tmp_dir, [str(FIXTURE)], hashes)

        manifest = json.loads((self.tmp_dir / "11_manifest.json").read_text(encoding="utf-8"))
        for key in ("schema_version", "tool_version", "generated_at_utc", "input_files",
                    "input_sha256", "records_discovered", "records_retained", "records_invalid",
                    "snapshot_duplicates", "snapshot_conflicts", "cohorts", "markets",
                    "asset_classes", "pair_total", "configuration"):
            self.assertIn(key, manifest)
        self.assertIn("arithmetic_tolerance", manifest["configuration"])
        self.assertIn("sign_epsilon", manifest["configuration"])

    def test_no_input_files_no_crash_on_empty_dir(self):
        empty_dir = self.tmp_dir / "empty_input"
        empty_dir.mkdir()
        records, hashes = load_records([str(empty_dir)])
        self.assertEqual(records, [])
        dedupe_snapshots(records)
        validate_semantics(records)
        add_derived_fields(records)
        results = write_outputs(records, self.tmp_dir / "out", [str(empty_dir)], hashes)
        self.assertEqual(results["integrity"]["records_discovered"], 0)


class TestResearchVerdictMapping(unittest.TestCase):
    def test_maps_every_classification_to_an_allowed_label(self):
        allowed = {"ACCUMULATE", "INSUFFICIENT_CROSS_MARKET_EVIDENCE", "MIXED",
                   "DESCRIPTIVE_POSITIVE", "DESCRIPTIVE_NEGATIVE"}
        classifications = ["INSUFFICIENT", "EARLY_MIXED", "EARLY_CONSISTENT_POS",
                            "EARLY_CONSISTENT_NEG", "CROSS_MARKET_POS", "CROSS_MARKET_NEG"]
        for c in classifications:
            self.assertIn(research_verdict(c), allowed)


if __name__ == "__main__":
    unittest.main()
