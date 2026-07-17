from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Literal


# ── Workspace schemas ──────────────────────────────────────────────────────────

AgentType = Literal["support", "operations", "finance", "onboarding"]


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    agent_type: AgentType = "support"
    zendesk_webhook_secret: str | None = None
    created_by: str | None = None

    model_config = {"json_schema_extra": {"example": {
        "name": "QuickCommerce Returns Agent",
        "agent_type": "support",
        "created_by": "elena.torres@quickcommerce.com"
    }}}


class WorkspaceRead(BaseModel):
    id: UUID
    name: str
    agent_type: str
    created_by: str | None
    created_at: datetime
    case_count: int = 0

    model_config = {"from_attributes": True}


# ── Exception case intake schemas ──────────────────────────────────────────────

class FullIntakePayload(BaseModel):
    """
    Structured escalation package from an instrumented agent.
    All 6 fields present. Intake mode = full.
    """
    workspace_id: UUID
    customer_message: str = Field(..., min_length=1)
    escalation_reason: str = Field(..., min_length=1)
    agent_trace: str | None = None
    attempted_actions: str | None = None
    missing_information: str | None = None
    policy_reference: str | None = None
    risk_level: str | None = None  # stored in escalation_reason if not separate

    model_config = {"json_schema_extra": {"example": {
        "workspace_id": "...",
        "customer_message": "I want a refund. I paid $45 cash and 200 loyalty points.",
        "escalation_reason": "Cannot determine correct refund split. Policy ambiguous.",
        "agent_trace": "Retrieved order. Attempted $65 cash refund. Blocked: exceeds cash payment.",
        "attempted_actions": "issue_cash_refund",
        "missing_information": "loyalty_points_refund_split_ratio",
        "policy_reference": "Section 7 — Loyalty Points"
    }}}


class ExceptionCaseRead(BaseModel):
    id: UUID
    workspace_id: UUID
    source: str
    intake_mode: str
    customer_message: str
    escalation_reason: str
    exception_type: str | None
    severity: str | None
    sla_tier: str | None
    recommended_owner: str | None
    status: str
    zendesk_ticket_id: str | None
    received_at: datetime

    model_config = {"from_attributes": True}


class IntakeResponse(BaseModel):
    exception_case: ExceptionCaseRead
    message: str
    next_step: str  # "classification queued" | "ready for retrieval"


# ── Zendesk webhook payload ─────────────────────────────────────────────────────

class ZendeskWebhookPayload(BaseModel):
    """
    Minimal payload from Zendesk ticket creation webhook.
    ExceptionLoop extracts customer_message and escalation_reason from ticket content.
    """
    ticket_id: str
    ticket_subject: str | None = None
    ticket_description: str  # customer message
    ticket_tags: list[str] = []
    requester_name: str | None = None
    workspace_id: str  # passed as a custom Zendesk ticket field or webhook metadata
