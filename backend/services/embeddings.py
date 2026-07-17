"""
Sprint 2 — Embedding service.

Generates OpenAI text-embedding-3-small vectors and stores in pgvector.
Retrieval uses cosine similarity via pgvector <=> operator.
"""

import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from openai import AsyncOpenAI

from models.exception_case import ExceptionCase
from models.similar_case_result import SimilarCaseResult
from models.resolution import Resolution

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536
TOP_K = 5


def _build_case_text(case: ExceptionCase) -> str:
    parts = [case.customer_message, case.escalation_reason]
    if case.agent_trace:
        parts.append(case.agent_trace)
    if case.missing_information:
        parts.append(f"Missing: {case.missing_information}")
    if case.policy_reference:
        parts.append(f"Policy: {case.policy_reference}")
    return " | ".join(parts)


async def embed_case(db: AsyncSession, case_id: str) -> ExceptionCase:
    result = await db.execute(
        select(ExceptionCase).where(ExceptionCase.id == case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError(f"Case {case_id} not found.")

    case_text = _build_case_text(case)
    response = await openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=case_text,
    )
    case.embedding = response.data[0].embedding
    await db.flush()
    return case


async def retrieve_similar_cases(db: AsyncSession, case_id: str) -> list[dict]:
    result = await db.execute(
        select(ExceptionCase).where(ExceptionCase.id == case_id)
    )
    case = result.scalar_one_or_none()
    if not case or case.embedding is None:
        return []

    # Find resolved cases with embeddings, excluding the current case
    similar_query = await db.execute(
        text("""
            SELECT ec.id, ec.customer_message, ec.exception_type, ec.severity,
                   r.action_taken, r.resolution_notes,
                   1 - (ec.embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM exception_cases ec
            JOIN resolutions r ON r.exception_case_id = ec.id
            WHERE ec.id != :case_id
              AND ec.embedding IS NOT NULL
              AND r.entered_pipeline = true
            ORDER BY ec.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """),
        {
            "embedding": str(case.embedding),
            "case_id": str(case_id),
            "top_k": TOP_K,
        },
    )
    rows = similar_query.fetchall()

    # Delete old similar_case_results for this case
    await db.execute(
        text("DELETE FROM similar_case_results WHERE exception_case_id = :case_id"),
        {"case_id": case_id},
    )

    similar_cases = []
    for rank, row in enumerate(rows, start=1):
        scr = SimilarCaseResult(
            exception_case_id=case.id,
            matched_case_id=row.id,
            similarity_score=float(row.similarity),
            rank=rank,
        )
        db.add(scr)
        similar_cases.append({
            "rank": rank,
            "case_id": str(row.id),
            "customer_message": row.customer_message,
            "exception_type": row.exception_type,
            "severity": row.severity,
            "resolution": row.action_taken,
            "similarity_score": float(row.similarity),
        })

    await db.flush()
    return similar_cases
