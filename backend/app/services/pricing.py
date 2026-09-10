"""Money handling (Section 12A) — the SINGLE place rounding happens.

Rule: round at the order-total level with half-up to the currency's minor unit
(2 dp for UZS/UYU/USD etc.). No call site re-implements rounding; they all go
through `round_money` / `calculate_totals`. No monetary field anywhere is a
float — everything is Decimal(Numeric(12,2)).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MINOR_UNIT = Decimal("0.01")


def round_money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(value).quantize(MINOR_UNIT, rounding=ROUND_HALF_UP)


@dataclass
class OrderTotals:
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal


def calculate_totals(
    items_total: Decimal,
    discount: Decimal = Decimal("0.00"),
    tax_rate: Decimal = Decimal("0.00"),
) -> OrderTotals:
    """Compute subtotal / discount / tax / total with a single half-up rounding.

    `discount` and `tax_rate` are given in the restaurant's currency units /
    percentage. Rounding happens once, here, at the total level.
    """
    subtotal = round_money(items_total)
    discount = round_money(discount) if discount else Decimal("0.00")
    disc_subtotal = subtotal - discount
    tax = round_money(disc_subtotal * tax_rate)
    total = round_money(disc_subtotal + tax)
    return OrderTotals(subtotal=subtotal, discount=discount, tax=tax, total=total)