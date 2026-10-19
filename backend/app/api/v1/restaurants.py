"""Restaurant + branch CRUD (Phase D). Every branch is tenant-scoped via the
`current_tenant` from JWT claims (Section 5A)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_tenant,
    get_current_user_restaurant,
    require_permission,
)
from app.database.session import get_db
from app.integrations.telegram import TelegramError
from app.models.branch import Branch
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.restaurants import (
    BranchCreate,
    BranchOut,
    BranchUpdate,
    RestaurantOut,
    RestaurantUpdate,
    TelegramConnectRequest,
    TelegramStatusOut,
)
from app.services import telegram_bot as telegram_bot_service
from app.services.subscription import ensure_branch_capacity
from app.utils.errors import NotFoundError, ValidationError

router = APIRouter(tags=["restaurants"])


@router.get("/restaurant/me", response_model=RestaurantOut)
async def get_my_restaurant(
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
):
    restaurant = await db.get(Restaurant, current_user.restaurant_id)
    if restaurant is None:
        raise NotFoundError(detail="Restaurant not found.")
    return restaurant


@router.patch("/restaurant/me", response_model=RestaurantOut)
async def update_my_restaurant(
    payload: RestaurantUpdate,
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    restaurant = await db.get(Restaurant, current_user.restaurant_id)
    if restaurant is None:
        raise NotFoundError(detail="Restaurant not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(restaurant, field, value)
    await db.flush()
    await db.commit()
    await db.refresh(restaurant)
    return restaurant


@router.get("/branches", response_model=list[BranchOut])
async def list_branches(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = list(
        (await db.scalars(
            select(Branch).where(
                Branch.restaurant_id == current_tenant, Branch.is_active.is_(True)
            ).order_by(Branch.name)
        )).all()
    )
    return result


@router.post("/branches", response_model=BranchOut, status_code=201)
async def create_branch(
    payload: BranchCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    await ensure_branch_capacity(db, current_tenant)
    branch = Branch(
        restaurant_id=current_tenant,
        name=payload.name,
        address=payload.address,
        phone=payload.phone,
        timezone=payload.timezone,
        currency=payload.currency,
        created_by_user_id=current_user.id,
    )
    db.add(branch)
    await db.flush()
    await db.commit()
    await db.refresh(branch)
    return branch


@router.get("/branches/{branch_id}", response_model=BranchOut)
async def get_branch(
    branch_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    branch = await db.get(Branch, branch_id)
    if branch is None or branch.restaurant_id != current_tenant:
        raise NotFoundError(detail="Branch not found in this restaurant.")
    return branch


@router.patch("/branches/{branch_id}", response_model=BranchOut)
async def update_branch(
    branch_id: uuid.UUID,
    payload: BranchUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    branch = await db.get(Branch, branch_id)
    if branch is None or branch.restaurant_id != current_tenant:
        raise NotFoundError(detail="Branch not found in this restaurant.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)
    await db.flush()
    await db.commit()
    await db.refresh(branch)
    return branch


@router.post("/restaurant/telegram", response_model=TelegramStatusOut)
async def connect_telegram_bot(
    payload: TelegramConnectRequest,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    try:
        restaurant = await telegram_bot_service.connect_bot(db, current_tenant, payload.bot_token)
    except TelegramError as err:
        raise ValidationError(detail=f"Telegram rejected this token: {err.description}")
    return TelegramStatusOut(
        telegram_connected=restaurant.telegram_connected,
        telegram_bot_username=restaurant.telegram_bot_username,
    )


@router.delete("/restaurant/telegram", response_model=TelegramStatusOut)
async def disconnect_telegram_bot(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    restaurant = await telegram_bot_service.disconnect_bot(db, current_tenant)
    return TelegramStatusOut(
        telegram_connected=restaurant.telegram_connected,
        telegram_bot_username=restaurant.telegram_bot_username,
    )