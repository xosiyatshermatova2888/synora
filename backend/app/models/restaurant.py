import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, uuid_pk


class Restaurant(Base, TimestampMixin):
    __tablename__ = "restaurants"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="UZS", nullable=False)  # ISO 4217
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Telegram ordering bot (Section 3B) -----------------------------------
    # One bot per restaurant, not a shared platform bot — the owner connects
    # their own @BotFather token via the dashboard Settings page. Never
    # returned raw in any API response (see schemas/restaurants.py); the
    # webhook secret authenticates inbound calls at api/v1/telegram.py.
    telegram_bot_token: Mapped[str | None] = mapped_column(String(200))
    telegram_bot_username: Mapped[str | None] = mapped_column(String(100))
    telegram_webhook_secret: Mapped[str | None] = mapped_column(String(100))

    # Where customers pay by card transfer (shown by the Telegram bot).
    payment_card_number: Mapped[str | None] = mapped_column(String(32))
    payment_card_holder: Mapped[str | None] = mapped_column(String(100))

    # --- Tariff / subscription (core/plans.py decides what these dates mean) --
    # The Python-side defaults give any restaurant created without an explicit
    # plan the safe legacy behaviour (Business, no expiry); `register` opts
    # new sign-ups into the 14-day Pro trial.
    plan: Mapped[str] = mapped_column(
        String(20), default="BUSINESS", server_default="BUSINESS", nullable=False
    )
    subscription_status: Mapped[str] = mapped_column(
        String(10), default="ACTIVE", server_default="ACTIVE", nullable=False
    )  # TRIAL | ACTIVE
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # NULL = no expiry
    billing_cycle: Mapped[str | None] = mapped_column(String(10))  # MONTHLY | ANNUAL

    @property
    def telegram_connected(self) -> bool:
        return self.telegram_bot_token is not None

# Audit: who created this restaurant. Plain column (no DB FK): it points at
    # users.id which itself references restaurants.id (a circular FK Postgres
    # cannot define in one migration). Referential integrity on this audit
    # field is enforced by the application layer.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    branches = relationship("Branch", back_populates="restaurant", lazy="selectin")
    users = relationship("User", back_populates="restaurant", lazy="selectin")