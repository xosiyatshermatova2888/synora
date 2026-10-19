"""SYNORA — permission constant registry.

Single source of truth for permission codes. Seeded once, globally, and never
per-tenant. Roles reference these codes via the `role_permissions` join table
(see Section 7A of the master spec). The ONLY place permission logic lives is
the `require_permission` dependency in `app/api/deps.py`.

Conventions: `<module>.<action>` in lower-case. Adding a new permission:
1. add the code here,
2. add a row to the `permissions` table (seed script),
3. grant it to roles in the seed data.
"""

from enum import Enum


class Permission(str, Enum):
    # orders
    ORDERS_READ = "orders.read"
    ORDERS_CREATE = "orders.create"
    ORDERS_UPDATE = "orders.update"
    ORDERS_CANCEL = "orders.cancel"
    ORDERS_DISCOUNT = "orders.discount"

    # menu
    MENU_READ = "menu.read"
    MENU_CREATE = "menu.create"
    MENU_UPDATE = "menu.update"
    MENU_DELETE = "menu.delete"

    # inventory
    INVENTORY_READ = "inventory.read"
    INVENTORY_MANAGE = "inventory.manage"

    # finance / payments
    FINANCE_READ = "finance.read"
    FINANCE_MANAGE = "finance.manage"
    PAYMENTS_CREATE = "payments.create"  # record a payment / settle an order

    # users
    USERS_READ = "users.read"
    USERS_MANAGE = "users.manage"

    # analytics
    ANALYTICS_READ = "analytics.read"


ALL_PERMISSIONS = [p.value for p in Permission]


# Role templates are declared in code (not the DB) so that permission grants
# are diffable and testable. Rows are still created in DB for joins.
ROLE_TEMPLATES: dict[str, list[str]] = {
    "OWNER": ALL_PERMISSIONS,
    "ADMIN": ALL_PERMISSIONS,
    "MANAGER": [
        Permission.ORDERS_READ.value,
        Permission.ORDERS_UPDATE.value,
        Permission.ORDERS_CANCEL.value,
        Permission.ORDERS_DISCOUNT.value,
        Permission.PAYMENTS_CREATE.value,
        Permission.MENU_READ.value,
        Permission.MENU_UPDATE.value,
        Permission.INVENTORY_READ.value,
        Permission.INVENTORY_MANAGE.value,
        Permission.FINANCE_READ.value,
        Permission.USERS_READ.value,
        Permission.ANALYTICS_READ.value,
    ],
    "CASHIER": [
        Permission.ORDERS_READ.value,
        Permission.ORDERS_CREATE.value,
        Permission.ORDERS_UPDATE.value,
        Permission.ORDERS_CANCEL.value,
        Permission.ORDERS_DISCOUNT.value,
        Permission.PAYMENTS_CREATE.value,
        Permission.FINANCE_READ.value,
    ],
    "WAITER": [
        Permission.ORDERS_READ.value,
        Permission.ORDERS_CREATE.value,
        Permission.ORDERS_UPDATE.value,
        # Needed to browse products/categories while building an order — a
        # waiter could not see the menu at all without this (menu.* write
        # actions stay OWNER/MANAGER-only).
        Permission.MENU_READ.value,
    ],
    "KITCHEN": [Permission.ORDERS_READ.value, Permission.ORDERS_UPDATE.value],
    "ACCOUNTANT": [Permission.FINANCE_READ.value, Permission.ANALYTICS_READ.value],
}