"""Command line entry point.

Reads a CSV of invoice line items and prints any line whose stated
total doesn't match quantity * unit_price, minus the discount, plus
tax on what's left after the discount.
"""
import argparse
import csv
import sys
from decimal import Decimal

from .core import LineItem, LineItemError, check_invoice_total, check_line, to_decimal

ZERO_TOLERANCE = Decimal("0")

REQUIRED_FIELDS = ("description", "quantity", "unit_price", "discount_pct", "total")


def parse_row(row: dict, line_number: int) -> LineItem:
    missing = [f for f in REQUIRED_FIELDS if f not in row]
    if missing:
        raise LineItemError(f"line {line_number}: missing column(s) {missing}")
    # tax_rate is optional so existing invoices without it keep working.
    raw_tax_rate = row.get("tax_rate", "")
    tax_rate = to_decimal(raw_tax_rate, "tax_rate") if raw_tax_rate and raw_tax_rate.strip() else Decimal("0")
    # invoice_id is optional too: rows without it are all treated as one
    # invoice, so single-invoice files don't need to name it.
    raw_invoice_id = row.get("invoice_id", "")
    invoice_id = raw_invoice_id.strip() if raw_invoice_id and raw_invoice_id.strip() else "1"
    # currency is optional; rows without it are assumed to be USD, which
    # rounds the same way as most other currencies anyway.
    raw_currency = row.get("currency", "")
    currency = raw_currency.strip().upper() if raw_currency and raw_currency.strip() else "USD"
    return LineItem(
        description=row["description"],
        quantity=to_decimal(row["quantity"], "quantity"),
        unit_price=to_decimal(row["unit_price"], "unit_price"),
        discount_pct=to_decimal(row["discount_pct"], "discount_pct"),
        stated_total=to_decimal(row["total"], "total"),
        tax_rate=tax_rate,
        invoice_id=invoice_id,
        currency=currency,
    )


def run(path: str, out=sys.stdout, strict: bool = False) -> int:
    tolerance = ZERO_TOLERANCE if strict else None
    problems = 0
    items_by_invoice = {}
    stated_invoice_totals = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_number, row in enumerate(reader, start=2):  # header is line 1
            try:
                item = parse_row(row, line_number)
            except LineItemError as exc:
                print(f"error: {exc}", file=out)
                problems += 1
                continue
            result = check_line(item) if tolerance is None else check_line(item, tolerance=tolerance)
            if not result.ok:
                problems += 1
                print(
                    f"line {line_number}: {item.description!r} stated {item.stated_total} "
                    f"but expected {result.expected_total} (off by {result.diff})",
                    file=out,
                )
            items_by_invoice.setdefault(item.invoice_id, []).append(item)

            raw_invoice_total = row.get("invoice_total", "")
            if raw_invoice_total and raw_invoice_total.strip():
                try:
                    stated = to_decimal(raw_invoice_total, "invoice_total")
                except LineItemError as exc:
                    print(f"error: {exc}", file=out)
                    problems += 1
                    continue
                seen = stated_invoice_totals.get(item.invoice_id)
                if seen is not None and seen != stated:
                    print(
                        f"error: line {line_number}: conflicting invoice_total for "
                        f"invoice {item.invoice_id!r} ({seen} vs {stated})",
                        file=out,
                    )
                    problems += 1
                else:
                    stated_invoice_totals[item.invoice_id] = stated

    for invoice_id, stated_total in stated_invoice_totals.items():
        items = items_by_invoice[invoice_id]
        result = (
            check_invoice_total(items, stated_total)
            if tolerance is None
            else check_invoice_total(items, stated_total, tolerance=tolerance)
        )
        if not result.ok:
            problems += 1
            print(
                f"invoice {invoice_id!r}: stated total {result.stated_total} but line "
                f"items sum to {result.line_item_sum} (off by {result.diff})",
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
            "columns (tax_rate, invoice_id, invoice_total, and currency are "
            "optional; currency defaults to USD)"
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "require the stated total to match exactly, instead of allowing "
            "the default one-minor-unit rounding tolerance"
        ),
    )
    args = parser.parse_args(argv)
    return run(args.csv_path, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
