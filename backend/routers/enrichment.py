"""Sprint 2 — Enrichment router: classify → embed → retrieve → recommend."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

from database import get_db
from models.exception_case import ExceptionCase
from models.recommendation import Recommendation
from models.similar_case_result import SimilarCaseResult
from models.resolution import Resolution
from services.classifier import classify_case
from services.embeddings import embed_case, retrieve_similar_cases
from services.recommender import generate_recommendation

router = APIRouter(tags=["enrichment"])


class EnrichmentResponse(BaseModel):
    case_id: UUID
    exception_type: str | None
    severity: str | None
    sla_tier: str | None
    similar_cases_found: int
    recommendation_confidence: float | None
    proposed_steps: str | None
    uncertainty_notes: str | None
    message: str


class SimilarCaseRead(BaseModel):
    rank: int
    case_id: UUID
    customer_message: str
    exception_type: str | None
    severity: str | None
    resolution: str
    similarity_score: float


class RecommendationRead(BaseModel):
    id: UUID
    exception_case_id: UUID
    proposed_steps: str
    evidence_summary: str | None
    similar_case_ids: list[str]
    confidence_score: float | None
    uncertainty_notes: str | None
    generated_at: datetime

    model_config = {"from_attributes": True}


@router.post("/enrich/{case_id}", response_model=EnrichmentResponse)
async def enrich_case(case_id: UUID, db: AsyncSession = Depends(get_db)):
    """Run classify → embed → retrieve → recommend pipeline."""
    try:
        case = await classify_case(db, str(case_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        case = await embed_case(db, str(case_id))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    similar_cases = []
    try:
        similar_cases = await retrieve_similar_cases(db, str(case_id))
    except Exception:
        pass

    try:
        rec = await generate_recommendation(db, str(case_id), similar_cases)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {e}")

    return EnrichmentResponse(
        case_id=case_id,
        exception_type=case.exception_type,
        severity=case.severity,
        sla_tier=case.sla_tier,
        similar_cases_found=len(similar_cases),
        recommendation_confidence=rec.confidence_score,
        proposed_steps=rec.proposed_steps,
        uncertainty_notes=rec.uncertainty_notes,
        message=(
            f"Enrichment complete. {len(similar_cases)} similar case(s) found. "
            f"Recommendation generated with {round((rec.confidence_score or 0)*100)}% confidence."
        ),
    )


@router.get("/cases/{case_id}/similar", response_model=list[SimilarCaseRead])
async def get_similar_cases(case_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SimilarCaseResult)
        .where(SimilarCaseResult.exception_case_id == case_id)
        .order_by(SimilarCaseResult.rank)
    )
    results = result.scalars().all()
    if not results:
        return []

    output = []
    for sr in results:
        case_result = await db.execute(
            select(ExceptionCase).where(ExceptionCase.id == sr.matched_case_id)
        )
        matched = case_result.scalar_one_or_none()
        if matched:
            res_result = await db.execute(
                select(Resolution).where(Resolution.exception_case_id == matched.id)
            )
            res = res_result.scalar_one_or_none()
            output.append(SimilarCaseRead(
                rank=sr.rank,
                case_id=matched.id,
                customer_message=matched.customer_message,
                exception_type=matched.exception_type,
                severity=matched.severity,
                resolution=res.action_taken if res else "not resolved",
                similarity_score=sr.similarity_score,
            ))
    return output


@router.get("/cases/{case_id}/recommendation", response_model=RecommendationRead)
async def get_recommendation(case_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Recommendation).where(Recommendation.exception_case_id == case_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="No recommendation found. Run /enrich/{case_id} first.")
    return rec
