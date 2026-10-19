"""Split-bill preview — pure calculation over an already-loaded `Order`.

No DB writes and no new model: a split is just "how to divide order.total
before paying it." The cashier settles the result by posting one
`POST /payments` per share (`app/services/payments.py::add_payment`), which is
also how mixed-payment checkout works — split-bill and mixed-payment share one
checkout code path client-side.
"""

from decimal import Decimal

from app.models.order import Order
from app.schemas.split_bill import SplitPreviewOut, SplitPreviewRequest, SplitShare
from app.services.pricing import round_money
from app.utils.errors import BusinessRuleError


def _item_line_total(item) -> Decimal:
    total = item.unit_price * item.quantity
    for modifier in item.modifiers:
        total += modifier.price * modifier.quantity
    return total - item.discount


def preview_split(order: Order, request: SplitPreviewRequest) -> SplitPreviewOut:
    total = round_money(order.total)

    if request.mode == "person":
        if not request.parts:
            raise BusinessRuleError(detail="'parts' is required for mode=person.")
        share = round_money(total / request.parts)
        shares = [share] * (request.parts - 1)
        shares.append(total - sum(shares))  # remainder absorbed into the last share
        return SplitPreviewOut(
            mode="person",
            order_total=total,
            shares=[
                SplitShare(label=f"{i + 1}-mehmon", amount=amount)
                for i, amount in enumerate(shares)
            ],
        )

    if request.mode == "item":
        if not request.item_groups:
            raise BusinessRuleError(detail="'item_groups' is required for mode=item.")
        items_by_id = {item.id: item for item in order.items}
        seen: set = set()
        for group in request.item_groups:
            for item_id in group.order_item_ids:
                if item_id not in items_by_id:
                    raise BusinessRuleError(detail=f"Order item {item_id} not found on this order.")
                if item_id in seen:
                    raise BusinessRuleError(detail=f"Order item {item_id} assigned to more than one group.")
                seen.add(item_id)

        all_items_subtotal = sum((_item_line_total(item) for item in order.items), Decimal("0.00"))
        # Proportion of the order's discount/tax/service-charge each group carries,
        # so a group's share reflects its fair slice of the whole bill, not just
        # its raw item total.
        adjustment_ratio = (
            (total - all_items_subtotal) / all_items_subtotal if all_items_subtotal > 0 else Decimal("0.00")
        )
        shares = []
        for group in request.item_groups:
            group_subtotal = sum(
                (_item_line_total(items_by_id[item_id]) for item_id in group.order_item_ids),
                Decimal("0.00"),
            )
            group_share = round_money(group_subtotal * (Decimal("1.00") + adjustment_ratio))
            shares.append(SplitShare(label=group.label, amount=group_share))
        return SplitPreviewOut(mode="item", order_total=total, shares=shares)

    if request.mode == "amount":
        if not request.amounts:
            raise BusinessRuleError(detail="'amounts' is required for mode=amount.")
        rounded = [round_money(a) for a in request.amounts]
        if round_money(sum(rounded, Decimal("0.00"))) != total:
            raise BusinessRuleError(detail="Amounts must sum exactly to the order total.")
        return SplitPreviewOut(
            mode="amount",
            order_total=total,
            shares=[
                SplitShare(label=f"{i + 1}-ulush", amount=amount)
                for i, amount in enumerate(rounded)
            ],
        )

    raise BusinessRuleError(detail=f"Unknown split mode '{request.mode}'.")
