import logging
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

    # Keep noisy libs quieter.
    for noisy in ("uvicorn.access", "watchfiles", "aiosqlite"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)