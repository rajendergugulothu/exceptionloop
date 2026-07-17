"""Sprint 3 — Resolution, quality review, new pattern flag routers."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Literal

from database import get_db
from models.resolution import Resolution
from models.quality_review import QualityReview
from models.new_pattern_flag import NewPatternFlag
from models.exception_case import ExceptionCase
from services.resolution_service import record_resolution, adjudicate_quality_review, flag_new_pattern

router = APIRouter(tags=["resolution"])


class ResolutionCreate(BaseModel):
    verdict: Literal["approved", "edited", "rejected"]
    action_taken: str = Field(..., min_length=1)
    resolved_by: str = Field(..., example="maya.okonkwo@nexagen.com")
    resolution_notes: str | None = None
    edit_delta: str | None = None
    usefulness_rating: int | None = Field(None, ge=1, le=5)

    def model_post_init(self, __context) -> None:
        if self.verdict == "rejected" and self.usefulness_rating is None:
            raise ValueError("usefulness_rating is required when rejecting a recommendation.")


class ResolutionRead(BaseModel):
    id: UUID
    exception_case_id: UUID
    verdict: str
    action_taken: str
    usefulness_rating: int | None
    resolved_by: str
    resolved_at: datetime
    entered_pipeline: bool
    model_config = {"from_attributes": True}


class AdjudicationRequest(BaseModel):
    reviewer: str
    decision: Literal["valid_signal", "noise", "escalate_to_ai_pm"]
    notes: str | None = None


class FlagRequest(BaseModel):
    flagged_by: str = Field(..., example="maya.okonkwo@nexagen.com")


class QualityReviewRead(BaseModel):
    id: UUID
    resolution_id: UUID
    triggered_by: str
    reviewer: str | None
    decision: str | None
    notes: str | None
    reviewed_at: datetime | None
    model_config = {"from_attributes": True}


class NewPatternFlagRead(BaseModel):
    id: UUID
    exception_case_id: UUID
    flagged_by: str
    occurrence_count: int
    status: str
    flagged_at: datetime
    model_config = {"from_attributes": True}


@router.post("/cases/{case_id}/resolve", response_model=ResolutionRead, status_code=201)
async def resolve_case(case_id: UUID, payload: ResolutionCreate, db: AsyncSession = Depends(get_db)):
    try:
        resolution = await record_resolution(
            db=db,
            case_id=str(case_id),
            verdict=payload.verdict,
            action_taken=payload.action_taken,
            resolved_by=payload.resolved_by,
            resolution_notes=payload.resolution_notes,
            edit_delta=payload.edit_delta,
            usefulness_rating=payload.usefulness_rating,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return resolution


@router.post("/cases/{case_id}/flag-new-pattern", response_model=NewPatternFlagRead, status_code=201)
async def flag_case_as_new_pattern(case_id: UUID, payload: FlagRequest, db: AsyncSession = Depends(get_db)):
    try:
        flag = await flag_new_pattern(db, str(case_id), payload.flagged_by)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return flag


@router.get("/workspaces/{workspace_id}/quality-reviews", response_model=list[QualityReviewRead])
async def list_pending_reviews(workspace_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(QualityReview)
        .join(Resolution, QualityReview.resolution_id == Resolution.id)
        .join(ExceptionCase, Resolution.exception_case_id == ExceptionCase.id)
        .where(
            ExceptionCase.workspace_id == workspace_id,
            QualityReview.decision == None,  # noqa: E711
        )
        .order_by(QualityReview.id)
    )
    return result.scalars().all()


@router.post("/quality-reviews/{review_id}/adjudicate", response_model=QualityReviewRead)
async def adjudicate(review_id: UUID, payload: AdjudicationRequest, db: AsyncSession = Depends(get_db)):
    try:
        review = await adjudicate_quality_review(db, str(review_id), payload.reviewer, payload.decision, payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return review


@router.get("/workspaces/{workspace_id}/new-pattern-flags", response_model=list[NewPatternFlagRead])
async def list_new_pattern_flags(workspace_id: UUID, status: str = "open", db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(NewPatternFlag)
        .join(ExceptionCase, NewPatternFlag.exception_case_id == ExceptionCase.id)
        .where(ExceptionCase.workspace_id == workspace_id, NewPatternFlag.status == status)
        .order_by(NewPatternFlag.occurrence_count.desc())
    )
    return result.scalars().all()
