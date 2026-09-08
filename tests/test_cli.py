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
