"""Tests for the CLI's CSV handling and --strict flag.

The core module already covers the reconciliation math in isolation;
these tests are about the plumbing around it - parsing rows out of an
actual file, exit codes, and the strict/non-strict tolerance switch.
"""
import io
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


class MainTests(unittest.TestCase):
    def test_strict_flag_is_wired_through(self):
        path = write_csv(["widget,3,3.335,0,10.00"])
        try:
            self.assertEqual(main([path]), 0)
            self.assertEqual(main([path, "--strict"]), 1)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
