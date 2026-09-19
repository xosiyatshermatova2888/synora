"""Staff (team member) API — POST/GET /users.

Without this endpoint, an owner has no way to give a waiter/cashier/kitchen
their own login: /auth/register always creates a brand-new restaurant. These
tests pin down create + list + the RBAC + tenant-isolation boundaries around it.
"""

from __future__ import annotations

from tests.conftest import TEST_PASSWORD, owner_headers, waiter_headers


class TestCreateStaff:
    def test_owner_can_create_waiter(self, client, world):
        res = client.post(
            "/api/v1/users",
            headers=owner_headers(world),
            json={
                "full_name": "New Waiter",
                "username": "new_waiter",
                "password": "NewPass123!",
                "role": "WAITER",
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["username"] == "new_waiter"
        assert body["roles"] == ["WAITER"]
        assert body["is_active"] is True

    def test_created_staff_can_log_in_with_correct_permissions(self, client, world):
        res = client.post(
            "/api/v1/users",
            headers=owner_headers(world),
            json={
                "full_name": "New Waiter",
                "username": "login_waiter",
                "password": "NewPass123!",
                "role": "WAITER",
            },
        )
        assert res.status_code == 201, res.text

        login = client.post(
            "/api/v1/auth/login",
            json={"username": "login_waiter", "password": "NewPass123!"},
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]

        me = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me.status_code == 200
        perms = set(me.json()["permissions"])
        assert {"orders.read", "orders.create", "orders.update", "menu.read"} <= perms
        assert "finance.read" not in perms
        assert "users.manage" not in perms

    def test_waiter_cannot_create_staff(self, client, world):
        res = client.post(
            "/api/v1/users",
            headers=waiter_headers(world),
            json={
                "full_name": "Sneaky",
                "username": "sneaky",
                "password": "NewPass123!",
                "role": "CASHIER",
            },
        )
        assert res.status_code == 403

    def test_duplicate_username_rejected(self, client, world):
        res = client.post(
            "/api/v1/users",
            headers=owner_headers(world),
            json={
                "full_name": "Duplicate",
                "username": world.waiter_a.username,
                "password": "NewPass123!",
                "role": "CASHIER",
            },
        )
        assert res.status_code == 409

    def test_owner_role_rejected(self, client, world):
        # role is a closed Literal in the schema — OWNER/ADMIN can only be
        # granted via /auth/register, never through this endpoint.
        res = client.post(
            "/api/v1/users",
            headers=owner_headers(world),
            json={
                "full_name": "Power Grab",
                "username": "poweruser",
                "password": "NewPass123!",
                "role": "OWNER",
            },
        )
        assert res.status_code == 422


class TestListStaff:
    def test_owner_lists_own_restaurant_staff_only(self, client, world):
        res = client.get("/api/v1/users", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        usernames = {u["username"] for u in res.json()}
        assert world.owner_a.username in usernames
        assert world.waiter_a.username in usernames
        # Tenant isolation: restaurant B's users must never leak into A's list.
        assert world.owner_b.username not in usernames
        assert world.waiter_b.username not in usernames

    def test_waiter_cannot_list_staff(self, client, world):
        res = client.get("/api/v1/users", headers=waiter_headers(world))
        assert res.status_code == 403
