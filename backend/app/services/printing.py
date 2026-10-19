"""Network receipt printing: kitchen tickets, cashier pre-check and receipt.

Printing is a side effect of an order action, never part of its transaction:
`schedule()` records a `PrintJob`, then sends it either as a fire-and-forget task
(kitchen tickets) or inline (explicit cashier button, so the UI can show the
error). A dead printer can therefore never fail or slow down an order — the job
just ends FAILED and can be retried from Settings.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import SessionLocal
from app.integrations import escpos
from app.models.branch import Branch
from app.models.order import Order
from app.models.printer import Printer, PrintJob
from app.models.restaurant import Restaurant
from app.schemas.printing import PrinterCreate, PrinterUpdate
from app.services import audit as audit_service
from app.utils.errors import BusinessRuleError, ConflictError, NotFoundError

logger = logging.getLogger("synora.printing")

SEND_ATTEMPTS = 3
_tasks: set[asyncio.Task] = set()

_METHOD_LABEL = {"CASH": "Naqd", "CARD": "Karta", "TRANSFER": "O'tkazma", "QR": "QR", "PAYME": "Payme"}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _money(value: Decimal | str, currency: str) -> str:
    return f"{Decimal(value):,.0f}".replace(",", " ") + f" {currency}"


def _stamp(moment: datetime, tz_name: str) -> str:
    try:
        zone = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        zone = timezone.utc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(zone).strftime("%d.%m.%Y %H:%M")


def _header(doc: escpos.Escpos, restaurant: Restaurant, branch: Branch, subtitle: str | None = None) -> None:
    doc.align("center").bold(True).text(restaurant.name).bold(False)
    doc.text(branch.name)
    if subtitle:
        doc.bold(True).text(subtitle).bold(False)
    doc.align("left").rule()


def _delivery_block(doc: escpos.Escpos, order: Order) -> None:
    if order.delivery_type is None and not order.customer_phone:
        return
    doc.rule()
    doc.bold(True).text("DELIVERY" if order.delivery_type == "DELIVERY" else "PICKUP" if order.delivery_type else "CUSTOMER").bold(False)
    if order.customer_name:
        doc.text(f"Name: {order.customer_name}")
    if order.customer_phone:
        doc.text(f"Phone: {order.customer_phone}")
    if order.delivery_type == "DELIVERY":
        if order.delivery_address:
            doc.text(f"Address: {order.delivery_address}")
        if order.delivery_note:
            doc.text(f"Note: {order.delivery_note}")
        if order.delivery_lat is not None and order.delivery_lng is not None:
            doc.text(f"GPS: {order.delivery_lat}, {order.delivery_lng}")
    if order.payment_method:
        doc.text("Pay: " + {"CASH": "cash", "CARD_TRANSFER": "card transfer", "PAYME": "Payme"}.get(order.payment_method, order.payment_method))


def _is_customer_order(order: Order) -> bool:
    """Telegram / QR / delivery orders carry a customer: their kitchen slip is the
    document that travels with the food to the courier, so it must be complete."""
    return order.delivery_type is not None or bool(order.customer_phone)


def _priced_items(doc: escpos.Escpos, order: Order, cur: str) -> None:
    for item in order.items:
        doc.bold(True).text(item.product_name_snapshot).bold(False)
        doc.columns(f"  {item.quantity} x {_money(item.unit_price, cur)}", _money(item.unit_price * item.quantity, cur))
        for mod in item.modifiers:
            doc.columns(f"  + {mod.modifier_name_snapshot} x{mod.quantity}", _money(mod.price * mod.quantity, cur))
        if item.notes:
            doc.text(f"  * {item.notes}")


def _totals(doc: escpos.Escpos, order: Order, cur: str) -> None:
    doc.columns("Subtotal", _money(order.subtotal, cur))
    if order.discount > 0:
        doc.columns("Discount", "-" + _money(order.discount, cur))
    if order.tax > 0:
        doc.columns("Tax", _money(order.tax, cur))
    if order.service_charge > 0:
        doc.columns("Service (10%)", _money(order.service_charge, cur))
    doc.rule().bold(True).columns("TOTAL", _money(order.total, cur)).bold(False)


def render_kitchen_ticket(order: Order, restaurant: Restaurant, branch: Branch, paper_width: int) -> bytes:
    doc = escpos.Escpos(paper_width)
    if not _is_customer_order(order):
        # Waiter / POS order: the cooks need only the table and the dishes.
        doc.align("center").bold(True).big(True)
        doc.text(f"TABLE {order.table.name}" if order.table is not None else "TAKEAWAY")
        doc.big(False).bold(False).text(f"#{order.order_number}  {_stamp(order.created_at, restaurant.timezone)}")
        doc.align("left").rule()
        for item in order.items:
            doc.bold(True).text(f"{item.quantity}x {item.product_name_snapshot}").bold(False)
            for mod in item.modifiers:
                suffix = f" x{mod.quantity}" if mod.quantity > 1 else ""
                doc.text(f"   + {mod.modifier_name_snapshot}{suffix}")
            if item.notes:
                doc.text(f"   * {item.notes}")
        if order.notes:
            doc.rule().bold(True).text(f"NOTE: {order.notes}").bold(False)
        return doc.feed(3).cut().to_bytes()

    # Customer order (Telegram / QR / delivery): the complete slip for the courier.
    cur = order.currency
    _header(doc, restaurant, branch, "ORDER" if order.delivery_type != "DELIVERY" else "DELIVERY ORDER")
    doc.align("center").bold(True).big(True).text(f"#{order.order_number}").big(False).bold(False).align("left")
    doc.text(f"{order.source} | {_stamp(order.created_at, restaurant.timezone)}")
    _delivery_block(doc, order)
    doc.rule()
    _priced_items(doc, order, cur)
    if order.notes:
        doc.rule().bold(True).text(f"NOTE: {order.notes}").bold(False)
    doc.rule()
    _totals(doc, order, cur)
    paid = sum((p.amount for p in order.payments if p.status == "PAID"), Decimal("0"))
    doc.rule().align("center").bold(True)
    doc.text("PAID" if paid >= order.total else f"TO COLLECT: {_money(order.total - paid, cur)}")
    doc.bold(False).align("left")
    return doc.feed(3).cut().to_bytes()


def render_bill(order: Order, restaurant: Restaurant, branch: Branch, kind: str, paper_width: int) -> bytes:
    cur = order.currency
    doc = escpos.Escpos(paper_width)
    _header(doc, restaurant, branch, {"PRECHECK": "HISOB / BILL", "ORDER_COPY": "BUYURTMA / ORDER"}.get(kind))
    if restaurant.address:
        doc.align("center").text(restaurant.address).align("left")
    if restaurant.phone:
        doc.align("center").text(f"Tel: {restaurant.phone}").align("left")
    doc.text(f"Order: #{order.order_number}")
    doc.text(_stamp(order.created_at, restaurant.timezone))
    if order.table is not None:
        doc.text(f"Table: {order.table.name}")
    if order.waiter is not None:
        doc.text(f"Waiter: {order.waiter.full_name}")
    _delivery_block(doc, order)
    doc.rule()
    for item in order.items:
        doc.text(item.product_name_snapshot)
        doc.columns(f"  {item.quantity} x {_money(item.unit_price, cur)}", _money(item.unit_price * item.quantity, cur))
        for mod in item.modifiers:
            doc.columns(f"  + {mod.modifier_name_snapshot} x{mod.quantity}", _money(mod.price * mod.quantity, cur))
    doc.rule()
    doc.columns("Subtotal", _money(order.subtotal, cur))
    if order.discount > 0:
        doc.columns("Discount", "-" + _money(order.discount, cur))
    if order.tax > 0:
        doc.columns("Tax", _money(order.tax, cur))
    if order.service_charge > 0:
        doc.columns("Service (10%)", _money(order.service_charge, cur))
    doc.rule().bold(True).columns("TOTAL", _money(order.total, cur)).bold(False)
    if kind == "RECEIPT":
        paid = [p for p in order.payments if p.status == "PAID"]
        if paid:
            doc.rule()
            for p in paid:
                doc.columns(_METHOD_LABEL.get(p.method, p.method), _money(p.amount, cur))
            doc.columns("Paid", _money(sum((p.amount for p in paid), Decimal("0")), cur))
        doc.rule().align("center").text("Rahmat! Thank you!").align("left")
    return doc.feed(3).cut().to_bytes()


def render_test(printer: Printer, restaurant: Restaurant, branch: Branch) -> bytes:
    doc = escpos.Escpos(printer.paper_width)
    _header(doc, restaurant, branch, "TEST PRINT")
    doc.text(f"Printer: {printer.name}")
    doc.text(f"Role: {printer.role}   Paper: {printer.paper_width}mm")
    doc.text(_stamp(datetime.now(timezone.utc), restaurant.timezone))
    doc.align("center").text("o' g' sh ch  OK").align("left")
    return doc.feed(3).cut().to_bytes()


# ---------------------------------------------------------------------------
# Job execution
# ---------------------------------------------------------------------------
async def _build_payload(session: AsyncSession, job: PrintJob, printer: Printer) -> bytes:
    restaurant = await session.get(Restaurant, job.restaurant_id)
    branch = await session.get(Branch, job.branch_id)
    if job.kind == "TEST" or job.order_id is None:
        return render_test(printer, restaurant, branch)
    from app.services import orders as order_service

    order = await order_service.get_order(session, job.restaurant_id, job.order_id)
    if job.kind == "KITCHEN_TICKET":
        return render_kitchen_ticket(order, restaurant, branch, printer.paper_width)
    return render_bill(order, restaurant, branch, job.kind, printer.paper_width)


async def _run_job(job_id: uuid.UUID) -> None:
    try:
        async with SessionLocal() as session:
            job = await session.get(PrintJob, job_id)
            if job is None:
                return
            printer = await session.get(Printer, job.printer_id) if job.printer_id else None
            if printer is None or not printer.is_active:
                job.status, job.error = "FAILED", "No active printer for this job."
                await session.commit()
                return
            try:
                payload = await _build_payload(session, job, printer)
            except Exception as exc:  # noqa: BLE001
                logger.exception("print job %s: rendering failed", job_id)
                job.status, job.error = "FAILED", f"Render error: {exc}"[:500]
                await session.commit()
                return

            if printer.mode == "AGENT":
                # A cloud server can't reach a LAN printer: park the bytes and
                # let the branch's print agent collect them (services/print_agent.py).
                job.payload, job.claimed_at, job.attempts = payload, None, 0
                job.status, job.error = "PENDING", None
                await session.commit()
                return

            last_error = "unknown error"
            for attempt in range(1, SEND_ATTEMPTS + 1):
                job.attempts = attempt
                try:
                    await escpos.send(printer.host, printer.port, payload)
                except Exception as exc:  # noqa: BLE001 — network errors vary widely
                    last_error = f"{type(exc).__name__}: {exc}".strip(": ")[:500]
                    if attempt < SEND_ATTEMPTS and not settings.print_dispatch_inline:
                        await asyncio.sleep(1.0)
                    continue
                job.status, job.error = "PRINTED", None
                job.printed_at = datetime.now(timezone.utc)
                await session.commit()
                return
            job.status, job.error = "FAILED", last_error
            await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("print job %s crashed", job_id)


async def schedule(
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID,
    kind: str,
    role: str,
    order_id: uuid.UUID | None = None,
    *,
    wait: bool = False,
    printer_id: uuid.UUID | None = None,
) -> PrintJob | None:
    """Create + run a print job. Returns None when the branch has no active
    printer for `role` (nothing to do), and never raises."""
    try:
        async with SessionLocal() as session:
            stmt = select(Printer).where(Printer.restaurant_id == restaurant_id, Printer.branch_id == branch_id)
            stmt = stmt.where(Printer.id == printer_id) if printer_id else stmt.where(
                Printer.role == role, Printer.is_active.is_(True)
            )
            printer = await session.scalar(stmt)
            if printer is None:
                return None
            job = PrintJob(
                restaurant_id=restaurant_id,
                branch_id=branch_id,
                printer_id=printer.id,
                kind=kind,
                order_id=order_id,
                status="PENDING",
            )
            session.add(job)
            await session.commit()
            job_id = job.id

        if wait or settings.print_dispatch_inline:
            await _run_job(job_id)
        else:
            task = asyncio.create_task(_run_job(job_id))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)

        async with SessionLocal() as session:
            return await session.get(PrintJob, job_id)
    except Exception:  # noqa: BLE001
        logger.exception("could not schedule print job (%s, order=%s)", kind, order_id)
        return None


async def _fire(coro) -> None:
    """Run a side-effect coroutine without making the caller wait for it."""
    if settings.print_dispatch_inline:
        await coro
        return
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def schedule_kitchen_ticket(restaurant_id: uuid.UUID, branch_id: uuid.UUID, order_id: uuid.UUID) -> None:
    await _fire(schedule(restaurant_id, branch_id, "KITCHEN_TICKET", "KITCHEN", order_id))


async def schedule_order_copy(restaurant_id: uuid.UUID, branch_id: uuid.UUID, order_id: uuid.UUID) -> None:
    """Full copy of a new order on the cashier (RECEIPT) printer, when that printer
    opted in with `auto_print_orders`."""
    await _fire(_order_copy(restaurant_id, branch_id, order_id))


async def _order_copy(restaurant_id: uuid.UUID, branch_id: uuid.UUID, order_id: uuid.UUID) -> None:
    try:
        async with SessionLocal() as session:
            enabled = await session.scalar(
                select(Printer.id).where(
                    Printer.restaurant_id == restaurant_id,
                    Printer.branch_id == branch_id,
                    Printer.role == "RECEIPT",
                    Printer.is_active.is_(True),
                    Printer.auto_print_orders.is_(True),
                )
            )
        if enabled is not None:
            await schedule(restaurant_id, branch_id, "ORDER_COPY", "RECEIPT", order_id)
    except Exception:  # noqa: BLE001
        logger.exception("order copy print failed for order %s", order_id)


async def auto_print_receipt_if_enabled(restaurant_id: uuid.UUID, branch_id: uuid.UUID, order_id: uuid.UUID) -> None:
    await _fire(_auto_print_receipt(restaurant_id, branch_id, order_id))


async def _auto_print_receipt(restaurant_id: uuid.UUID, branch_id: uuid.UUID, order_id: uuid.UUID) -> None:
    try:
        async with SessionLocal() as session:
            enabled = await session.scalar(
                select(Printer.id).where(
                    Printer.restaurant_id == restaurant_id,
                    Printer.branch_id == branch_id,
                    Printer.role == "RECEIPT",
                    Printer.is_active.is_(True),
                    Printer.auto_print_receipt.is_(True),
                )
            )
        if enabled is not None:
            await schedule(restaurant_id, branch_id, "RECEIPT", "RECEIPT", order_id)
    except Exception:  # noqa: BLE001
        logger.exception("auto receipt print failed for order %s", order_id)


# ---------------------------------------------------------------------------
# Explicit actions (API)
# ---------------------------------------------------------------------------
async def print_order(
    session: AsyncSession, restaurant_id: uuid.UUID, order_id: uuid.UUID, kind: str
) -> PrintJob:
    from app.services import orders as order_service

    order = await order_service.get_order(session, restaurant_id, order_id)
    role = "KITCHEN" if kind == "KITCHEN_TICKET" else "RECEIPT"
    job = await schedule(restaurant_id, order.branch_id, kind, role, order.id, wait=True)
    if job is None:
        label = "kitchen" if role == "KITCHEN" else "receipt"
        raise BusinessRuleError(detail=f"No active {label} printer is set up for this branch.")
    return job


async def retry_job(session: AsyncSession, restaurant_id: uuid.UUID, job_id: uuid.UUID) -> PrintJob:
    job = await session.scalar(
        select(PrintJob).where(PrintJob.restaurant_id == restaurant_id, PrintJob.id == job_id)
    )
    if job is None:
        raise NotFoundError(detail="Print job not found in this restaurant.")
    job.status, job.attempts, job.error = "PENDING", 0, None
    job.payload, job.claimed_at = None, None
    await session.commit()
    await _run_job(job.id)
    await session.refresh(job)
    return job


async def list_jobs(session: AsyncSession, restaurant_id: uuid.UUID, limit: int = 50) -> list[PrintJob]:
    result = await session.scalars(
        select(PrintJob)
        .where(PrintJob.restaurant_id == restaurant_id)
        .order_by(PrintJob.created_at.desc())
        .limit(limit)
    )
    return list(result.all())


async def capabilities(session: AsyncSession, restaurant_id: uuid.UUID, branch_id: uuid.UUID) -> dict[str, bool]:
    roles = set(
        (
            await session.scalars(
                select(Printer.role).where(
                    Printer.restaurant_id == restaurant_id,
                    Printer.branch_id == branch_id,
                    Printer.is_active.is_(True),
                )
            )
        ).all()
    )
    return {"kitchen": "KITCHEN" in roles, "receipt": "RECEIPT" in roles}


# ---------------------------------------------------------------------------
# Printer CRUD
# ---------------------------------------------------------------------------
async def list_printers(session: AsyncSession, restaurant_id: uuid.UUID, branch_id: uuid.UUID | None) -> list[Printer]:
    stmt = select(Printer).where(Printer.restaurant_id == restaurant_id).order_by(Printer.created_at)
    if branch_id is not None:
        stmt = stmt.where(Printer.branch_id == branch_id)
    return list((await session.scalars(stmt)).all())


async def _get_printer(session: AsyncSession, restaurant_id: uuid.UUID, printer_id: uuid.UUID) -> Printer:
    printer = await session.scalar(
        select(Printer).where(Printer.restaurant_id == restaurant_id, Printer.id == printer_id)
    )
    if printer is None:
        raise NotFoundError(detail="Printer not found in this restaurant.")
    return printer


async def create_printer(
    session: AsyncSession, restaurant_id: uuid.UUID, actor_id: uuid.UUID, payload: PrinterCreate
) -> Printer:
    branch = await session.scalar(
        select(Branch).where(Branch.restaurant_id == restaurant_id, Branch.id == payload.branch_id)
    )
    if branch is None:
        raise NotFoundError(detail="Branch not found in this restaurant.")
    exists = await session.scalar(
        select(Printer.id).where(Printer.branch_id == payload.branch_id, Printer.role == payload.role)
    )
    if exists is not None:
        raise ConflictError(detail="This branch already has a printer for that role.")
    printer = Printer(restaurant_id=restaurant_id, **payload.model_dump())
    session.add(printer)
    await session.flush()
    await session.commit()
    await audit_service.log_action(
        session, restaurant_id, actor_id, "printer.create", "printer", printer.id,
        f"Added {printer.role.lower()} printer {printer.name} ({printer.host}:{printer.port})",
    )
    return printer


async def update_printer(
    session: AsyncSession, restaurant_id: uuid.UUID, actor_id: uuid.UUID, printer_id: uuid.UUID, payload: PrinterUpdate
) -> Printer:
    printer = await _get_printer(session, restaurant_id, printer_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(printer, field, value)
    if printer.mode == "DIRECT" and printer.host == "local":
        raise BusinessRuleError(detail="A direct printer needs an IPv4 address; use agent mode for USB printers.")
    await session.commit()
    await session.refresh(printer)
    await audit_service.log_action(
        session, restaurant_id, actor_id, "printer.update", "printer", printer.id,
        f"Updated {printer.role.lower()} printer {printer.name} ({printer.host}:{printer.port})",
    )
    return printer


async def delete_printer(
    session: AsyncSession, restaurant_id: uuid.UUID, actor_id: uuid.UUID, printer_id: uuid.UUID
) -> None:
    printer = await _get_printer(session, restaurant_id, printer_id)
    summary = f"Removed {printer.role.lower()} printer {printer.name}"
    await session.delete(printer)
    await session.commit()
    await audit_service.log_action(session, restaurant_id, actor_id, "printer.delete", "printer", printer_id, summary)


async def test_print(session: AsyncSession, restaurant_id: uuid.UUID, printer_id: uuid.UUID) -> PrintJob:
    printer = await _get_printer(session, restaurant_id, printer_id)
    job = await schedule(
        restaurant_id, printer.branch_id, "TEST", printer.role, None, wait=True, printer_id=printer.id
    )
    if job is None:
        raise BusinessRuleError(detail="Could not start the test print.")
    return job
