"""Parser-level tests: extraction, tolerant text handling, structural
rejection. See Section 17 items 1-4, 17-18 of the T4.4A spec."""

import unittest

from research.t44a.parser import parse_text, parse_block


VALID_RECORD = """T44C
|SYM=DOW
|CLASS=EQUITY_INDEX
|COHORT=T42-H20
|CELL=B_BAND_T01-05
|PAIR=8
|ERET=0.850
|CRET=0.220
|DRET=0.630
|EHIT=62.5
|CHIT=50.0
|EMFE=1.200
|CMFE=0.900
|DMFE=0.300
|EMAE=-0.400
|CMAE=-0.550
|DMAE=0.150
"""


class TestParseValid(unittest.TestCase):
    # Section 17, item 1: parse valid T44C
    def test_parses_all_fields(self):
        recs = parse_text(VALID_RECORD, "test.txt")
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertTrue(r.parse_ok)
        self.assertEqual(r.sym, "DOW")
        self.assertEqual(r.asset_class, "EQUITY_INDEX")
        self.assertEqual(r.cohort, "T42-H20")
        self.assertEqual(r.cell, "B_BAND_T01-05")
        self.assertEqual(r.pair, 8)
        self.assertAlmostEqual(r.eret, 0.850)
        self.assertAlmostEqual(r.dret, 0.630)
        self.assertAlmostEqual(r.dmae, 0.150)


class TestParseNA(unittest.TestCase):
    # Section 17, item 2: parse NA fields
    def test_na_becomes_none(self):
        text = VALID_RECORD.replace("|PAIR=8", "|PAIR=0")
        for key in ("ERET", "CRET", "DRET", "EHIT", "CHIT", "EMFE", "CMFE", "DMFE", "EMAE", "CMAE", "DMAE"):
            text = "\n".join(
                line if not line.startswith(f"|{key}=") else f"|{key}=NA"
                for line in text.split("\n")
            )
        recs = parse_text(text, "test.txt")
        r = recs[0]
        self.assertTrue(r.parse_ok)
        self.assertEqual(r.pair, 0)
        self.assertIsNone(r.eret)
        self.assertIsNone(r.dret)
        self.assertTrue(r.field_present["ERET"])  # key was present, just NA -- not "missing"

    def test_na_case_insensitive(self):
        text = VALID_RECORD.replace("|ERET=0.850", "|ERET=na")
        r = parse_text(text, "test.txt")[0]
        self.assertIsNone(r.eret)
        self.assertTrue(r.field_present["ERET"])


class TestRejectMalformed(unittest.TestCase):
    # Section 17, item 3: reject malformed record
    def test_missing_identity_field_rejected(self):
        text = VALID_RECORD.replace("|SYM=DOW\n", "")
        r = parse_text(text, "test.txt")[0]
        self.assertFalse(r.parse_ok)
        self.assertTrue(any("SYM" in e for e in r.parse_errors))

    def test_bad_cell_pattern_rejected(self):
        text = VALID_RECORD.replace("|CELL=B_BAND_T01-05", "|CELL=B_BAND_XX")
        r = parse_text(text, "test.txt")[0]
        self.assertFalse(r.parse_ok)
        self.assertTrue(any("CELL" in e for e in r.parse_errors))

    def test_non_numeric_metric_rejected(self):
        text = VALID_RECORD.replace("|ERET=0.850", "|ERET=not_a_number")
        r = parse_text(text, "test.txt")[0]
        self.assertFalse(r.parse_ok)
        self.assertTrue(any("ERET" in e for e in r.parse_errors))

    def test_invalid_pair_not_silently_coerced(self):
        text = VALID_RECORD.replace("|PAIR=8", "|PAIR=abc")
        r = parse_text(text, "test.txt")[0]
        self.assertFalse(r.parse_ok)
        self.assertIsNone(r.pair)  # never silently coerced to e.g. 0


class TestCellDecomposition(unittest.TestCase):
    # Section 17, item 4: correct cell decomposition
    def test_side_source_age(self):
        cases = [
            ("B_BAND_T01-05", "BUY", "BAND", "T01-05"),
            ("S_DIV_T16-20", "SELL", "DIV", "T16-20"),
            ("B_DIV_T06-10", "BUY", "DIV", "T06-10"),
            ("S_BAND_T11-15", "SELL", "BAND", "T11-15"),
        ]
        for cell, side, source, age in cases:
            text = VALID_RECORD.replace("|CELL=B_BAND_T01-05", f"|CELL={cell}")
            r = parse_text(text, "test.txt")[0]
            self.assertEqual(r.side, side, cell)
            self.assertEqual(r.source, source, cell)
            self.assertEqual(r.age_bucket, age, cell)


class TestIgnoresUnrelatedText(unittest.TestCase):
    # Section 17, item 17: unrelated TradingView text ignored
    def test_surrounding_noise_ignored(self):
        text = (
            "[TradingView Pine Log] 2026-01-05 09:31:02 chart loaded\n"
            "some random line that is not a record at all | not=a|field=either\n"
            + VALID_RECORD +
            "\n[unrelated] plot redraw complete, tick=48213\n"
        )
        recs = parse_text(text, "test.txt")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].sym, "DOW")
        self.assertTrue(recs[0].parse_ok)

    def test_crlf_and_lf_both_tolerated(self):
        crlf_text = VALID_RECORD.replace("\n", "\r\n")
        r = parse_text(crlf_text, "test.txt")[0]
        self.assertTrue(r.parse_ok)
        self.assertEqual(r.sym, "DOW")


class TestZeroPairSafe(unittest.TestCase):
    # Section 17, item 18: zero-pair record handled safely
    def test_pair_zero_with_na_metrics_parses_ok(self):
        text = VALID_RECORD.replace("|PAIR=8", "|PAIR=0")
        for key in ("ERET", "CRET", "DRET", "EHIT", "CHIT", "EMFE", "CMFE", "DMFE", "EMAE", "CMAE", "DMAE"):
            text = "\n".join(
                line if not line.startswith(f"|{key}=") else f"|{key}=NA"
                for line in text.split("\n")
            )
        r = parse_text(text, "test.txt")[0]
        self.assertTrue(r.parse_ok)
        self.assertEqual(r.pair, 0)


class TestMultipleBlocksAndSourceFile(unittest.TestCase):
    def test_two_records_both_parsed(self):
        text = VALID_RECORD + "\n" + VALID_RECORD.replace("SYM=DOW", "SYM=NAS100")
        recs = parse_text(text, "myfile.txt", start_index=5)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0].record_index, 5)
        self.assertEqual(recs[1].record_index, 6)
        self.assertEqual(recs[0].source_file, "myfile.txt")
        self.assertEqual(recs[1].sym, "NAS100")


if __name__ == "__main__":
    unittest.main()
