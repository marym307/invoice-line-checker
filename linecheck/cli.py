"""Command line entry point.

Reads a CSV of invoice line items and prints any line whose stated
total doesn't match quantity * unit_price, minus the discount, plus
tax on what's left after the discount.
"""
import argparse
import csv
import sys
from decimal import Decimal

from .core import LineItem, LineItemError, check_line, to_decimal

REQUIRED_FIELDS = ("description", "quantity", "unit_price", "discount_pct", "total")


def parse_row(row: dict, line_number: int) -> LineItem:
    missing = [f for f in REQUIRED_FIELDS if f not in row]
    if missing:
        raise LineItemError(f"line {line_number}: missing column(s) {missing}")
    # tax_rate is optional so existing invoices without it keep working.
    raw_tax_rate = row.get("tax_rate", "")
    tax_rate = to_decimal(raw_tax_rate, "tax_rate") if raw_tax_rate and raw_tax_rate.strip() else Decimal("0")
    return LineItem(
        description=row["description"],
        quantity=to_decimal(row["quantity"], "quantity"),
        unit_price=to_decimal(row["unit_price"], "unit_price"),
        discount_pct=to_decimal(row["discount_pct"], "discount_pct"),
        stated_total=to_decimal(row["total"], "total"),
        tax_rate=tax_rate,
    )


def run(path: str, out=sys.stdout) -> int:
    problems = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_number, row in enumerate(reader, start=2):  # header is line 1
            try:
                item = parse_row(row, line_number)
            except LineItemError as exc:
                print(f"error: {exc}", file=out)
                problems += 1
                continue
            result = check_line(item)
            if not result.ok:
                problems += 1
                print(
                    f"line {line_number}: {item.description!r} stated {item.stated_total} "
                    f"but expected {result.expected_total} (off by {result.diff})",
                    file=out,
                )
    if problems == 0:
        print("all line items check out", file=out)
    return 1 if problems else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="linecheck",
        description="Check invoice line-item totals against quantity, unit price, and discount.",
    )
    parser.add_argument(
        "csv_path",
        help=(
            "CSV file with description,quantity,unit_price,discount_pct,total "
            "columns (tax_rate is optional)"
        ),
    )
    args = parser.parse_args(argv)
    return run(args.csv_path)


if __name__ == "__main__":
    raise SystemExit(main())
