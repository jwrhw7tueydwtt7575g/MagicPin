from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Scope = Literal['category', 'merchant', 'customer', 'trigger']
SendAs = Literal['vera', 'merchant_on_behalf']
ReplyAction = Literal['send', 'wait', 'end']


class ContextPushRequest(BaseModel):
    scope: str
    context_id: str
    version: int = Field(ge=1)
    payload: dict[str, Any]
    delivered_at: str


class ContextPushAccepted(BaseModel):
    accepted: bool = True
    ack_id: str
    stored_at: str


class ContextPushRejected(BaseModel):
    accepted: bool = False
    reason: str
    current_version: int | None = None
    details: str | None = None


class TickRequest(BaseModel):
    now: str
    available_triggers: list[str] = []


class TickAction(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: str | None = None
    send_as: SendAs
    trigger_id: str
    template_name: str | None = None
    template_params: list[str] | None = None
    body: str
    cta: str
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: list[TickAction]


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: str | None = None
    from_role: str
    message: str
    received_at: str
    turn_number: int


class ReplySendResponse(BaseModel):
    action: Literal['send']
    body: str
    cta: str
    rationale: str


class ReplyWaitResponse(BaseModel):
    action: Literal['wait']
    wait_seconds: int
    rationale: str


class ReplyEndResponse(BaseModel):
    action: Literal['end']
    rationale: str


class HealthResponse(BaseModel):
    status: Literal['ok']
    uptime_seconds: int
    contexts_loaded: dict[str, int]


class MetadataResponse(BaseModel):
    team_name: str
    team_members: list[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str


class TeardownResponse(BaseModel):
    accepted: bool
