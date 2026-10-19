# Importing every model here registers them on Base.metadata so Alembic
# autogenerate and `Base.metadata.create_all` see the full schema.
from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.customer import Customer
from app.models.expense import Expense, EXPENSE_CATEGORIES
from app.models.idempotency import IdempotencyKey
from app.models.inventory import InventoryItem, InventoryTransaction, INVENTORY_TRANSACTION_TYPES
from app.models.kitchen import (
    KitchenStation,
    KitchenTicket,
    KITCHEN_TICKET_ACTIVE,
    KITCHEN_TICKET_STATUSES,
)
from app.models.menu import Category, Modifier, ModifierGroup, Product, product_modifier_groups
from app.models.notification import Notification, NOTIFICATION_TYPES
from app.models.order import Order, OrderItem, OrderItemModifier, ORDER_STATUSES, ORDER_SOURCES, KITCHEN_STATUSES
from app.models.printer import (
    Printer,
    PrintAgent,
    PrintJob,
    PRINTER_MODES,
    PRINTER_ROLES,
    PRINT_JOB_KINDS,
    PRINT_JOB_STATUSES,
)
from app.models.payment import CashShift, Payment, PAYMENT_METHODS, CASH_SHIFT_STATUSES
from app.models.refresh_token import RefreshToken
from app.models.restaurant import Restaurant
from app.models.subscription import SubscriptionPayment, PAYMENT_STATUSES, BILLING_CYCLES
from app.models.table import Table
from app.models.telegram_session import TelegramSession
from app.models.user import Permission, Role, role_permissions, user_roles, User

__all__ = [
    "AuditLog",
    "Branch",
    "CASH_SHIFT_STATUSES",
    "CashShift",
    "Category",
    "Customer",
    "EXPENSE_CATEGORIES",
    "Expense",
    "IdempotencyKey",
    "INVENTORY_TRANSACTION_TYPES",
    "InventoryItem",
    "InventoryTransaction",
    "KITCHEN_STATUSES",
    "KITCHEN_TICKET_ACTIVE",
    "KITCHEN_TICKET_STATUSES",
    "KitchenStation",
    "KitchenTicket",
    "Modifier",
    "ModifierGroup",
    "NOTIFICATION_TYPES",
    "Notification",
    "ORDER_SOURCES",
    "ORDER_STATUSES",
    "Order",
    "OrderItem",
    "OrderItemModifier",
    "PAYMENT_METHODS",
    "PRINTER_MODES",
    "PRINTER_ROLES",
    "PRINT_JOB_KINDS",
    "PRINT_JOB_STATUSES",
    "Payment",
    "Permission",
    "PrintAgent",
    "PrintJob",
    "Printer",
    "Product",
    "RefreshToken",
    "Restaurant",
    "Role",
    "SubscriptionPayment",
    "Table",
    "TelegramSession",
    "User",
    "product_modifier_groups",
    "role_permissions",
    "user_roles",
]