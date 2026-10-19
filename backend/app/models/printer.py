"""Receipt-printer domain — network (LAN) ESC/POS thermal printers per branch,
and a log of every print attempt (`PrintJob`) so a dead printer is visible and
retryable instead of silently losing a kitchen ticket.

One printer per (branch, role): KITCHEN prints new-order tickets, RECEIPT prints
the cashier's pre-check ("hisob") and final receipt.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, uuid_pk

PRINTER_ROLES = ("KITCHEN", "RECEIPT")
PRINT_JOB_KINDS = ("KITCHEN_TICKET", "ORDER_COPY", "PRECHECK", "RECEIPT", "TEST")
PRINT_JOB_STATUSES = ("PENDING", "PRINTED", "FAILED")
# DIRECT: this server opens the TCP connection (only works when the backend is
# on the restaurant's LAN). AGENT: a small program on a PC in the restaurant
# polls for jobs and forwards them (needed when the backend is in the cloud).
PRINTER_MODES = ("DIRECT", "AGENT")


class Printer(Base, TimestampMixin):
    __tablename__ = "printers"
    __table_args__ = (
        UniqueConstraint("branch_id", "role", name="uq_printers_branch_role"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # Private IPv4 only (validated in schemas/printing.py): the server opens a
    # TCP connection to this address, so it must never be an arbitrary host.
    host: Mapped[str] = mapped_column(String(45), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=9100, nullable=False)
    paper_width: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # RECEIPT printers only: print the final receipt automatically once an
    # order is fully paid.
    auto_print_receipt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mode: Mapped[str] = mapped_column(String(10), default="DIRECT", server_default="DIRECT", nullable=False)
    # RECEIPT printers only: print every NEW order in full (prices, totals) the
    # moment it arrives, so the cashier has the whole order while the kitchen
    # printer shows only what must be cooked.
    auto_print_orders: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False
    )
    printer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("printers.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(10), default="PENDING", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # AGENT-mode jobs: the rendered ESC/POS bytes wait here until the agent
    # confirms the print (then they are cleared). `claimed_at` is the lease so
    # two polls never hand the same job to the agent twice at once.
    payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PrintAgent(Base):
    """Credential for the print agent of one branch (one agent per branch).
    Only the SHA-256 of the token is stored; the token is shown once."""

    __tablename__ = "print_agents"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
