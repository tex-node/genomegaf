"""Aggregation-level tests: dedup, semantic validation, weighted means,
consistency/concentration metrics, maturity/breadth labels, and evidence
classification. See Section 17 items 5-16, 19 of the T4.4A spec."""

import unittest

import pandas as pd

from research.t44a.parser import T44Record, METRIC_ATTR_MAP, ALL_FIELDS
from research.t44a.aggregate import (
    dedupe_snapshots, validate_semantics, add_derived_fields, eligible_dataframe,
    maturity_label, breadth_label, classify_evidence, summarize_group,
    _weighted_mean, _market_consistency,
)


def make_record(record_index=0, sym="DOW", asset_class="EQUITY_INDEX", cohort="T42-H20",
                 cell="B_BAND_T01-05", pair=8, **metrics):
    """Builds a fully-formed, structurally-valid T44Record for tests
    that exercise aggregate.py directly, without going through the text
    parser. Any metric not given defaults to a small self-consistent
    positive example so validate_semantics() passes cleanly unless a
    test deliberately breaks something."""
    defaults = dict(eret=0.5, cret=0.2, dret=0.3, ehit=60.0, chit=50.0,
                     emfe=0.8, cmfe=0.5, dmfe=0.3, emae=-0.4, cmae=-0.5, dmae=0.1)
    defaults.update(metrics)
    r = T44Record(record_index=record_index, source_file="test", raw_text="T44C|...")
    r.sym, r.asset_class, r.cohort, r.cell, r.pair = sym, asset_class, cohort, cell, pair
    r.side, r.source, r.age_bucket = ("BUY" if cell[0] == "B" else "SELL"), cell.split("_")[1], cell.split("_", 2)[2]
    for key, attr in METRIC_ATTR_MAP.items():
        setattr(r, attr, defaults[attr])
    r.field_present = {k: True for k in ALL_FIELDS}
    r.field_raw = {k: "x" for k in ALL_FIELDS}
    r.parse_ok = True
    return r


class TestWeightedMean(unittest.TestCase):
    # Section 17, item 5
    def test_pair_weighted_mean(self):
        df = pd.DataFrame({"dret": [1.0, 2.0, 3.0], "pair": [10, 20, 30]})
        # (1*10 + 2*20 + 3*30) / 60 = (10+40+90)/60 = 140/60
        self.assertAlmostEqual(_weighted_mean(df, "dret"), 140 / 60)

    def test_ignores_zero_pair_rows(self):
        df = pd.DataFrame({"dret": [1.0, 99.0], "pair": [10, 0]})
        self.assertAlmostEqual(_weighted_mean(df, "dret"), 1.0)

    def test_empty_returns_none(self):
        df = pd.DataFrame({"dret": [], "pair": []})
        self.assertIsNone(_weighted_mean(df, "dret"))


class TestDedupeSnapshots(unittest.TestCase):
    # Section 17, item 6
    def test_keeps_highest_pair(self):
        r1 = make_record(record_index=0, pair=5, dret=0.10)
        r2 = make_record(record_index=1, pair=9, dret=0.12)
        dedupe_snapshots([r1, r2])
        self.assertTrue(r1.is_duplicate_dropped)
        self.assertFalse(r1.retained)
        self.assertFalse(r2.is_duplicate_dropped)
        self.assertTrue(r2.retained)

    # Section 17, item 19: no pseudo-observation expansion
    def test_pair_not_summed_across_duplicates(self):
        r1 = make_record(record_index=0, pair=5, dret=0.10)
        r2 = make_record(record_index=1, pair=9, dret=0.12)
        records = dedupe_snapshots([r1, r2])
        validate_semantics(records)
        add_derived_fields(records)
        df = eligible_dataframe(records)
        # only the PAIR=9 winner should be eligible -- total must be 9, not 14
        self.assertEqual(int(df["pair"].sum()), 9)
        self.assertEqual(len(df), 1)

    def test_single_record_group_always_retained(self):
        r1 = make_record(record_index=0, pair=8)
        dedupe_snapshots([r1])
        self.assertTrue(r1.retained)
        self.assertFalse(r1.is_duplicate_dropped)


