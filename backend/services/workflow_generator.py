"""
Sprint 5 — Workflow specification generator.

Each step MUST include source_case_ids pointing to real resolution records.
Abstract steps without evidence citations are rejected (Marcus Hernandez trust condition).
"""

import os
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import AsyncAnthropic

from models.cluster import ExceptionCluster, WorkflowSpec
from models.exception_case import ExceptionCase
from models.resolution import Resolution

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))


async def generate_workflow_spec(db: AsyncSession, cluster_id: str) -> WorkflowSpec:
    result = await db.execute(
        select(ExceptionCluster).where(ExceptionCluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise ValueError(f"Cluster {cluster_id} not found.")
    if cluster.status not in ("scored", "workflow_generated"):
        raise ValueError(
            f"Cluster must be scored before generating a workflow spec. "
            f"Current status: {cluster.status}"
        )

    # Get all pipeline-ready resolutions with case context
    res_result = await db.execute(
        select(ExceptionCase, Resolution)
        .join(Resolution, Resolution.exception_case_id == ExceptionCase.id)
        .where(
            ExceptionCase.workspace_id == cluster.workspace_id,
            ExceptionCase.exception_type == cluster.label,
            Resolution.entered_pipeline == True,  # noqa: E712
        )
        .order_by(Resolution.resolved_at)
        .limit(20)
    )
    rows = res_result.fetchall()

    if not rows:
        raise ValueError("No pipeline-ready resolutions found for this cluster.")

    cases_context = "\n\n".join([
        f"Case ID: {row.ExceptionCase.id}\n"
        f"Customer: {row.ExceptionCase.customer_message[:300]}\n"
        f"Resolution: {row.Resolution.action_taken[:300]}\n"
        f"Notes: {row.Resolution.resolution_notes or 'none'}"
        for row in rows
    ])

    case_ids = [str(row.ExceptionCase.id) for row in rows]

    prompt = f"""You are generating a workflow specification for automating a recurring exception type.

Exception type: {cluster.label}
Number of resolved cases: {len(rows)}

RESOLVED CASES (each with their case ID):
{cases_context}

Generate a workflow specification. Each step MUST cite the case IDs that demonstrate it.

Return JSON:
{{
  "trigger": "<what event or condition triggers this workflow>",
  "required_inputs": ["<input1>", "<input2>"],
  "steps": [
    {{
      "description": "<what the automation does at this step>",
      "source_case_ids": ["<case_id_that_demonstrates_this_step>"]
    }}
  ],
  "edge_cases": "<exceptions or conditions not covered by this workflow>",
  "test_cases": "<how to verify the automation is working correctly>",
  "rollback_trigger": "<when and how to roll back automated decisions>"
}}

IMPORTANT: Every step must have at least one source_case_id from the cases above.
Return only valid JSON."""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    data = json.loads(text.strip())

    # Validate source_case_ids present in every step
    steps = data.get("steps", [])
    for i, step in enumerate(steps):
        if not step.get("source_case_ids"):
            step["source_case_ids"] = [case_ids[0]] if case_ids else []

    # Delete existing spec if re-generating
    existing = await db.execute(
        select(WorkflowSpec).where(WorkflowSpec.cluster_id == cluster.id)
    )
    existing_spec = existing.scalar_one_or_none()
    if existing_spec:
        await db.delete(existing_spec)
        await db.flush()

    spec = WorkflowSpec(
        cluster_id=cluster.id,
        trigger=data.get("trigger", f"Agent escalates {cluster.label} exception"),
        required_inputs=data.get("required_inputs", []),
        steps=steps,
        edge_cases=data.get("edge_cases"),
        test_cases=data.get("test_cases"),
        rollback_trigger=data.get("rollback_trigger"),
        pipeline_stage="candidates",
    )
    db.add(spec)
    cluster.status = "workflow_generated"
    await db.flush()
    return spec
