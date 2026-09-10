from app.integrations.payments.base import get_provider, register_provider
from app.integrations.payments.payme import PaymeProvider

register_provider(PaymeProvider)

__all__ = ["get_provider", "register_provider"]