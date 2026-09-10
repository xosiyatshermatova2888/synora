"""Tenant (restaurant) scoping — the CONCRETE isolation mechanism.

Every tenant-scoped repository MUST inherit from `TenantScopedRepository`
(see `app/repositories/base.py`) whose `get/list/update/delete` methods require
a `restaurant_id` argument and apply it as a WHERE clause before any other
filter. There is NO code path that queries a tenant-scoped table without a
restaurant_id.

The runtime `get_current_tenant` dependency (app/api/deps.py) extracts
`restaurant_id` from the authenticated user's JWT claims — never from a
request body or query parameter that the client could tamper with.

Rule of thumb for every new module:
    - entity table gets a NOT NULL `restaurant_id` column + index,
    - its repository extends TenantScopedRepository,
    - its routes inject `current_tenant` and hand it to the repository.
Cross-tenant access must surface as HTTP 404 (never 403), so resource presence
is never disclosed.
"""