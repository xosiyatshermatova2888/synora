"""Transactional email delivery (Phase M).

One small swap-able interface: `send_email(to, subject, html_body)`. The
current provider is plain SMTP via `aiosmtplib` (works with any SMTP service —
Resend/SendGrid/Mailgun all expose SMTP). Swapping in an HTTP-only provider
means replacing the body of this module, not touching call sites.

When SMTP is not configured (`settings.email_enabled` is False) the module
falls back to logging the email with enough detail to complete the flow
locally — the README documents that production requires real SMTP credentials.
"""

from __future__ import annotations

import asyncio
import logging

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger("synora.email")


async def send_email(to: str, subject: str, html_body: str) -> None:
    if not settings.email_enabled:
        # Log-only fallback: lets the full password-reset flow run locally
        # without an inbox. Clearly labeled so it's never mistaken for real
        # delivery. The URL is present so the flow is actually testable.
        logger.warning(
            "email not configured — reset link for %s: %s",
            to,
            _extract_link(html_body),
        )
        return

    message = aiosmtplib.email.message_from_string(
        f"Subject: {subject}\nFrom: {settings.smtp_from_email}\n"
        f"To: {to}\nMIME-Version: 1.0\n"
        f"Content-Type: text/html; charset=utf-8\n\n{html_body}"
    )
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        use_tls=settings.smtp_use_tls,
        validate_certs=True,
    )


def _extract_link(html_body: str) -> str:
    import re

    m = re.search(r'href=["\']([^"\']+)["\']', html_body)
    return m.group(1) if m else "(no link found)"


def build_reset_url(token: str, locale: str = "uz") -> str:
    base = settings.public_app_url.rstrip("/")
    return f"{base}/{locale}/reset-password?token={token}"


async def _self_check_imports() -> None:
    # Import guard so the module loads without runtime deps in exotic setups.
    return None


if __name__ == "__main__":
    asyncio.run(send_email("demo@example.com", "Test", "<a href='http://x'>x</a>"))