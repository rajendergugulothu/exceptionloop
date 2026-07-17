from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from database import Base


class Recommendation(Base):
    """Generated after similar-case retrieval — never before. Must cite source cases."""

    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    exception_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exception_cases.id"), nullable=False
    )
    proposed_steps: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    similar_case_ids: Mapped[list[str]] = mapped_column(
        ARRAY(UUID), default=list
    )  # IDs of cases cited in this recommendation
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    exception_case: Mapped["ExceptionCase"] = relationship(
        back_populates="recommendation"
    )


class SimilarCaseResult(Base):
    """Results of the similarity search for a given exception case."""

    __tablename__ = "similar_case_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    exception_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exception_cases.id"),
        nullable=False,
    )
    matched_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exception_cases.id"),
        nullable=False,
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    exception_case: Mapped["ExceptionCase"] = relationship(
        back_populates="similar_results",
        foreign_keys=[exception_case_id],
    )


class Resolution(Base):
    """
    The primary learning signal. One per exception case.
    entered_pipeline = False until quality gate passes.
    Low-usefulness rejections (usefulness_rating <= 2) route to quality_reviews.
    """

    __tablename__ = "resolutions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    exception_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exception_cases.id"), nullable=False
    )
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendations.id"), nullable=True
    )
    action_taken: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # approved | edited | rejected
    edit_delta: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # what changed if edited
    usefulness_rating: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 1-5: measures retrieval quality, not recommendation quality
    resolved_by: Mapped[str] = mapped_column(String(255), nullable=False)
    resolved_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    entered_pipeline: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # False until quality gate passes — enforced at data layer

    # Relationships
    exception_case: Mapped["ExceptionCase"] = relationship(back_populates="resolution")
    quality_review: Mapped["QualityReview | None"] = relationship(
        back_populates="resolution", uselist=False
    )


class QualityReview(Base):
    """
    Manager adjudication for low-usefulness rejections.
    Required before resolutions.entered_pipeline = True on flagged cases.
    """

    __tablename__ = "quality_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resolution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resolutions.id"), nullable=False
    )
    triggered_by: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # low_usefulness_rating | manual
    reviewer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # valid_signal | noise | escalate_to_ai_pm
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    resolution: Mapped["Resolution"] = relationship(back_populates="quality_review")


class NewPatternFlag(Base):
    """
    One-click flag from specialist: this case is genuinely novel.
    Routes to AI PM review queue. occurrence_count tracks re-appearances.
    """

    __tablename__ = "new_pattern_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    exception_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exception_cases.id"), nullable=False
    )
    flagged_by: Mapped[str] = mapped_column(String(255), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(
        Integer, default=1
    )  # increments if same novel pattern appears again
    ai_pm_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="open"
    )  # open | reviewed | converted_to_cluster
    flagged_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    exception_case: Mapped["ExceptionCase"] = relationship(
        back_populates="new_pattern_flag"
    )