class TestSnapshotConflict(unittest.TestCase):
    # Section 17, item 7
    def test_equal_pair_differing_metrics_flagged(self):
        r1 = make_record(record_index=0, pair=8, dret=0.30)
        r2 = make_record(record_index=1, pair=8, dret=0.45)  # same PAIR, different DRET
        dedupe_snapshots([r1, r2])
        self.assertTrue(r1.is_snapshot_conflict)
        self.assertTrue(r2.is_snapshot_conflict)
        # last encountered wins
        self.assertFalse(r1.retained)
        self.assertTrue(r2.retained)

    def test_equal_pair_identical_metrics_not_flagged(self):
        r1 = make_record(record_index=0, pair=8, dret=0.30)
        r2 = make_record(record_index=1, pair=8, dret=0.30)
        dedupe_snapshots([r1, r2])
        self.assertFalse(r1.is_snapshot_conflict)
        self.assertFalse(r2.is_snapshot_conflict)
        self.assertTrue(r2.retained)  # still "last encountered" by convention


class TestArithmeticValidation(unittest.TestCase):
    # Section 17, items 8, 9, 10
    def test_dret_ok_within_tolerance(self):
        r = make_record(eret=0.850, cret=0.220, dret=0.630)
        validate_semantics([r])
        self.assertTrue(r.ret_delta_ok)

    def test_dret_flagged_outside_tolerance(self):
        r = make_record(eret=0.850, cret=0.220, dret=0.500)  # should be 0.630
        validate_semantics([r])
        self.assertFalse(r.ret_delta_ok)
        # arithmetic mismatch is flagged but does NOT exclude the record
        self.assertTrue(r.valid)

    def test_dmfe_ok_and_flagged(self):
        ok = make_record(emfe=1.2, cmfe=0.9, dmfe=0.3)
        bad = make_record(emfe=1.2, cmfe=0.9, dmfe=0.9)
        validate_semantics([ok, bad])
        self.assertTrue(ok.mfe_delta_ok)
        self.assertFalse(bad.mfe_delta_ok)

    def test_dmae_ok_and_flagged(self):
        ok = make_record(emae=-0.4, cmae=-0.5, dmae=0.1)
        bad = make_record(emae=-0.4, cmae=-0.5, dmae=0.9)
        validate_semantics([ok, bad])
        self.assertTrue(ok.mae_delta_ok)
        self.assertFalse(bad.mae_delta_ok)

    def test_missing_metric_for_pair_gt_0_is_invalid(self):
        r = make_record(pair=8)
        r.field_present["ERET"] = False  # simulate a missing key for a PAIR>0 record
        validate_semantics([r])
        self.assertFalse(r.valid)

    def test_hit_out_of_range_is_invalid(self):
        r = make_record(ehit=150.0)
        validate_semantics([r])
        self.assertFalse(r.valid)


class TestPositiveMarketShare(unittest.TestCase):
    # Section 17, item 11
    def test_pos_neg_zero_and_share(self):
        df = pd.DataFrame({
            "sym": ["A", "B", "C", "D"],
            "dret": [0.5, -0.3, 0.0, 0.2],
            "pair": [10, 10, 10, 10],
        })
        stats = _market_consistency(df, "dret")
        self.assertEqual(stats["pos"], 2)
        self.assertEqual(stats["neg"], 1)
        self.assertEqual(stats["zero"], 1)
        self.assertAlmostEqual(stats["pos_share"], 0.5)


class TestConcentrationFlags(unittest.TestCase):
    # Section 17, items 12, 13
    def test_market_concentrated_flag(self):
        records = [
            make_record(record_index=0, sym="A", pair=60, dret=0.3),
            make_record(record_index=1, sym="B", pair=40, dret=0.2),
        ]
        dedupe_snapshots(records)
        validate_semantics(records)
        add_derived_fields(records)
        df = eligible_dataframe(records)
        row = summarize_group(df, "test", "TEST")
        self.assertTrue(row["MARKET_CONCENTRATED"])  # 60/100 = 0.60 > 0.50

    def test_market_not_concentrated_when_balanced(self):
        records = [
            make_record(record_index=0, sym="A", pair=50, dret=0.3),
            make_record(record_index=1, sym="B", pair=50, dret=0.2),
        ]
        dedupe_snapshots(records)
        validate_semantics(records)
        add_derived_fields(records)
        df = eligible_dataframe(records)
        row = summarize_group(df, "test", "TEST")
        self.assertFalse(row["MARKET_CONCENTRATED"])  # 50/100 = 0.50, not > 0.50

    def test_class_concentrated_flag(self):
        records = [
            make_record(record_index=0, sym="A", asset_class="FX", pair=80, dret=0.3),
            make_record(record_index=1, sym="B", asset_class="METAL", pair=20, dret=0.2),
        ]
        dedupe_snapshots(records)
        validate_semantics(records)
        add_derived_fields(records)
        df = eligible_dataframe(records)
        row = summarize_group(df, "test", "TEST")
        self.assertTrue(row["CLASS_CONCENTRATED"])  # 80/100 = 0.80 > 0.70


