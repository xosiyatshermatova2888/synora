"""Print agent plumbing: per-branch credential + the poll/result protocol.

The agent is a tiny script on a PC inside the restaurant (scripts/print_agent.py).
It only ever makes OUTBOUND HTTPS calls to this server, so no router port needs
opening: it polls for jobs, writes the bytes to the LAN printer (host/port are
part of the job), and reports back.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.printer import Printer, PrintAgent, PrintJob
from app.utils.errors import NotFoundError, UnauthorizedError

LEASE = timedelta(seconds=30)  # a delivered job is not re-sent within this window
ONLINE_WITHIN = timedelta(seconds=45)  # "online" if it polled this recently
MAX_ATTEMPTS = 3
STALE_AFTER = timedelta(hours=6)  # a ticket older than this is no longer useful
POLL_BATCH = 10


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware(moment: datetime | None) -> datetime | None:
    return moment.replace(tzinfo=timezone.utc) if moment is not None and moment.tzinfo is None else moment


async def rotate_token(session: AsyncSession, restaurant_id: uuid.UUID, branch_id: uuid.UUID) -> str:
    branch = await session.scalar(
        select(Branch).where(Branch.restaurant_id == restaurant_id, Branch.id == branch_id)
    )
    if branch is None:
        raise NotFoundError(detail="Branch not found in this restaurant.")
    token = "pa_" + secrets.token_urlsafe(32)
    agent = await session.scalar(select(PrintAgent).where(PrintAgent.branch_id == branch_id))
    if agent is None:
        agent = PrintAgent(restaurant_id=restaurant_id, branch_id=branch_id, token_hash=_hash(token))
        session.add(agent)
    else:  # rotating invalidates the old token immediately
        agent.token_hash, agent.last_seen_at = _hash(token), None
    await session.commit()
    return token


async def status(session: AsyncSession, restaurant_id: uuid.UUID, branch_id: uuid.UUID) -> dict:
    agent = await session.scalar(
        select(PrintAgent).where(PrintAgent.restaurant_id == restaurant_id, PrintAgent.branch_id == branch_id)
    )
    seen = _aware(agent.last_seen_at) if agent else None
    online = bool(seen and datetime.now(timezone.utc) - seen < ONLINE_WITHIN)
    return {"configured": agent is not None, "last_seen_at": seen, "online": online}


async def authenticate(session: AsyncSession, token: str | None) -> PrintAgent:
    if not token:
        raise UnauthorizedError(detail="Print agent token required.")
    agent = await session.scalar(select(PrintAgent).where(PrintAgent.token_hash == _hash(token)))
    if agent is None:
        raise UnauthorizedError(detail="Invalid print agent token.")
    return agent


async def poll(session: AsyncSession, agent: PrintAgent) -> list[dict]:
    now = datetime.now(timezone.utc)
    agent.last_seen_at = now

    rows = (
        await session.execute(
            select(PrintJob, Printer)
            .join(Printer, Printer.id == PrintJob.printer_id)
            .where(
                PrintJob.restaurant_id == agent.restaurant_id,
                PrintJob.branch_id == agent.branch_id,
                PrintJob.status == "PENDING",
                PrintJob.payload.is_not(None),
                Printer.mode == "AGENT",
                Printer.is_active.is_(True),
            )
            .order_by(PrintJob.created_at)
            .limit(POLL_BATCH * 3)
        )
    ).all()

    out: list[dict] = []
    for job, printer in rows:
        if now - _aware(job.created_at) > STALE_AFTER:
            job.status, job.error, job.payload = "FAILED", "Expired: the print agent was offline too long.", None
            continue
        claimed = _aware(job.claimed_at)
        if claimed is not None and now - claimed < LEASE:
            continue
        if len(out) >= POLL_BATCH:
            break
        job.claimed_at = now
        job.attempts += 1
        out.append(
            {
                "id": job.id,
                "host": printer.host,
                "port": printer.port,
                "data_b64": base64.b64encode(job.payload).decode("ascii"),
            }
        )
    await session.commit()
    return out


async def report_result(
    session: AsyncSession, agent: PrintAgent, job_id: uuid.UUID, ok: bool, error: str | None
) -> PrintJob:
    # Tenant + branch scoping come from the agent's own credential, never the body.
    job = await session.scalar(
        select(PrintJob).where(
            PrintJob.id == job_id,
            PrintJob.restaurant_id == agent.restaurant_id,
            PrintJob.branch_id == agent.branch_id,
        )
    )
    if job is None:
        raise NotFoundError(detail="Print job not found.")
    if job.status != "PENDING":  # duplicate / late report: keep the first outcome
        return job
    if ok:
        job.status, job.error, job.payload = "PRINTED", None, None
        job.printed_at = datetime.now(timezone.utc)
    else:
        job.error = (error or "Printer did not accept the job.")[:500]
        if job.attempts >= MAX_ATTEMPTS:
            job.status, job.payload = "FAILED", None
        # else: stays PENDING with claimed_at as the backoff, so it is retried
        # after the lease instead of hammering a dead printer.
    await session.commit()
    return job
