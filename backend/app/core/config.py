from functools import lru_cache
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "SYNORA API"
    app_env: str = "dev"
    debug: bool = True

    database_url: str = (
        "postgresql+asyncpg://synora:synora@localhost:55432/synora"
    )

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_seconds: int = 900
    login_lockout_seconds: int = 900

    refresh_cookie_name: str = "synora_refresh"
    # httpOnly + SameSite=Strict always. Secure is toggled off in dev so the
    # cookie works over plain http://localhost; production must keep it on.
    refresh_cookie_secure: bool = True
    refresh_cookie_path: str = "/api/v1/auth"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    upload_dir: str = "uploads"

    # Public-facing base URL of the app. Used to build absolute links in emails
    # (password reset) and payment return URLs. In prod: https://<real-domain>.
    public_app_url: str = "http://localhost:3000"

    # --- Email (SMTP) --------------------------------------------------------
    # Leave untested-smoke blank to run in "log-only" mode: the app never sends
    # mail, it logs the reset link instead (safe, testable local fallback).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "SYNORA <no-reply@synora.app>"
    smtp_use_tls: bool = True

    # --- Password reset ------------------------------------------------------
    password_reset_expire_minutes: int = 45

    # --- Object storage (S3-compatible) --------------------------------------
    # When S3_ENDPOINT is set, uploads go to the bucket instead of local disk.
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    s3_public_url_base: str = ""  # e.g. https://files.example.com or http://localhost:9000
    s3_use_path_style: bool = True

    # --- Payme (Uzbekistan payment gateway) ----------------------------------
    # Sandbox checkout: https://test.paycom.uz ; live: https://checkout.paycom.uz
    payme_checkout_base_url: str = "https://test.paycom.uz"
    payme_login: str = ""      # Basic-auth user (usually "Paycom")
    payme_key: str = ""        # Basic-auth password: TEST KEY while testing
    payme_merchant_id: str = ""  # cashier/m-id used in the checkout LINK path
    payme_is_test: bool = True

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def payme_configured(self) -> bool:
        return bool(self.payme_key)

    @model_validator(mode="after")
    def _validate_deployment_fields(self) -> "Settings":
        # Never let a known public default sign tokens outside dev. "change-me"
        # is only acceptable for throwaway local runs.
        if self.app_env == "prod" and self.jwt_secret_key == "change-me":
            raise ValueError(
                "JWT_SECRET_KEY must be set to a real secret when APP_ENV=prod "
                "(generate one with: python -c \"import secrets; "
                "print(secrets.token_urlsafe(64))\")."
            )
        # Never run production on Payme sandbox credentials.
        if self.app_env == "prod" and self.payme_configured and self.payme_is_test:
            raise ValueError(
                "Refusing to start production with Payme TEST credentials. Set "
                "PAYME_IS_TEST=false and supply the live merchant key."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()