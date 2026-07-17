"""
Exception intake router.

Two modes:
1. POST /intake/full  — structured 6-field payload from instrumented agent
2. POST /webhooks/zendesk/{workspace_id} — minimal intake from Zendesk webhook

Both produce exception_case records and queue them for classification.
"""

import hashlib
import hmac
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from database import get_db
from models.workspace import Workspace
from models.exception_case import ExceptionCase
from models.audit import AuditLog
from schemas import (
    FullIntakePayload, ExceptionCaseRead, IntakeResponse, ZendeskWebhookPayload
)

router = APIRouter(tags=["intake"])


# ── Structured intake (instrumented agents) ────────────────────────────────────

@router.post("/intake/full", response_model=IntakeResponse, status_code=201)
async def intake_full(
    payload: FullIntakePayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a full 6-field escalation package from an instrumented AI agent.
    Produces maximum value: rich context for retrieval and recommendation.
    """
    await _assert_workspace(db, payload.workspace_id)

    case = ExceptionCase(
        workspace_id=payload.workspace_id,
        source="api",
        intake_mode="full",
        customer_message=payload.customer_message,
        escalation_reason=payload.escalation_reason,
        agent_trace=payload.agent_trace,
        attempted_actions=payload.attempted_actions,
        missing_information=payload.missing_information,
        policy_reference=payload.policy_reference,
        status="open",
    )
    db.add(case)
    await db.flush()

    _add_audit(db, case, "exception_received", "system")
    enriched = ExceptionCaseRead.model_validate(case)

    return IntakeResponse(
        exception_case=enriched,
        message="Full escalation package received.",
        next_step="classification queued",
    )


# ── Minimal intake (Zendesk webhook) ─────────────────────────────────────────

@router.post("/webhooks/zendesk/{workspace_id}", status_code=201)
async def zendesk_webhook(
    workspace_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a Zendesk ticket creation event.
    Validates HMAC signature, extracts customer message, creates minimal exception case.
    Specialist never needs to leave Zendesk — this is the no-instrumentation entry point.
    """
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    # Validate Zendesk webhook signature
    body = await request.body()
    if workspace.zendesk_webhook_secret:
        signature = request.headers.get("X-Zendesk-Webhook-Signature", "")
        expected = hmac.new(
            workspace.zendesk_webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    import json
    try:
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    ticket_id = str(data.get("ticket_id") or data.get("id", ""))
    description = data.get("ticket_description") or data.get("description", "")
    subject = data.get("ticket_subject") or data.get("subject", "")

    if not description:
        raise HTTPException(status_code=400, detail="ticket_description is required.")

    # Check for duplicate (same Zendesk ticket)
    existing = await db.execute(
        select(ExceptionCase).where(
            ExceptionCase.zendesk_ticket_id == ticket_id,
            ExceptionCase.workspace_id == workspace_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"status": "duplicate", "message": "Case already exists for this ticket."}

    # Infer escalation reason from ticket tags or subject
    escalation_reason = f"Agent escalated: {subject}" if subject else "Agent escalated case"

    case = ExceptionCase(
        workspace_id=workspace_id,
        source="zendesk_webhook",
        intake_mode="minimal",
        customer_message=description,
        escalation_reason=escalation_reason,
        zendesk_ticket_id=ticket_id,
        status="open",
    )
    db.add(case)
    await db.flush()

    _add_audit(db, case, "exception_received", "zendesk_webhook")

    return {
        "status": "created",
        "exception_case_id": str(case.id),
        "message": "Minimal intake created from Zendesk webhook. Sidebar will surface shortly.",
    }


# ── List exception cases for a workspace ──────────────────────────────────────

@router.get("/workspaces/{workspace_id}/cases", response_model=list[ExceptionCaseRead])
async def list_cases(
    workspace_id: UUID,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List exception cases for a workspace with optional status and severity filters."""
    await _assert_workspace(db, workspace_id)

    query = select(ExceptionCase).where(
        ExceptionCase.workspace_id == workspace_id
    ).order_by(ExceptionCase.received_at.desc()).limit(limit).offset(offset)

    if status:
        query = query.where(ExceptionCase.status == status)
    if severity:
        query = query.where(ExceptionCase.severity == severity)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/cases/{case_id}", response_model=ExceptionCaseRead)
async def get_case(case_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single exception case by ID."""
    result = await db.execute(select(ExceptionCase).where(ExceptionCase.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Exception case not found.")
    return case


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _assert_workspace(db: AsyncSession, workspace_id: UUID) -> None:
    result = await db.execute(
        select(Workspace.id).where(Workspace.id == workspace_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workspace not found.")


def _add_audit(db: AsyncSession, case: ExceptionCase, action: str, actor: str) -> None:
    db.add(AuditLog(
        workspace_id=case.workspace_id,
        entity_type="exception_case",
        entity_id=case.id,
        action=action,
        actor=actor,
        new_value={
            "source": case.source,
            "intake_mode": case.intake_mode,
            "zendesk_ticket_id": case.zendesk_ticket_id,
        },
    ))
