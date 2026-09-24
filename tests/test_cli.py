"""Tests for the CLI's CSV handling and --strict flag.

The core module already covers the reconciliation math in isolation;
these tests are about the plumbing around it - parsing rows out of an
actual file, exit codes, and the strict/non-strict tolerance switch.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest

from linecheck.cli import main, run


def write_csv(rows, header="description,quantity,unit_price,discount_pct,total"):
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        f.write("\n".join(rows) + "\n")
    return path


class RunTests(unittest.TestCase):
    def test_clean_invoice_exits_zero(self):
        path = write_csv(["widget,2,5.00,0,10.00"])
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out), 0)
            self.assertIn("all line items check out", out.getvalue())
        finally:
            os.remove(path)

    def test_mismatched_total_exits_one_and_is_reported(self):
        path = write_csv(["widget,2,5.00,0,11.00"])
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out), 1)
            self.assertIn("expected 10.00", out.getvalue())
        finally:
            os.remove(path)

    def test_within_tolerance_passes_by_default_but_fails_strict(self):
        # 3 * 3.335 = 10.005, which rounds to 10.01 but is within a
        # cent of the stated 10.00 - the default tolerance accepts it.
        path = write_csv(["widget,3,3.335,0,10.00"])
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out), 0)

            strict_out = io.StringIO()
            self.assertEqual(run(path, out=strict_out, strict=True), 1)
            self.assertIn("off by 0.01", strict_out.getvalue())
        finally:
            os.remove(path)

    def test_unparsable_row_is_reported_as_error(self):
        path = write_csv(["widget,not-a-number,5.00,0,10.00"])
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out), 1)
            self.assertIn("error:", out.getvalue())
        finally:
            os.remove(path)


class InvoiceTotalTests(unittest.TestCase):
    def test_matching_invoice_total_is_silent(self):
        path = write_csv(
            ["widget,2,5.00,0,10.00,A1,15.00", "gadget,1,5.00,0,5.00,A1,15.00"],
            header="description,quantity,unit_price,discount_pct,total,invoice_id,invoice_total",
        )
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out), 0)
            self.assertIn("all line items check out", out.getvalue())
        finally:
            os.remove(path)

    def test_mismatched_invoice_total_is_flagged_even_with_correct_lines(self):
        path = write_csv(
            ["widget,2,5.00,0,10.00,A1,20.00", "gadget,1,5.00,0,5.00,A1,20.00"],
            header="description,quantity,unit_price,discount_pct,total,invoice_id,invoice_total",
        )
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out), 1)
            self.assertIn("invoice 'A1'", out.getvalue())
            self.assertIn("sum to 15.00", out.getvalue())
        finally:
            os.remove(path)

    def test_rows_without_invoice_id_are_treated_as_one_invoice(self):
        path = write_csv(
            ["widget,2,5.00,0,10.00,,25.00", "gadget,1,5.00,0,5.00,,25.00"],
            header="description,quantity,unit_price,discount_pct,total,invoice_id,invoice_total",
        )
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out), 1)
            self.assertIn("sum to 15.00", out.getvalue())
        finally:
            os.remove(path)

    def test_conflicting_invoice_totals_for_same_invoice_are_reported(self):
        path = write_csv(
            ["widget,2,5.00,0,10.00,A1,15.00", "gadget,1,5.00,0,5.00,A1,16.00"],
            header="description,quantity,unit_price,discount_pct,total,invoice_id,invoice_total",
        )
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out), 1)
            self.assertIn("conflicting invoice_total", out.getvalue())
        finally:
            os.remove(path)


class CurrencyTests(unittest.TestCase):
    def test_jpy_line_with_no_decimal_places_checks_out(self):
        path = write_csv(
            ["widget,3,1000,0,3000,JPY"],
            header="description,quantity,unit_price,discount_pct,total,currency",
        )
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out), 0)
            self.assertIn("all line items check out", out.getvalue())
        finally:
            os.remove(path)

    def test_jpy_mismatch_is_flagged_with_a_whole_number_expected_total(self):
        path = write_csv(
            ["widget,3,1000,0,3500,JPY"],
            header="description,quantity,unit_price,discount_pct,total,currency",
        )
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out), 1)
            self.assertIn("expected 3000", out.getvalue())
        finally:
            os.remove(path)

    def test_missing_currency_column_defaults_to_usd(self):
        path = write_csv(["widget,2,5.00,0,10.00"])
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out), 0)
        finally:
            os.remove(path)


class MainTests(unittest.TestCase):
    def test_strict_flag_is_wired_through(self):
        path = write_csv(["widget,3,3.335,0,10.00"])
        try:
            self.assertEqual(main([path]), 0)
            self.assertEqual(main([path, "--strict"]), 1)
        finally:
            os.remove(path)


class JsonOutputTests(unittest.TestCase):
    def test_clean_invoice_reports_ok_with_no_problems(self):
        path = write_csv(["widget,2,5.00,0,10.00"])
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out, json_output=True), 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload, {"ok": True, "problems": []})
        finally:
            os.remove(path)

    def test_mismatched_total_is_reported_as_structured_problem(self):
        path = write_csv(["widget,2,5.00,0,11.00"])
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out, json_output=True), 1)
            payload = json.loads(out.getvalue())
            self.assertFalse(payload["ok"])
            self.assertEqual(len(payload["problems"]), 1)
            problem = payload["problems"][0]
            self.assertEqual(problem["type"], "line_mismatch")
            self.assertEqual(problem["line"], 2)
            self.assertEqual(problem["expected_total"], "10.00")
            self.assertEqual(problem["diff"], "1.00")
        finally:
            os.remove(path)

    def test_unparsable_row_is_a_structured_error(self):
        path = write_csv(["widget,not-a-number,5.00,0,10.00"])
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out, json_output=True), 1)
            payload = json.loads(out.getvalue())
            problem = payload["problems"][0]
            self.assertEqual(problem["type"], "error")
            self.assertEqual(problem["line"], 2)
        finally:
            os.remove(path)

    def test_invoice_mismatch_is_a_structured_problem(self):
        path = write_csv(
            ["widget,2,5.00,0,10.00,A1,20.00", "gadget,1,5.00,0,5.00,A1,20.00"],
            header="description,quantity,unit_price,discount_pct,total,invoice_id,invoice_total",
        )
        try:
            out = io.StringIO()
            self.assertEqual(run(path, out=out, json_output=True), 1)
            payload = json.loads(out.getvalue())
            problem = payload["problems"][0]
            self.assertEqual(problem["type"], "invoice_mismatch")
            self.assertEqual(problem["invoice_id"], "A1")
            self.assertEqual(problem["line_item_sum"], "15.00")
        finally:
            os.remove(path)

    def test_json_flag_is_wired_through_main(self):
        path = write_csv(["widget,2,5.00,0,10.00"])
        try:
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                self.assertEqual(main([path, "--json"]), 0)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload, {"ok": True, "problems": []})
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
