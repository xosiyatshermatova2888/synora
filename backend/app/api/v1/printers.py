"""Receipt-printer settings + print-job log.

Managing printers (an address the server connects to) is admin-only
(`users.manage`); every staff role that can read orders may ask which printers
exist for a branch (booleans only — no addresses) so the UI can choose between
the network printer and the browser fallback.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user_restaurant, require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.printing import (
    AgentStatusOut,
    AgentTokenOut,
    PrinterCapabilitiesOut,
    PrinterCreate,
    PrinterOut,
    PrinterUpdate,
    PrintJobOut,
)
from app.services import print_agent as agent_service
from app.services import printing as printing_service

router = APIRouter(tags=["printers"])


@router.get("/printers", response_model=list[PrinterOut])
async def list_printers(
    branch_id: uuid.UUID | None = Query(default=None),
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    return await printing_service.list_printers(db, current_tenant, branch_id)


@router.get("/printers/capabilities", response_model=PrinterCapabilitiesOut)
async def printer_capabilities(
    branch_id: uuid.UUID = Query(),
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
):
    return await printing_service.capabilities(db, current_tenant, branch_id)


@router.post("/printers", response_model=PrinterOut, status_code=201)
async def create_printer(
    payload: PrinterCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    return await printing_service.create_printer(db, current_tenant, current_user.id, payload)


@router.patch("/printers/{printer_id}", response_model=PrinterOut)
async def update_printer(
    printer_id: uuid.UUID,
    payload: PrinterUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    return await printing_service.update_printer(db, current_tenant, current_user.id, printer_id, payload)


@router.delete("/printers/{printer_id}", status_code=204)
async def delete_printer(
    printer_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    await printing_service.delete_printer(db, current_tenant, current_user.id, printer_id)


@router.post("/printers/{printer_id}/test", response_model=PrintJobOut)
async def test_print(
    printer_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    return await printing_service.test_print(db, current_tenant, printer_id)


@router.get("/print-jobs", response_model=list[PrintJobOut])
async def list_print_jobs(
    limit: int = Query(default=30, ge=1, le=100),
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    return await printing_service.list_jobs(db, current_tenant, limit)


@router.post("/print-jobs/{job_id}/retry", response_model=PrintJobOut)
async def retry_print_job(
    job_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    return await printing_service.retry_job(db, current_tenant, job_id)


@router.get("/printers/agent", response_model=AgentStatusOut)
async def agent_status(
    branch_id: uuid.UUID = Query(),
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    return await agent_service.status(db, current_tenant, branch_id)


@router.post("/printers/agent/token", response_model=AgentTokenOut)
async def rotate_agent_token(
    branch_id: uuid.UUID = Query(),
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    """Create or replace the branch's print-agent token. Shown once."""
    return {"token": await agent_service.rotate_token(db, current_tenant, branch_id)}
