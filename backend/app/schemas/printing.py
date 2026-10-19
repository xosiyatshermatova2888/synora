import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.integrations.escpos import validate_private_ipv4


# A printer plugged into the restaurant PC by USB has no IP address. Its jobs are
# queued for the print agent (mode AGENT) and the agent prints them through the
# PC's own printer driver, so the stored "host" is just this marker.
LOCAL_HOST = "local"
_LOCAL_ALIASES = {"", "local", "usb"}


def _clean_host(value: str, *, agent: bool | None) -> str:
    """`agent`: True = AGENT mode, False = DIRECT, None = unknown (partial update)."""
    if value.strip().lower() in _LOCAL_ALIASES:
        if agent is False:
            raise ValueError("A direct printer needs an IPv4 address like 192.168.1.50")
        return LOCAL_HOST
    return validate_private_ipv4(value)


class PrinterBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str = LOCAL_HOST
    port: int = Field(default=9100, ge=1, le=65535)
    paper_width: Literal[58, 80] = 80
    is_active: bool = True
    auto_print_receipt: bool = False
    auto_print_orders: bool = False
    mode: Literal["DIRECT", "AGENT"] = "DIRECT"

    @model_validator(mode="after")
    def _check_host(self):
        self.host = _clean_host(self.host, agent=self.mode == "AGENT")
        return self


class PrinterCreate(PrinterBase):
    branch_id: uuid.UUID
    role: Literal["KITCHEN", "RECEIPT"]


class PrinterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    paper_width: Literal[58, 80] | None = None
    is_active: bool | None = None
    auto_print_receipt: bool | None = None
    auto_print_orders: bool | None = None
    mode: Literal["DIRECT", "AGENT"] | None = None

    @model_validator(mode="after")
    def _check_host(self):
        if self.host is not None:
            agent = None if self.mode is None else self.mode == "AGENT"
            self.host = _clean_host(self.host, agent=agent)
        return self


class PrinterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    role: str
    host: str
    port: int
    paper_width: int
    is_active: bool
    auto_print_receipt: bool
    auto_print_orders: bool
    mode: str


class PrinterCapabilitiesOut(BaseModel):
    kitchen: bool
    receipt: bool


class PrintJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    branch_id: uuid.UUID
    printer_id: uuid.UUID | None
    kind: str
    order_id: uuid.UUID | None
    status: str
    attempts: int
    error: str | None
    created_at: datetime
    printed_at: datetime | None


# --- Print agent (runs on a PC inside the restaurant) -------------------------
class AgentStatusOut(BaseModel):
    configured: bool
    last_seen_at: datetime | None
    online: bool


class AgentTokenOut(BaseModel):
    token: str  # shown exactly once; only its hash is stored


class AgentJobOut(BaseModel):
    id: uuid.UUID
    host: str
    port: int
    data_b64: str


class AgentPollOut(BaseModel):
    jobs: list[AgentJobOut]


class AgentResultIn(BaseModel):
    ok: bool
    error: str | None = Field(default=None, max_length=500)
