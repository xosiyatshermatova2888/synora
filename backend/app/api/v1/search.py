"""Global search API — gated by `orders.read` (broad enough for day-to-day
staff use)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, require_permission
from app.database.session import get_db
from app.schemas.search import SearchResultsOut
from app.services import search as search_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResultsOut)
async def search(
    q: str = Query(min_length=1, max_length=100),
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
):
    return await search_service.global_search(db, current_tenant, q)
