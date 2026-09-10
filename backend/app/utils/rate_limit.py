"""In-process, per-IP + per-account login rate limiter.

Keeps a sliding window of failed attempts keyed by account and by IP. On
breach it returns 429 and short-circuits before password verification even
runs (so it never leaks password timing).

NOTE: this is a single-process implementation, appropriate for one uvicorn
worker in dev. When the API scales to multiple workers/replicas, swap the
store for Redis (the interface stays the same). See README "Architecture
decisions".
"""

import threading
import time
from collections import defaultdict, deque

from app.core.config import settings


class LoginRateLimiter:
    def __init__(
        self,
        max_attempts: int = settings.login_rate_limit_max_attempts,
        window_seconds: int = settings.login_rate_limit_window_seconds,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failed: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str) -> None:
        cutoff = time.monotonic() - self.window_seconds
        q = self._failed[key]
        while q and q[0] < cutoff:
            q.popleft()

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            self._prune(key)
            return len(self._failed[key]) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._prune(key)
            self._failed[key].append(time.monotonic())

    def record_success(self, key: str) -> None:
        with self._lock:
            self._failed.pop(key, None)


login_limiter = LoginRateLimiter()


def login_blocked(email: str, ip: str) -> bool:
    return login_limiter.is_blocked(f"email:{email}") or login_limiter.is_blocked(
        f"ip:{ip}"
    )


def record_login_failure(email: str, ip: str) -> None:
    login_limiter.record_failure(f"email:{email}")
    login_limiter.record_failure(f"ip:{ip}")


def record_login_success(email: str, ip: str) -> None:
    login_limiter.record_success(f"email:{email}")
    login_limiter.record_success(f"ip:{ip}")


# ---------------------------------------------------------------------------
# General per-IP API rate limiter (Section 18) — protects against abusive
# clients beyond the auth-specific limit above. In-memory, single-process: swap
# for Redis when scaling to multiple workers (same interface).
# ---------------------------------------------------------------------------
GENERAL_LIMIT_MAX: int = 600
GENERAL_LIMIT_WINDOW_SECONDS: int = 60

_general_limiter = LoginRateLimiter(
    max_attempts=GENERAL_LIMIT_MAX, window_seconds=GENERAL_LIMIT_WINDOW_SECONDS
)


def api_limit_hit(ip: str) -> bool:
    return _general_limiter.is_blocked(ip)


def record_api_call(ip: str) -> None:
    # Only track after the first N hits so healthy traffic isn't kept in memory.
    _general_limiter._prune(ip)
    q = _general_limiter._failed[ip]
    if len(q) < GENERAL_LIMIT_MAX:
        q.append(time.monotonic())