class TestMaturityLabels(unittest.TestCase):
    # Section 17, item 14
    def test_boundaries(self):
        self.assertEqual(maturity_label(0), "EMBRYONIC")
        self.assertEqual(maturity_label(4), "EMBRYONIC")
        self.assertEqual(maturity_label(5), "EARLY")
        self.assertEqual(maturity_label(9), "EARLY")
        self.assertEqual(maturity_label(10), "DEVELOPING")
        self.assertEqual(maturity_label(19), "DEVELOPING")
        self.assertEqual(maturity_label(20), "MATURE")
        self.assertEqual(maturity_label(1000), "MATURE")


class TestBreadthLabels(unittest.TestCase):
    # Section 17, item 15
    def test_boundaries(self):
        self.assertEqual(breadth_label(0), "SINGLE_MARKET")
        self.assertEqual(breadth_label(1), "SINGLE_MARKET")
        self.assertEqual(breadth_label(2), "LIMITED_BREADTH")
        self.assertEqual(breadth_label(3), "MULTI_MARKET")
        self.assertEqual(breadth_label(4), "MULTI_MARKET")
        self.assertEqual(breadth_label(5), "BROAD")
        self.assertEqual(breadth_label(50), "BROAD")


class TestEvidenceClassification(unittest.TestCase):
    # Section 17, item 16
    def test_insufficient_low_pairs(self):
        stats = {"pos": 1, "neg": 0, "zero": 0, "pos_share": 1.0}
        self.assertEqual(classify_evidence(3, 3, 0.5, stats), "INSUFFICIENT")

    def test_insufficient_single_market(self):
        stats = {"pos": 1, "neg": 0, "zero": 0, "pos_share": 1.0}
        self.assertEqual(classify_evidence(50, 1, 0.5, stats), "INSUFFICIENT")

    def test_cross_market_pos(self):
        stats = {"pos": 5, "neg": 1, "zero": 0, "pos_share": 5 / 6}
        self.assertEqual(classify_evidence(25, 6, 0.4, stats), "CROSS_MARKET_POS")

    def test_cross_market_neg(self):
        stats = {"pos": 1, "neg": 5, "zero": 0, "pos_share": 1 / 6}
        self.assertEqual(classify_evidence(25, 6, -0.4, stats), "CROSS_MARKET_NEG")

    def test_early_consistent_pos_below_breadth_threshold(self):
        # meets the >60% share bar but not the >=20 pairs / >=5 markets bar
        stats = {"pos": 3, "neg": 1, "zero": 0, "pos_share": 0.75}
        self.assertEqual(classify_evidence(10, 4, 0.3, stats), "EARLY_CONSISTENT_POS")

    def test_early_mixed(self):
        stats = {"pos": 2, "neg": 2, "zero": 0, "pos_share": 0.5}
        self.assertEqual(classify_evidence(10, 4, 0.1, stats), "EARLY_MIXED")

    def test_never_returns_forbidden_labels(self):
        forbidden = {"VALIDATED", "PROVEN", "SIGNIFICANT", "TRADEABLE"}
        for pt in (0, 3, 10, 25, 100):
            for nm in (0, 1, 2, 5, 10):
                for wd in (None, -0.5, 0.0, 0.5):
                    stats = {"pos": 1, "neg": 1, "zero": 0, "pos_share": 0.5}
                    label = classify_evidence(pt, nm, wd, stats)
                    self.assertNotIn(label, forbidden)


if __name__ == "__main__":
    unittest.main()
