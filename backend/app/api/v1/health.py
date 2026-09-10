from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe — process is up")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe — DB connection succeeds")
async def health_ready(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}