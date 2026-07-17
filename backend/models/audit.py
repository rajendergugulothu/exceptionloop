from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from database import Base


class AuditLog(Base):
    """
    Immutable append-only audit log.
    Required for EU AI Act Article 14 compliance (demonstrable human oversight).
    No rows are ever updated or deleted.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # exception_case | recommendation | resolution | quality_review
    # new_pattern_flag | cluster | readiness_score | workflow_spec
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    # exception_received | exception_classified | recommendation_generated
    # resolution_approved | resolution_rejected | quality_gate_passed
    # quality_gate_flagged | adjudication_completed | new_pattern_flagged
    # cluster_created | purity_reviewed | readiness_scored
    # workflow_spec_generated | pipeline_stage_advanced
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="audit_logs")
