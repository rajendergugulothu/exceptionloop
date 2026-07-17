"""
Sprint 3 — Resolution capture service.

Quality gate: usefulness_rating <= 2 on rejection → entered_pipeline = False,
creates QualityReview record, routes to manager adjudication.
"""

from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.exception_case import ExceptionCase
from models.resolution import Resolution
from models.quality_review import QualityReview
from models.new_pattern_flag import NewPatternFlag
from models.audit import AuditLog


async def record_resolution(
    db: AsyncSession,
    case_id: str,
    verdict: str,
    action_taken: str,
    resolved_by: str,
    resolution_notes: str | None = None,
    edit_delta: str | None = None,
    usefulness_rating: int | None = None,
) -> Resolution:
    result = await db.execute(
        select(ExceptionCase).where(ExceptionCase.id == case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError(f"Case {case_id} not found.")

    # Quality gate: approved and edited resolutions always enter the pipeline
    # Rejected resolutions with usefulness_rating <= 2 are held for adjudication
    low_usefulness = (
        verdict == "rejected"
        and usefulness_rating is not None
        and usefulness_rating <= 2
    )
    entered_pipeline = not low_usefulness

    resolution = Resolution(
        exception_case_id=case.id,
        action_taken=action_taken,
        resolution_notes=resolution_notes,
        verdict=verdict,
        edit_delta=edit_delta,
        usefulness_rating=usefulness_rating,
        resolved_by=resolved_by,
        entered_pipeline=entered_pipeline,
    )
    db.add(resolution)
    await db.flush()

    # Create quality review if low usefulness
    if low_usefulness:
        review = QualityReview(
            resolution_id=resolution.id,
            triggered_by="low_usefulness_rating",
        )
        db.add(review)

    # Update case status
    case.status = "resolved"
    await db.flush()

    db.add(AuditLog(
        workspace_id=case.workspace_id,
        entity_type="resolution",
        entity_id=resolution.id,
        action="resolution_recorded",
        actor=resolved_by,
        new_value={
            "verdict": verdict,
            "entered_pipeline": entered_pipeline,
            "usefulness_rating": usefulness_rating,
        },
    ))
    return resolution


async def adjudicate_quality_review(
    db: AsyncSession,
    review_id: str,
    reviewer: str,
    decision: str,
    notes: str | None,
) -> QualityReview:
    result = await db.execute(
        select(QualityReview).where(QualityReview.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise ValueError(f"Quality review {review_id} not found.")

    review.reviewer = reviewer
    review.decision = decision
    review.notes = notes
    review.reviewed_at = datetime.now(timezone.utc)

    # Unlock pipeline if manager deems it a valid signal
    if decision == "valid_signal":
        res_result = await db.execute(
            select(Resolution).where(Resolution.id == review.resolution_id)
        )
        resolution = res_result.scalar_one_or_none()
        if resolution:
            resolution.entered_pipeline = True

    await db.flush()
    return review


async def flag_new_pattern(
    db: AsyncSession,
    case_id: str,
    flagged_by: str,
) -> NewPatternFlag:
    result = await db.execute(
        select(ExceptionCase).where(ExceptionCase.id == case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError(f"Case {case_id} not found.")

    # Check if a flag already exists for this case
    existing = await db.execute(
        select(NewPatternFlag).where(NewPatternFlag.exception_case_id == case.id)
    )
    flag = existing.scalar_one_or_none()
    if flag:
        flag.occurrence_count += 1
        await db.flush()
        return flag

    flag = NewPatternFlag(
        exception_case_id=case.id,
        flagged_by=flagged_by,
        occurrence_count=1,
        status="open",
    )
    db.add(flag)
    case.status = "flagged"
    await db.flush()
    return flag
