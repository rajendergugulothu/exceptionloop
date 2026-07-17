from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import uuid
from database import Base


class ExceptionCase(Base):
    __tablename__ = "exception_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )

    # Intake metadata
    source: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # api | zendesk_webhook | batch_upload
    intake_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="minimal"
    )  # full | minimal

    # Core case content (always present)
    customer_message: Mapped[str] = mapped_column(Text, nullable=False)
    escalation_reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Extended context (present in full intake, null in minimal)
    agent_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_actions: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_information: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_reference: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classification (set by classifier after intake)
    exception_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # critical | high | medium | low
    sla_tier: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # urgent | standard | low
    recommended_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(
        nullable=True
    )

    # Case status
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="open"
    )  # open | in_review | resolved | flagged

    # Zendesk integration
    zendesk_ticket_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Embedding for similarity search (1536 dims = text-embedding-3-small)
    # Null until embedding service processes the case
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )

    received_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="exception_cases")
    recommendation: Mapped["Recommendation | None"] = relationship(
        back_populates="exception_case", uselist=False
    )
    similar_results: Mapped[list["SimilarCaseResult"]] = relationship(
        back_populates="exception_case",
        foreign_keys="SimilarCaseResult.exception_case_id",
    )
    resolution: Mapped["Resolution | None"] = relationship(
        back_populates="exception_case", uselist=False
    )
    new_pattern_flag: Mapped["NewPatternFlag | None"] = relationship(
        back_populates="exception_case", uselist=False
    )
