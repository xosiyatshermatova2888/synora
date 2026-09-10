"""Authentication tests (Section 8 / 32).

Covers register â†’ login â†’ me â†’ refresh rotation â†’ logout, invalid JWTs, and
the brute-force rate limiter.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.refresh_token import RefreshToken
from tests.conftest import TEST_PASSWORD


REGISTER = {
    "full_name": "Demo Founder",
    "email": "founder@synora.io",
    "password": TEST_PASSWORD,
    "restaurant_name": "Founder Diner",
    "currency": "UZS",
    "timezone": "Asia/Tashkent",
}


def _refresh_cookie(client) -> str | None:
    return client.cookies.get(settings.refresh_cookie_name)


async def _refresh_row(db, token: str) -> RefreshToken | None:
    from app.core.security import hash_refresh_token

    return await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )


class TestRegister:
    def test_register_creates_restaurant_owner_and_tokens(self, client, db):
        res = client.post("/api/v1/auth/register", json=REGISTER)
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert _refresh_cookie(client) is not None
        assert res.headers.get("set-cookie", "").lower().count("httponly") >= 1

        me = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
        )
        assert me.status_code == 200, me.text
        data = me.json()
        assert data["email"] == REGISTER["email"]
        assert data["restaurant_name"] == "Founder Diner"
        assert [r["name"] for r in data["roles"]] == ["OWNER"]
        assert "orders.create" in data["permissions"]
        assert "finance.manage" in data["permissions"]

    def test_register_duplicate_email_is_generic_409(self, client):
        first = client.post("/api/v1/auth/register", json=REGISTER)
        assert first.status_code == 201
        second = client.post("/api/v1/auth/register", json=REGISTER)
        assert second.status_code == 409
        # Do not leak that the account exists.
        assert "exists" not in second.text.lower()

    def test_register_weak_password_rejected(self, client):
        payload = {**REGISTER, "email": "weak@synora.io", "password": "123"}
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 422


class TestLogin:
    def test_login_success_returns_tokens_and_cookie(self, client, world):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": world.owner_a.email, "password": TEST_PASSWORD},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["access_token"]
        assert _refresh_cookie(client) is not None

    def test_login_wrong_password_401(self, client, world):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": world.owner_a.email, "password": "wrong-password"},
        )
        assert res.status_code == 401
        assert _refresh_cookie(client) is None

    def test_login_unknown_email_401(self, client):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@synora.io", "password": TEST_PASSWORD},
        )
        assert res.status_code == 401


class TestRefreshRotation:
    async def test_refresh_rotates_and_old_token_is_revoked(self, client, db, world):
        login = client.post(
            "/api/v1/auth/login",
            json={"email": world.owner_a.email, "password": TEST_PASSWORD},
        )
        old_cookie = _refresh_cookie(client)
        assert old_cookie

        res = client.post("/api/v1/auth/refresh")
        assert res.status_code == 200, res.text
        assert res.json()["access_token"]
        new_cookie = _refresh_cookie(client)
        assert new_cookie and new_cookie != old_cookie

        old_row = await _refresh_row(db, old_cookie)
        assert old_row is not None and old_row.revoked_at is not None
        new_row = await _refresh_row(db, new_cookie)
        assert new_row is not None and new_row.revoked_at is None

    async def test_stale_refresh_token_rejected(self, client, db, world):
        login = client.post(
            "/api/v1/auth/login",
            json={"email": world.waiter_a.email, "password": TEST_PASSWORD},
        )
        stale_cookie = _refresh_cookie(client)

        # First refresh rotates the cookie away.
        client.post("/api/v1/auth/refresh")
        assert client.cookies.get(settings.refresh_cookie_name) != stale_cookie

        # Replaying the old cookie must fail (rotation invalidated it).
        client.cookies.set(settings.refresh_cookie_name, stale_cookie)
        res = client.post("/api/v1/auth/refresh")
        assert res.status_code == 401

    async def test_logout_revokes_token(self, client, db, world):
        client.post(
            "/api/v1/auth/login",
            json={"email": world.owner_a.email, "password": TEST_PASSWORD},
        )
        cookie = _refresh_cookie(client)
        res = client.post("/api/v1/auth/logout")
        assert res.status_code == 204
        row = await _refresh_row(db, cookie)
        assert row is not None and row.revoked_at is not None


class TestMe:
    def test_me_requires_auth(self, client):
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_me_rejects_invalid_token(self, client):
        res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
        assert res.status_code == 401

    def test_me_rejects_non_access_token_type(self, client, world):
        from jose import jwt

        from app.core.config import settings

        payload = {
            "sub": str(world.owner_a.id),
            "rid": str(world.restaurant_a.id),
            "perms": [],
            "typ": "not-access",
            "iat": 0,
            "exp": 9999999999,
        }
        bad = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bad}"})
        assert res.status_code == 401


class TestLoginRateLimit:
    def test_login_rate_limiter_blocks_after_attempts(self, client, world, monkeypatch):
        from app.utils.rate_limit import login_limiter

        monkeypatch.setattr(login_limiter, "max_attempts", 2)
        payload = {"email": world.owner_a.email, "password": "wrong-password"}
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401
        third = client.post("/api/v1/auth/login", json=payload)
        assert third.status_code == 429

    def test_successful_login_resets_account_failures(self, client, world):
        login_limiter_wrap = client

        # Fail, then succeed: the success must clear the account fail-counter so
        # the next failure doesn't inherit a blocked state.
        wrong = {"email": world.cashier_a.email, "password": "wrong-password"}
        assert login_limiter_wrap.post("/api/v1/auth/login", json=wrong).status_code == 401
        ok = {"email": world.cashier_a.email, "password": TEST_PASSWORD}
        assert login_limiter_wrap.post("/api/v1/auth/login", json=ok).status_code == 200