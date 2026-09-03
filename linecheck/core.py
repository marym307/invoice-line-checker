"""Core reconciliation logic for invoice line items.

Kept free of any I/O so it can be unit tested without touching a
filesystem or a CSV parser.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


class LineItemError(ValueError):
    pass


@dataclass
class LineItem:
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    stated_total: Decimal


@dataclass
class LineResult:
    item: LineItem
    expected_total: Decimal
    ok: bool
    diff: Decimal


def to_decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise LineItemError(f"{field!r} is not a valid number: {value!r}")


def expected_line_total(quantity: Decimal, unit_price: Decimal, discount_pct: Decimal) -> Decimal:
    """Return the line total a correctly written invoice should show.

    Discount is applied to the raw quantity*unit_price amount, and the
    result is rounded to cents once, at the end, using half-up rounding
    - that's how invoices are written by hand and by most billing
    software, not the banker's rounding Decimal uses by default.
    """
    if discount_pct < 0 or discount_pct > 100:
        raise LineItemError(f"discount_pct out of range: {discount_pct}")
    raw = quantity * unit_price
    discounted = raw * (Decimal(100) - discount_pct) / Decimal(100)
    return discounted.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def check_line(item: LineItem, tolerance: Decimal = TWO_PLACES) -> LineResult:
    """Compare a line item's stated total to what it should be.

    A one-cent tolerance is allowed by default because different
    invoicing systems round per-line amounts slightly differently;
    that's noise, not the kind of error this tool is meant to catch.
    """
    expected = expected_line_total(item.quantity, item.unit_price, item.discount_pct)
    diff = (item.stated_total - expected).copy_abs()
    return LineResult(item=item, expected_total=expected, ok=diff <= tolerance, diff=diff)
