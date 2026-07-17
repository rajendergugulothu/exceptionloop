"""
Sprint 2 — Recommendation generator.

ALWAYS receives similar_cases as a parameter — never fetches them itself.
This is the architectural constraint that enforces retrieval-before-recommendation.
The LLM sees actual customer messages and resolutions from similar cases.
"""

import os
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import AsyncAnthropic

from models.exception_case import ExceptionCase
from models.recommendation import Recommendation

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))


async def generate_recommendation(
    db: AsyncSession,
    case_id: str,
    similar_cases: list[dict],
) -> Recommendation:
    result = await db.execute(
        select(ExceptionCase).where(ExceptionCase.id == case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError(f"Case {case_id} not found.")

    # Build similar cases context
    if similar_cases:
        cases_text = "\n\n".join([
            f"Case {i+1} (similarity: {sc['similarity_score']:.0%}):\n"
            f"  Customer: {sc['customer_message']}\n"
            f"  Resolution: {sc['resolution']}"
            for i, sc in enumerate(similar_cases)
        ])
        evidence_note = f"Based on {len(similar_cases)} similar resolved case(s)."
    else:
        cases_text = "No similar resolved cases found (cold start)."
        evidence_note = "No similar cases available — recommendation based on general policy reasoning."

    prompt = f"""You are an exception specialist assistant. A customer service AI agent has escalated a case it cannot handle.

CURRENT CASE:
Customer message: {case.customer_message}
Escalation reason: {case.escalation_reason}
Exception type: {case.exception_type or "unknown"}
Severity: {case.severity or "unknown"}
{f"Agent trace: {case.agent_trace}" if case.agent_trace else ""}
{f"Missing information: {case.missing_information}" if case.missing_information else ""}

SIMILAR RESOLVED CASES (shown to specialist before this recommendation):
{cases_text}

Provide a recommendation grounded in the similar cases above. Return JSON:
{{
  "proposed_steps": "<numbered step-by-step resolution, citing similar cases where relevant>",
  "evidence_summary": "<1-2 sentences on which similar cases informed this recommendation and why>",
  "confidence_score": <0.0 to 1.0>,
  "uncertainty_notes": "<what is unclear or would change the recommendation, or null>"
}}

Return only valid JSON."""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )

    text_response = response.content[0].text.strip()
    if text_response.startswith("```"):
        text_response = text_response.split("```")[1]
        if text_response.startswith("json"):
            text_response = text_response[4:]
    data = json.loads(text_response.strip())

    # Delete existing recommendation if re-running
    existing = await db.execute(
        select(Recommendation).where(Recommendation.exception_case_id == case.id)
    )
    existing_rec = existing.scalar_one_or_none()
    if existing_rec:
        await db.delete(existing_rec)
        await db.flush()

    rec = Recommendation(
        exception_case_id=case.id,
        proposed_steps=data.get("proposed_steps", ""),
        evidence_summary=data.get("evidence_summary", evidence_note),
        similar_case_ids=[sc["case_id"] for sc in similar_cases],
        confidence_score=data.get("confidence_score"),
        uncertainty_notes=data.get("uncertainty_notes"),
    )
    db.add(rec)
    await db.flush()
    return rec
