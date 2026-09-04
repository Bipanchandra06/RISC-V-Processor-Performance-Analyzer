import unittest

from src.export import csv_bytes, hazard_rows, pdf_bytes, predictor_rows


class ExportTests(unittest.TestCase):
    def test_hazard_rows_are_cycle_indexed(self):
        payload = {"traces": {"five_stage": [{"cycle": 4, "events": ["load-use stall", "forward A=10, B=00"]}]}}
        rows = hazard_rows(payload)
        self.assertEqual(rows[0]["Cycle"], 4)
        self.assertEqual(rows[0]["Stall cycles"], 1)
        self.assertEqual(rows[1]["Resolution"], "Operand forwarding")

    def test_download_formats_contain_sections(self):
        payload = {"cores": {}, "traces": {}, "predictors": {}}
        self.assertIn(b"PERFORMANCE SUMMARY", csv_bytes(payload))
        self.assertTrue(pdf_bytes(payload).startswith(b"%PDF-1.4"))

    def test_predictor_rows_are_five_stage_only(self):
        payload = {"predictors": {"branch": {
            "single_stage": {"mode": "always-not-taken"},
            "five_stage": {"mode": "two-bit"},
        }}}
        rows = predictor_rows(payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Processor"], "Five Stage")


if __name__ == "__main__":
    unittest.main()
