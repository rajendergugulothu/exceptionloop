"""
Sprint 4 — 8-dimension automation readiness scoring.

Cluster must be in ready_for_scoring status (purity >= 80% passed).
Scores each dimension 0-1. Blockers = dimensions below 0.6 threshold.
"""

import os
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import AsyncAnthropic

from models.cluster import ExceptionCluster, ReadinessScore
from models.exception_case import ExceptionCase
from models.resolution import Resolution

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

BLOCKER_THRESHOLD = 0.6

DIMENSIONS = [
    "frequency_score",
    "consistency_score",
    "data_completeness_score",
    "risk_score",
    "reversibility_score",
    "policy_clarity_score",
    "integration_stability_score",
    "evaluation_feasibility_score",
]

WEIGHTS = {
    "frequency_score": 0.15,
    "consistency_score": 0.20,
    "data_completeness_score": 0.10,
    "risk_score": 0.15,
    "reversibility_score": 0.10,
    "policy_clarity_score": 0.15,
    "integration_stability_score": 0.10,
    "evaluation_feasibility_score": 0.05,
}


async def score_readiness(db: AsyncSession, cluster_id: str) -> ReadinessScore:
    result = await db.execute(
        select(ExceptionCluster).where(ExceptionCluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise ValueError(f"Cluster {cluster_id} not found.")
    if cluster.status not in ("ready_for_scoring", "scored", "workflow_generated"):
        raise ValueError(
            f"Cluster must pass purity review (>=80%) before readiness scoring. "
            f"Current status: {cluster.status}"
        )

    # Get sample resolutions for context
    res_result = await db.execute(
        select(ExceptionCase, Resolution)
        .join(Resolution, Resolution.exception_case_id == ExceptionCase.id)
        .where(
            ExceptionCase.workspace_id == cluster.workspace_id,
            ExceptionCase.exception_type == cluster.label,
            Resolution.entered_pipeline == True,  # noqa: E712
        )
        .limit(10)
    )
    rows = res_result.fetchall()

    resolution_samples = "\n".join([
        f"- {row.Resolution.action_taken[:200]}"
        for row in rows
    ])

    prompt = f"""You are assessing automation readiness for an exception cluster.

Cluster: {cluster.label}
Case count: {cluster.case_count}
Purity score: {cluster.purity_score:.0%}

Sample resolutions:
{resolution_samples or "No resolutions available."}

Score each dimension from 0.0 to 1.0:
- frequency_score: How often does this exception occur? (higher = more frequent = better ROI)
- consistency_score: How consistently are similar cases resolved the same way?
- data_completeness_score: Is the data needed to automate reliably available?
- risk_score: How safe is automation? (1.0 = very safe, 0.0 = high risk)
- reversibility_score: Can automated actions be easily reversed if wrong?
- policy_clarity_score: Is there clear policy guidance for all cases?
- integration_stability_score: Are the required integrations stable and well-documented?
- evaluation_feasibility_score: Can automated decisions be evaluated for correctness?

Return JSON:
{{
  "frequency_score": 0.0-1.0,
  "consistency_score": 0.0-1.0,
  "data_completeness_score": 0.0-1.0,
  "risk_score": 0.0-1.0,
  "reversibility_score": 0.0-1.0,
  "policy_clarity_score": 0.0-1.0,
  "integration_stability_score": 0.0-1.0,
  "evaluation_feasibility_score": 0.0-1.0
}}

Return only valid JSON."""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    scores = json.loads(text.strip())

    total = sum(scores.get(d, 0) * WEIGHTS[d] for d in DIMENSIONS)
    blockers = [d for d in DIMENSIONS if scores.get(d, 0) < BLOCKER_THRESHOLD]

    # Delete existing score if re-running
    existing = await db.execute(
        select(ReadinessScore).where(ReadinessScore.cluster_id == cluster.id)
    )
    existing_score = existing.scalar_one_or_none()
    if existing_score:
        await db.delete(existing_score)
        await db.flush()

    rs = ReadinessScore(
        cluster_id=cluster.id,
        total_score=round(total, 3),
        blockers=blockers,
        **{d: round(scores.get(d, 0), 3) for d in DIMENSIONS},
    )
    db.add(rs)
    cluster.status = "scored"
    await db.flush()
    return rs
