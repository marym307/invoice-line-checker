# linecheck

A command line tool that checks whether the totals on an invoice's
line items actually add up.

## the problem

Invoice line items usually carry two independent pieces of data: the
inputs (quantity, unit price, discount) and the output (the total for
that line). Nothing forces those to agree. Someone edits the quantity
after the total was already typed in, a discount gets applied twice,
a spreadsheet formula gets dragged over the wrong range - the line
still looks fine at a glance, and the error only surfaces later when
someone reconciles against a bank statement.

`linecheck` reads a CSV of line items and recomputes each total from
scratch (`quantity * unit_price`, minus the discount, plus tax on
what's left after the discount, rounded to cents), then flags any
line where the stated total doesn't match.

## usage

```
$ cat invoice.csv
description,quantity,unit_price,discount_pct,total
Consulting - September,10,150.00,0,1500.00
Widget A,25,4.50,10,101.25
Widget B,3,19.99,0,69.97
Return - Widget A,-5,4.50,10,-20.25

$ python -m linecheck.cli invoice.csv
line 4: 'Widget B' stated 69.97 but expected 59.97 (off by 10.00)
```

Each row needs a `description`, `quantity`, `unit_price`,
`discount_pct` (0-100), and `total`. Quantities and discounts can be
negative or fractional - a negative quantity is treated as a credit
or return, not an error.

An optional `tax_rate` column adds sales tax, calculated on the
amount left after the discount rather than the pre-discount amount.
Rows without the column, or with it left blank, are treated as
untaxed:

```
description,quantity,unit_price,discount_pct,total,tax_rate
Widget A,25,4.50,10,109.35,8
```

Rounding is half-up to the nearest cent, applied once at the end
after both the discount and the tax, which is how the total is
expected to have been calculated in the first place. A stated total
within one cent of the recomputed value is accepted, since different
invoicing systems round per-line amounts slightly differently and
that's not the kind of error this tool is meant to catch.

Exit status is `0` when every line checks out and `1` when at least
one line is flagged or unparsable.

## installing

No dependencies beyond the Python standard library (3.9+). Either run
it directly from a checkout:

```
python -m linecheck.cli invoice.csv
```

or install it locally so the `linecheck` command is on your PATH:

```
pip install -e .
linecheck invoice.csv
```

## running the tests

```
python -m unittest discover -s tests
```

## license

MIT, see LICENSE.
