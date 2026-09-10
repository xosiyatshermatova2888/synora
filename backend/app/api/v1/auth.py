from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_client_ip,
    get_current_user_restaurant,
    require_login_rate_limit,
)
from app.core.config import settings
from app.database.session import get_db
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services import auth as auth_service
from app.services.password_reset import confirm_reset, request_reset
from app.utils.rate_limit import record_login_failure, record_login_success

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
    result = await auth_service.register(
        db,
        payload,
        response=response,
        user_agent=request.headers.get("user-agent"),
        ip=await get_client_ip(request),
    )
    return _payload_to_model(result)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_login_rate_limit),
):
    email = payload.email.lower()
    ip = await get_client_ip(request)
    try:
        result = await auth_service.login(
            db,
            email,
            payload.password,
            response=response,
            user_agent=request.headers.get("user-agent"),
            ip=ip,
        )
    except Exception:
        record_login_failure(email, ip)
        raise
    record_login_success(email, ip)
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


@router.post("/password-reset/request", status_code=202)
async def password_reset_request(
    payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)
):
    # Uniform 202 for existing and unknown addresses: no account disclosure.
    await request_reset(db, payload.email)
    return {"status": "if the account exists, a reset email will be sent"}


@router.post("/password-reset/confirm", status_code=204)
async def password_reset_confirm(
    payload: PasswordResetConfirm, db: AsyncSession = Depends(get_db)
):
    await confirm_reset(db, payload.token, payload.new_password)
    return None