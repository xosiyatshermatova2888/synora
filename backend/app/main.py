from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger, request_id_var
from app.database.session import SessionLocal
from app.utils.rate_limit import GENERAL_LIMIT_WINDOW_SECONDS
from app.websocket.routes import router as websocket_router
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from app.utils.errors import APIError

import os
import uuid

configure_logging()
logger = get_logger("synora.app")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/api/docs" if settings.debug else None,
    redoc_url=None,
)

# Serve uploaded images (local/dev disk storage).
# TODO: swap for S3-compatible object storage before production.
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/files", StaticFiles(directory=settings.upload_dir), name="files")


@app.on_event("startup")
async def log_startup() -> None:
    # Seed the GLOBAL permissions + system-role templates (idempotent).
    from app.services.permissions import ensure_system_permissions_and_roles

    async with SessionLocal() as session:
        await ensure_system_permissions_and_roles(session)
        await session.commit()
    logger.info("startup complete", extra={"env": settings.app_env, "debug": settings.debug})


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    request_id_var.set(request_id)
    logger.info("incoming request", extra={
        "method": request.method, "path": request.url.path})
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled error", extra={
            "method": request.method, "path": request.url.path})
        raise
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def general_rate_limit_middleware(request: Request, call_next):
    """Per-IP API rate limit (Section 18). Health + auth/login are exempt (login
    has its own stricter limit in the route)."""
    path = request.url.path
    if path.startswith("/api/v1") and not (
        path.endswith("/health") or path.endswith("/health/ready")
    ):
        from fastapi.responses import JSONResponse

        from app.api.deps import get_client_ip
        from app.utils import rate_limit

        ip = await get_client_ip(request)
        if rate_limit.api_limit_hit(ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again later."},
                headers={"Retry-After": str(GENERAL_LIMIT_WINDOW_SECONDS)},
            )
        rate_limit.record_api_call(ip)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    logger.info("api error", extra={
        "method": request.method, "path": request.url.path,
        "status": exc.status_code, "detail": exc.detail})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("integrity error", extra={
        "method": request.method, "path": request.url.path})
    await request.state.session.rollback() if hasattr(request.state, "session") else None
    return JSONResponse(
        status_code=409,
        content={"detail": "Resource conflicts with existing data."},
    )


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("database error", extra={
        "method": request.method, "path": request.url.path})
    return JSONResponse(status_code=500, content={"detail": "Database error."})


@app.exception_handler(StarletteHTTPException)
async def handled_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(api_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict:
    return {"service": settings.app_name, "health": "/api/v1/health"}