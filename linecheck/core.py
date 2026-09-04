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
    tax_rate: Decimal = Decimal("0")


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


def expected_line_total(
    quantity: Decimal,
    unit_price: Decimal,
    discount_pct: Decimal,
    tax_rate: Decimal = Decimal("0"),
) -> Decimal:
    """Return the line total a correctly written invoice should show.

    Discount is applied to the raw quantity*unit_price amount, tax is
    applied to what's left after the discount (not the pre-discount
    amount - charging tax on a discount you didn't actually pay would
    be wrong), and the result is rounded to cents once, at the very
    end, using half-up rounding - that's how invoices are written by
    hand and by most billing software, not the banker's rounding
    Decimal uses by default.
    """
    if discount_pct < 0 or discount_pct > 100:
        raise LineItemError(f"discount_pct out of range: {discount_pct}")
    if tax_rate < 0:
        raise LineItemError(f"tax_rate out of range: {tax_rate}")
    raw = quantity * unit_price
    discounted = raw * (Decimal(100) - discount_pct) / Decimal(100)
    taxed = discounted * (Decimal(100) + tax_rate) / Decimal(100)
    return taxed.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def check_line(item: LineItem, tolerance: Decimal = TWO_PLACES) -> LineResult:
    """Compare a line item's stated total to what it should be.

    A one-cent tolerance is allowed by default because different
    invoicing systems round per-line amounts slightly differently;
    that's noise, not the kind of error this tool is meant to catch.
    """
    expected = expected_line_total(
        item.quantity, item.unit_price, item.discount_pct, item.tax_rate
    )
    diff = (item.stated_total - expected).copy_abs()
    return LineResult(item=item, expected_total=expected, ok=diff <= tolerance, diff=diff)
