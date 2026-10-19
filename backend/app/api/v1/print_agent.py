"""Endpoints the restaurant's print agent calls. Authenticated by the branch's
agent token (not a user JWT): the token alone fixes the tenant and branch."""

import uuid

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.printer import PrintAgent
from app.schemas.printing import AgentPollOut, AgentResultIn
from app.services import print_agent as agent_service

router = APIRouter(prefix="/print-agent", tags=["print-agent"])
_bearer = HTTPBearer(auto_error=False)


async def get_print_agent(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> PrintAgent:
    return await agent_service.authenticate(db, credentials.credentials if credentials else None)


@router.post("/poll", response_model=AgentPollOut)
async def poll(agent: PrintAgent = Depends(get_print_agent), db: AsyncSession = Depends(get_db)):
    return {"jobs": await agent_service.poll(db, agent)}


@router.post("/jobs/{job_id}/result", status_code=204)
async def report_result(
    job_id: uuid.UUID,
    payload: AgentResultIn,
    agent: PrintAgent = Depends(get_print_agent),
    db: AsyncSession = Depends(get_db),
):
    await agent_service.report_result(db, agent, job_id, payload.ok, payload.error)
