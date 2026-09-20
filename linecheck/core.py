"""Core reconciliation logic for invoice line items.

Kept free of any I/O so it can be unit tested without touching a
filesystem or a CSV parser.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

# Minor-unit decimal places, for currencies that differ from the usual two.
# Anything not listed here is assumed to have two, which covers most of
# ISO 4217 - these are the exceptions worth getting right.
CURRENCY_DECIMALS = {
    "BHD": 3,
    "CLP": 0,
    "DJF": 0,
    "GNF": 0,
    "ISK": 0,
    "JOD": 3,
    "JPY": 0,
    "KMF": 0,
    "KRW": 0,
    "KWD": 3,
    "OMR": 3,
    "PYG": 0,
    "RWF": 0,
    "TND": 3,
    "UGX": 0,
    "VND": 0,
    "VUV": 0,
    "XAF": 0,
    "XOF": 0,
    "XPF": 0,
}
DEFAULT_DECIMALS = 2


def currency_quantum(currency: str) -> Decimal:
    """Return the smallest unit a currency's totals are rounded to.

    Decimal.scaleb(-n) turns a place count directly into a quantizing
    value: 2 -> Decimal('0.01'), 0 -> Decimal('1').
    """
    places = CURRENCY_DECIMALS.get(currency.upper(), DEFAULT_DECIMALS)
    return Decimal(1).scaleb(-places)


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
    invoice_id: str = "1"
    currency: str = "USD"


@dataclass
class LineResult:
    item: LineItem
    expected_total: Decimal
    ok: bool
    diff: Decimal


@dataclass
class InvoiceResult:
    invoice_id: str
    stated_total: Decimal
    line_item_sum: Decimal
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
    currency: str = "USD",
) -> Decimal:
    """Return the line total a correctly written invoice should show.

    Discount is applied to the raw quantity*unit_price amount, tax is
    applied to what's left after the discount (not the pre-discount
    amount - charging tax on a discount you didn't actually pay would
    be wrong), and the result is rounded once, at the very end, using
    half-up rounding - that's how invoices are written by hand and by
    most billing software, not the banker's rounding Decimal uses by
    default. It's rounded to the currency's smallest unit, which is a
    cent for most currencies but not all - a yen total has no decimal
    places at all.
    """
    if discount_pct < 0 or discount_pct > 100:
        raise LineItemError(f"discount_pct out of range: {discount_pct}")
    if tax_rate < 0:
        raise LineItemError(f"tax_rate out of range: {tax_rate}")
    raw = quantity * unit_price
    discounted = raw * (Decimal(100) - discount_pct) / Decimal(100)
    taxed = discounted * (Decimal(100) + tax_rate) / Decimal(100)
    return taxed.quantize(currency_quantum(currency), rounding=ROUND_HALF_UP)


def check_line(item: LineItem, tolerance: Optional[Decimal] = None) -> LineResult:
    """Compare a line item's stated total to what it should be.

    A one-unit tolerance (one cent, or one yen, depending on the line's
    currency) is allowed by default because different invoicing systems
    round per-line amounts slightly differently; that's noise, not the
    kind of error this tool is meant to catch.
    """
    expected = expected_line_total(
        item.quantity, item.unit_price, item.discount_pct, item.tax_rate, item.currency
    )
    if tolerance is None:
        tolerance = currency_quantum(item.currency)
    diff = (item.stated_total - expected).copy_abs()
    return LineResult(item=item, expected_total=expected, ok=diff <= tolerance, diff=diff)


def check_invoice_total(
    line_items: list, stated_total: Decimal, tolerance: Optional[Decimal] = None
) -> InvoiceResult:
    """Compare an invoice's stated grand total to its line items added up.

    This catches a different mistake than check_line: every line can be
    individually correct (quantity * price, minus discount, matches its
    own total) while the invoice as a whole is still wrong, because a
    line was left off, entered twice, or the grand total was hand-typed
    instead of summed.
    """
    line_item_sum = sum((item.stated_total for item in line_items), Decimal("0"))
    if tolerance is None:
        currency = line_items[0].currency if line_items else "USD"
        tolerance = currency_quantum(currency)
    diff = (stated_total - line_item_sum).copy_abs()
    invoice_id = line_items[0].invoice_id if line_items else ""
    return InvoiceResult(
        invoice_id=invoice_id,
        stated_total=stated_total,
        line_item_sum=line_item_sum,
        ok=diff <= tolerance,
        diff=diff,
    )
