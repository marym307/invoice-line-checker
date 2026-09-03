"""Table-driven tests for the line-item reconciliation core.

These are the cases that are easy to get wrong: negative quantities
for credits and returns, discounts that land exactly on a rounding
boundary, and discount percentages outside 0-100.
"""
import unittest
from decimal import Decimal

from linecheck.core import LineItem, LineItemError, check_line, expected_line_total


class ExpectedLineTotalTests(unittest.TestCase):
    # (label, quantity, unit_price, discount_pct, expected total)
    CASES = [
        ("plain multiplication", "5", "10.00", "0", "50.00"),
        ("ten percent discount", "5", "10.00", "10", "45.00"),
        ("fractional quantity (hours billed)", "2.5", "40.00", "0", "100.00"),
        ("full discount zeroes the line", "3", "19.99", "100", "0.00"),
        ("credit / return line has negative quantity", "-2", "15.00", "0", "-30.00"),
        ("half-cent rounds up, not to even", "1", "0.125", "0", "0.13"),
        ("another half-cent, still rounds up", "1", "0.135", "0", "0.14"),
        ("tiny unit price, large quantity", "1000", "0.001", "0", "1.00"),
        ("discount produces a fraction of a cent", "3", "10.00", "33.33", "20.00"),
    ]

    def test_cases(self):
        for label, quantity, unit_price, discount_pct, expected in self.CASES:
            with self.subTest(label):
                result = expected_line_total(
                    Decimal(quantity), Decimal(unit_price), Decimal(discount_pct)
                )
                self.assertEqual(result, Decimal(expected))

    def test_discount_over_100_is_rejected(self):
        with self.assertRaises(LineItemError):
            expected_line_total(Decimal("1"), Decimal("10.00"), Decimal("101"))

    def test_negative_discount_is_rejected(self):
        with self.assertRaises(LineItemError):
            expected_line_total(Decimal("1"), Decimal("10.00"), Decimal("-1"))


class CheckLineTests(unittest.TestCase):
    def test_matching_total_is_ok(self):
        item = LineItem("widget", Decimal("2"), Decimal("5.00"), Decimal("0"), Decimal("10.00"))
        result = check_line(item)
        self.assertTrue(result.ok)
        self.assertEqual(result.diff, Decimal("0.00"))

    def test_mismatched_total_is_flagged(self):
        item = LineItem("widget", Decimal("2"), Decimal("5.00"), Decimal("0"), Decimal("11.00"))
        result = check_line(item)
        self.assertFalse(result.ok)
        self.assertEqual(result.diff, Decimal("1.00"))

    def test_stated_total_within_rounding_tolerance_is_ok(self):
        # Different invoicing systems round per-line amounts slightly
        # differently; a one-cent gap is noise, not an error.
        item = LineItem("widget", Decimal("3"), Decimal("3.335"), Decimal("0"), Decimal("10.00"))
        result = check_line(item)
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
