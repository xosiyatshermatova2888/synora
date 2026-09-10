"""Payment provider interface (Phase M).

`PaymentProvider` is the seam between SYNORA's internal payments ledger and an
external processor. Each provider implements checkout creation and webhook
authentication; the per-provider JSON-RPC/HTTP dispatch lives with the
implementation so swapping/adding providers (Payme -> Click, ...) never touches
the `Payment` model or the order state machine.

Providers register in a small registry; `get_provider("PAYME")` etc. Webhooks
are verified by the provider BEFORE the service trusts any field, so an
unauthenticated payload can never mark an order paid.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class ProviderEvent:
    """A verified webhook event handed from provider to the payment service."""

    method: str
    params: dict[str, Any]
    order_id: uuid.UUID | None = None
    transaction_id: str | None = None
    raw: str = ""


class WebhookUnauthorized(Exception):
    """Provider could not authenticate the webhook caller."""


class PaymentProvider(ABC):
    """Methods a provider must implement to plug into SYNORA payments."""

    name: str = ""

    @abstractmethod
    def create_checkout(self, order_id: uuid.UUID, amount: Decimal) -> str:
        """Return a URL/token the customer is sent to to pay `amount`."""

    @abstractmethod
    def verify_webhook(self, payload: dict, signature: str | None, raw: str) -> ProviderEvent:
        """Authenticate a webhook call and normalize it to a `ProviderEvent`.

        Must raise `WebhookUnauthorized` when the signature doesn't match. Must
        map the payload's account/order identifier to `order_id`.
        """


_REGISTRY: dict[str, type[PaymentProvider]] = {}


def register_provider(cls: type[PaymentProvider]) -> type[PaymentProvider]:
    _REGISTRY[cls.name.upper()] = cls
    return cls


def get_provider(name: str) -> PaymentProvider | None:
    cls = _REGISTRY.get(name.upper())
    return cls() if cls is not None else None


__all__ = [
    "PaymentProvider",
    "ProviderEvent",
    "WebhookUnauthorized",
    "get_provider",
    "register_provider",
    "field",
]