"""
Sprint 2 — Exception classifier.

Deterministic rules first, Claude fallback for ambiguous cases.
Sets exception_type, severity, sla_tier, recommended_owner on the case.
"""

import os
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import AsyncAnthropic

from models.exception_case import ExceptionCase

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

DETERMINISTIC_RULES = {
    "refund_split": ["refund split", "loyalty points", "partial refund", "cash and points"],
    "account_verification": ["verify account", "identity verification", "account locked", "cannot verify"],
    "policy_ambiguity": ["policy unclear", "policy ambiguous", "policy conflict", "not specified in policy"],
    "high_value_transaction": ["$500", "$1000", "$2000", "high value", "large refund"],
    "fraud_indicator": ["fraud", "chargeback", "dispute", "unauthorized"],
    "missing_data": ["missing information", "incomplete", "no order found", "cannot retrieve"],
}

SEVERITY_MAP = {
    "fraud_indicator": "critical",
    "high_value_transaction": "high",
    "refund_split": "medium",
    "policy_ambiguity": "medium",
    "account_verification": "medium",
    "missing_data": "low",
}

SLA_MAP = {
    "critical": "urgent",
    "high": "urgent",
    "medium": "standard",
    "low": "low",
}

OWNER_MAP = {
    "fraud_indicator": "fraud_team",
    "high_value_transaction": "senior_specialist",
    "refund_split": "exception_specialist",
    "policy_ambiguity": "policy_team",
    "account_verification": "account_team",
    "missing_data": "exception_specialist",
}


def _deterministic_classify(text: str) -> str | None:
    text_lower = text.lower()
    for exception_type, keywords in DETERMINISTIC_RULES.items():
        if any(kw in text_lower for kw in keywords):
            return exception_type
    return None


async def _llm_classify(customer_message: str, escalation_reason: str) -> dict:
    prompt = f"""Classify this AI agent exception case.

Customer message: {customer_message}
Escalation reason: {escalation_reason}

Return JSON with exactly these fields:
{{
  "exception_type": "<one of: refund_split | account_verification | policy_ambiguity | high_value_transaction | fraud_indicator | missing_data | other>",
  "severity": "<one of: critical | high | medium | low>",
  "sla_tier": "<one of: urgent | standard | low>",
  "recommended_owner": "<one of: fraud_team | senior_specialist | exception_specialist | policy_team | account_team>"
}}

Return only valid JSON, no explanation."""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


async def classify_case(db: AsyncSession, case_id: str) -> ExceptionCase:
    result = await db.execute(
        select(ExceptionCase).where(ExceptionCase.id == case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError(f"Case {case_id} not found.")

    combined = f"{case.customer_message} {case.escalation_reason}"
    exception_type = _deterministic_classify(combined)

    if exception_type:
        severity = SEVERITY_MAP.get(exception_type, "medium")
        sla_tier = SLA_MAP.get(severity, "standard")
        recommended_owner = OWNER_MAP.get(exception_type, "exception_specialist")
    else:
        try:
            result_llm = await _llm_classify(case.customer_message, case.escalation_reason)
            exception_type = result_llm.get("exception_type", "other")
            severity = result_llm.get("severity", "medium")
            sla_tier = result_llm.get("sla_tier", "standard")
            recommended_owner = result_llm.get("recommended_owner", "exception_specialist")
        except Exception:
            exception_type = "other"
            severity = "medium"
            sla_tier = "standard"
            recommended_owner = "exception_specialist"

    case.exception_type = exception_type
    case.severity = severity
    case.sla_tier = sla_tier
    case.recommended_owner = recommended_owner
    await db.flush()
    return case
