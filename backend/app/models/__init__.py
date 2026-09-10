# Importing every model here registers them on Base.metadata so Alembic
# autogenerate and `Base.metadata.create_all` see the full schema.
from app.models.branch import Branch
from app.models.idempotency import IdempotencyKey
from app.models.kitchen import (
    KitchenStation,
    KitchenTicket,
    KITCHEN_TICKET_ACTIVE,
    KITCHEN_TICKET_STATUSES,
)
from app.models.menu import Category, Modifier, ModifierGroup, Product, product_modifier_groups
from app.models.order import Order, OrderItem, OrderItemModifier, ORDER_STATUSES, ORDER_SOURCES, KITCHEN_STATUSES
from app.models.password_reset import PasswordResetToken
from app.models.payment import CashShift, Payment, PAYMENT_METHODS, CASH_SHIFT_STATUSES
from app.models.refresh_token import RefreshToken
from app.models.restaurant import Restaurant
from app.models.table import Table
from app.models.user import Permission, Role, role_permissions, user_roles, User

__all__ = [
    "Branch",
    "CASH_SHIFT_STATUSES",
    "CashShift",
    "Category",
    "IdempotencyKey",
    "KITCHEN_STATUSES",
    "KITCHEN_TICKET_ACTIVE",
    "KITCHEN_TICKET_STATUSES",
    "KitchenStation",
    "KitchenTicket",
    "Modifier",
    "ModifierGroup",
    "ORDER_SOURCES",
    "ORDER_STATUSES",
    "Order",
    "OrderItem",
    "OrderItemModifier",
    "PAYMENT_METHODS",
    "PasswordResetToken",
    "Payment",
    "Permission",
    "Product",
    "RefreshToken",
    "Restaurant",
    "Role",
    "Table",
    "User",
    "product_modifier_groups",
    "role_permissions",
    "user_roles",
]