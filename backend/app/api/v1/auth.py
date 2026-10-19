import uuid

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_client_ip,
    get_current_user_restaurant,
)
from app.core.config import settings
from app.database.session import get_db
from app.schemas.auth import (
    LoginRequest,
    PinLoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    WaiterBranchOut,
    WaiterDirectoryEntry,
)
from app.services import auth as auth_service
from app.utils.errors import RateLimitedError
from app.utils.rate_limit import (
    login_blocked,
    pin_login_blocked,
    record_register_attempt,
    register_limit_hit,
    record_login_failure,
    record_login_success,
    record_pin_login_failure,
    record_pin_login_success,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _payload_to_model(p) -> TokenResponse:
    return TokenResponse(
        access_token=p.access_token, token_type="bearer", expires_in=p.expires_in
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    ip = await get_client_ip(request)
    if register_limit_hit(ip):
        raise RateLimitedError(detail="Too many sign-ups from this address. Try again later.")
    record_register_attempt(ip)
    result = await auth_service.register(
        db,
        payload,
        response=response,
        user_agent=request.headers.get("user-agent"),
        ip=ip,
    )
    return _payload_to_model(result)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    username = payload.username.lower()
    ip = await get_client_ip(request)
    # Checked here, where the username from the BODY is known. (A dependency
    # cannot see it: it was reading a `?username=` query parameter that no client
    # ever sends, so the per-account lock never engaged.)
    if login_blocked(username, ip):
        raise RateLimitedError(detail="Too many login attempts. Try again later.")
    try:
        result = await auth_service.login(
            db,
            username,
            payload.password,
            response=response,
            user_agent=request.headers.get("user-agent"),
            ip=ip,
        )
    except Exception:
        record_login_failure(username, ip)
        raise
    record_login_success(username, ip)
    return _payload_to_model(result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
):
    result = await auth_service.refresh(
        db,
        refresh_token or "",
        response=response,
        user_agent=request.headers.get("user-agent"),
        ip=await get_client_ip(request),
    )
    return _payload_to_model(result)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
):
    await auth_service.logout(db, refresh_token, response=response)
    return None


@router.get("/me", response_model=UserOut)
async def me(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user_restaurant),
):
    return await auth_service.me(db, user)


# --- Waiter kiosk PIN login (see schemas/auth.py) ---------------------------


@router.get("/waiter-branches", response_model=list[WaiterBranchOut])
async def waiter_branches(db: AsyncSession = Depends(get_db)):
    pairs = await auth_service.list_waiter_branches(db)
    return [
        WaiterBranchOut(id=branch.id, name=branch.name, restaurant_name=restaurant_name)
        for branch, restaurant_name in pairs
    ]


@router.get("/waiter-directory", response_model=list[WaiterDirectoryEntry])
async def waiter_directory(branch_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    users = await auth_service.waiter_directory(db, branch_id)
    return [WaiterDirectoryEntry(id=u.id, full_name=u.full_name) for u in users]


@router.post("/pin-login", response_model=TokenResponse)
async def pin_login(
    payload: PinLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    ip = await get_client_ip(request)
    key = str(payload.user_id)
    if pin_login_blocked(key, ip):
        raise RateLimitedError(detail="Too many attempts. Try again later.")
    try:
        result = await auth_service.pin_login(
            db,
            payload.branch_id,
            payload.user_id,
            payload.pin,
            response=response,
            user_agent=request.headers.get("user-agent"),
            ip=ip,
        )
    except Exception:
        record_pin_login_failure(key, ip)
        raise
    record_pin_login_success(key, ip)
    return _payload_to_model(result)