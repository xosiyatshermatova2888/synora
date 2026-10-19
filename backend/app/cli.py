"""Operator commands, run on the server:

    python -m app.cli make-platform-admin <username>
    python -m app.cli revoke-platform-admin <username>

Platform-admin status gates the subscription-approval console, so it can only
be granted here — there is deliberately no API for it.
"""

import asyncio
import sys

from sqlalchemy import select

from app.database.session import SessionLocal, engine
from app.models.user import User


async def _set_platform_admin(username: str, value: bool) -> int:
    try:
        async with SessionLocal() as session:
            user = await session.scalar(select(User).where(User.username == username.strip()))
            if user is None:
                print(f"No user with username '{username}'.", file=sys.stderr)
                return 1
            user.is_platform_admin = value
            await session.commit()
        print(f"{username}: is_platform_admin = {value}")
        return 0
    finally:
        # Same event loop that opened the connections, or asyncpg complains.
        await engine.dispose()


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("make-platform-admin", "revoke-platform-admin"):
        print(__doc__)
        return 2
    return asyncio.run(_set_platform_admin(argv[2], argv[1] == "make-platform-admin"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
