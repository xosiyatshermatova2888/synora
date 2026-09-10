"""Password reset flow tests (Phase M): request is 202-and-silent for unknown
addresses, tokens are single-use and short-lived, resolving a reset logs the
user out everywhere (all refresh tokens revoked)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.password_reset import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from tests.conftest import TEST_PASSWORD

NEW_PASSWORD = "NewPass987!"


class _CapturedEmail:
    """Replaces `send_email` so tests can read the reset link Payme-less."""

    def __init__(self):
        self.sent = None

    async def __call__(self, to, subject, html_body):
        import re

        m = re.search(r'href=["\']([^"\']+)["\']', html_body)
        self.sent = {"to": to, "subject": subject, "url": m.group(1) if m else None}


@pytest.fixture
def captured():
    cap = _CapturedEmail()
    import app.services.password_reset as svc

    svc.send_email = cap
    return cap


def _token_from(url: str) -> str:
    return parse_qs(urlparse(url).query)["token"][0]


class TestRequest:
    def test_request_existing_user_mails_reset_link(self, client, world, captured):
        res = client.post("/api/v1/auth/password-reset/request", json={"email": world.owner_a.email})
        assert res.status_code == 202
        assert captured.sent is not None
        assert captured.sent["to"] == world.owner_a.email
        assert "token=" in captured.sent["url"]

    def test_request_unknown_email_is_silent_202(self, client, captured):
        res = client.post("/api/v1/auth/password-reset/request", json={"email": "ghost@synora.io"})
        assert res.status_code == 202
        assert captured.sent is None  # no account -> no email, no disclosure


class TestConfirm:
    async def test_confirm_sets_password_and_revokes_all_sessions(self, client, world, db, captured):
        # Steal a session first.
        client.post("/api/v1/auth/login", json={"email": world.owner_a.email, "password": TEST_PASSWORD})
        old_refresh = client.cookies.get(settings.refresh_cookie_name)
        assert old_refresh

        client.post("/api/v1/auth/password-reset/request", json={"email": world.owner_a.email})
        token = _token_from(captured.sent["url"])

        res = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": NEW_PASSWORD},
        )
        assert res.status_code == 204

        user = await db.scalar(select(User).where(User.id == world.owner_a.id))
        await db.refresh(user)  # identity map may hold the pre-reset hash
        from app.core.security import verify_password

        assert verify_password(NEW_PASSWORD, user.password_hash)

        from app.core.security import hash_refresh_token

        old_row = await db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(old_refresh))
        )
        assert old_row is not None

        # Old session must be dead after the reset.
        client.cookies.set(settings.refresh_cookie_name, old_refresh)
        assert client.post("/api/v1/auth/refresh").status_code == 401

        # And the new password actually logs in.
        login = client.post("/api/v1/auth/login", json={"email": world.owner_a.email, "password": NEW_PASSWORD})
        assert login.status_code == 200
        # Old password is rejected.
        stale = client.post("/api/v1/auth/login", json={"email": world.owner_a.email, "password": TEST_PASSWORD})
        assert stale.status_code == 401

    def test_confirm_rejects_garbage_token(self, client, world):
        res = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": "not-a-real-token", "new_password": NEW_PASSWORD},
        )
        assert res.status_code == 401

    async def test_token_is_single_use(self, client, world, db, captured):
        client.post("/api/v1/auth/password-reset/request", json={"email": world.owner_a.email})
        token = _token_from(captured.sent["url"])
        first = client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD})
        assert first.status_code == 204
        second = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "AnotherPass1!"},
        )
        assert second.status_code == 401

    async def test_expired_token_rejected(self, client, world, db, captured):
        client.post("/api/v1/auth/password-reset/request", json={"email": world.owner_a.email})
        token = _token_from(captured.sent["url"])
        row = await db.scalar(select(PasswordResetToken).order_by(PasswordResetToken.created_at.desc()))
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()

        res = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": NEW_PASSWORD},
        )
        assert res.status_code == 401

    async def test_stored_token_is_hashed(self, client, world, db, captured):
        client.post("/api/v1/auth/password-reset/request", json={"email": world.owner_a.email})
        token = _token_from(captured.sent["url"])
        row = await db.scalar(select(PasswordResetToken))
        assert row.token_hash != token  # opaque token, SHA-256 hash stored
        assert row.token_hash == sha256(token.encode()).hexdigest()