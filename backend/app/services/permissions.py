"""Idempotent bootstrap of the GLOBAL permissions + system-role templates.

This is foundation, not demo data: the `permissions` table is global by design
(Section 7A) and system roles are templates shared by every tenant. Demo
content (a restaurant, users, menu, tables) lives in `app/utils/seed.py`.

Never seeds per-tenant rows. Calling this on startup or before registration is
safe — existence checks make it idempotent.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ROLE_TEMPLATES, ALL_PERMISSIONS
from app.models.user import Permission, Role, role_permissions

PERMISSION_DESCRIPTIONS = {
    "orders.read": "View orders",
    "orders.create": "Create orders",
    "orders.update": "Update orders",
    "orders.cancel": "Cancel orders",
    "payments.create": "Record payments and settle orders",
    "menu.read": "View menu",
    "menu.create": "Create categories and products",
    "menu.update": "Update categories and products",
    "menu.delete": "Delete categories and products",
    "inventory.read": "View inventory",
    "inventory.manage": "Manage inventory and recipes",
    "finance.read": "View finance and payments",
    "finance.manage": "Manage payments and cash shifts",
    "users.read": "View users",
    "users.manage": "Manage users and roles",
    "analytics.read": "View analytics",
}


async def ensure_system_permissions_and_roles(session: AsyncSession) -> dict[str, Role]:
    """Create missing permissions and system roles. Returns system roles by name."""
    existing_perms = set(
        await session.scalars(select(Permission.code))
    )
    for code in ALL_PERMISSIONS:
        if code not in existing_perms:
            session.add(
                Permission(code=code, description=PERMISSION_DESCRIPTIONS.get(code))
            )
    await session.flush()

    perm_rows = {p.code: p for p in (await session.scalars(select(Permission))).all()}

    existing_roles = {
        r.name: r for r in (await session.scalars(select(Role))).all()
        if r.is_system_role and r.restaurant_id is None
    }

    roles: dict[str, Role] = {}
    for name, codes in ROLE_TEMPLATES.items():
        role = existing_roles.get(name)
        if role is None:
            role = Role(
                name=name, is_system_role=True, restaurant_id=None
            )
            session.add(role)
            await session.flush()
        # Sync grants so template changes propagate.
        await session.execute(
            role_permissions.delete().where(role_permissions.c.role_id == role.id)
        )
        for code in codes:
            await session.execute(
                role_permissions.insert().values(
                    role_id=role.id, permission_id=perm_rows[code].id
                )
            )
        roles[name] = role

    await session.flush()
    return roles