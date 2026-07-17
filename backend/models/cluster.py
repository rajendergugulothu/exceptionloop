from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
import uuid
from database import Base


class ExceptionCluster(Base):
    """
    Recurring exception pattern identified by the clustering pipeline.
    Must pass purity check (>=80%) before advancing to readiness scoring.
    pipeline_stage maps to the exception pipeline kanban view.
    """

    __tablename__ = "exception_clusters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    purity_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # % of reviewer-agreed cases; must be >=0.80 to advance
    resolution_consistency: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # % of cases resolved with same steps
    first_seen_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="forming"
    )
    # forming | purity_review | ready_for_scoring | scored
    # | workflow_generated | approved | in_development | shipped
    # Pipeline view mapping:
    #   candidates: forming, purity_review, ready_for_scoring, scored, workflow_generated
    #   approved: approved
    #   in_development: in_development
    #   shipped: shipped

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="clusters")
    readiness_score: Mapped["ReadinessScore | None"] = relationship(
        back_populates="cluster", uselist=False
    )
    workflow_spec: Mapped["WorkflowSpec | None"] = relationship(
        back_populates="cluster", uselist=False
    )


class ReadinessScore(Base):
    """
    8-dimension automation readiness assessment per cluster.
    Generated after cluster purity check passes.
    """

    __tablename__ = "readiness_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exception_clusters.id"), nullable=False
    )

    # 8 dimensions — each scored 0-1
    frequency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_completeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # higher = lower risk (inverted so all dimensions are "higher is better")
    reversibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    policy_clarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    integration_stability_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    evaluation_feasibility_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    total_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # weighted average
    blockers: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list
    )  # dimension names below threshold

    scored_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    scored_by: Mapped[str] = mapped_column(
        String(20), default="system"
    )  # system | human_override

    # Relationships
    cluster: Mapped["ExceptionCluster"] = relationship(back_populates="readiness_score")


class WorkflowSpec(Base):
    """
    Draft automation workflow generated from clustered human resolutions.
    Each step in `steps` (JSONB) embeds source_case_ids — the real resolution
    examples that produced it. This is the Marcus Hernandez trust condition.
    """

    __tablename__ = "workflow_specs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exception_clusters.id"), nullable=False
    )
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    required_inputs: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    steps: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False
    )
    # Each step: {"description": "...", "source_case_ids": ["uuid1", "uuid2"]}
    # source_case_ids links each step to the real resolutions that produced it
    edge_cases: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_cases: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_stage: Mapped[str] = mapped_column(
        String(30), default="candidates"
    )  # candidates | approved | in_development | shipped
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deployed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    cluster: Mapped["ExceptionCluster"] = relationship(back_populates="workflow_spec")
