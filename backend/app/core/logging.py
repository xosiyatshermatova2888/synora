import logging
import re
import sys
from contextvars import ContextVar

from .config import settings

# Correlate every log line of a single request across layers. Set per-request
# in app/main.py middleware; falls back to "-" for non-HTTP paths.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class AppNameFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.app_name = settings.app_name
        return True


# WebSocket clients authenticate with `?token=<access JWT>`, and uvicorn logs the
# full request path. Mask it so a log file never holds a usable credential.
_SECRET_QUERY = re.compile(r"(?i)\b(token|access_token|refresh_token|secret)=[^&\s\"']+")


def redact_secrets(text: str) -> str:
    return _SECRET_QUERY.sub(lambda m: f"{m.group(1)}=***", text)


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact_secrets(a) if isinstance(a, str) else a for a in record.args)
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.addFilter(AppNameFilter())
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(request_id)s | %(name)s | %(message)s"
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # httpx/httpcore log full request URLs, and a Telegram bot token is part of
    # its API URL (/bot<token>/method) — never let it reach the logs.
    # Keep noisy libs quieter.
    for noisy in ("uvicorn.access", "watchfiles", "aiosqlite", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # uvicorn logs "WebSocket /path?token=... [accepted]" on `uvicorn.error`.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).addFilter(RedactSecretsFilter())
    handler.addFilter(RedactSecretsFilter())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)