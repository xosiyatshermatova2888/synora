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


DISCOUNT_TYPES = ("FIXED", "PERCENT")


def resolve_discount(
    base_amount: Decimal, discount_type: str, discount_value: Decimal
) -> Decimal:
    """Turn a FIXED currency amount or a PERCENT (0-100) into a currency amount.

    Never exceeds `base_amount` — a 100%+ percent or an over-sized fixed amount
    both clamp to a full discount rather than producing a negative total.
    """
    if not discount_value:
        return Decimal("0.00")
    if discount_type == "PERCENT":
        amount = round_money(base_amount * discount_value / Decimal("100"))
    else:
        amount = round_money(discount_value)
    return min(amount, round_money(base_amount)) if base_amount > 0 else Decimal("0.00")


@dataclass
class OrderTotals:
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    service_charge: Decimal
    total: Decimal


def calculate_totals(
    items_total: Decimal,
    discount: Decimal = Decimal("0.00"),
    tax_rate: Decimal = Decimal("0.00"),
    service_charge_rate: Decimal = Decimal("0.00"),
) -> OrderTotals:
    """Compute subtotal / discount / tax / service_charge / total with a single
    half-up rounding.

    `discount` is a currency amount; `tax_rate` / `service_charge_rate` are
    fractions (0.10 = 10%) applied to the post-discount subtotal. Tax and
    service charge are kept as separate line items — one is a government
    levy, the other is a house/staff charge — and never merged into a single
    number. Rounding happens once, here, at the total level.
    """
    subtotal = round_money(items_total)
    discount = round_money(discount) if discount else Decimal("0.00")
    disc_subtotal = subtotal - discount
    tax = round_money(disc_subtotal * tax_rate)
    service_charge = round_money(disc_subtotal * service_charge_rate)
    total = round_money(disc_subtotal + tax + service_charge)
    return OrderTotals(
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        service_charge=service_charge,
        total=total,
    )