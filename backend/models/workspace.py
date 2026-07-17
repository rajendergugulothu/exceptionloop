from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_type: Mapped[str] = mapped_column(
        String(50), default="support"
    )  # support | operations | finance | onboarding
    zendesk_webhook_secret: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    exception_cases: Mapped[list["ExceptionCase"]] = relationship(
        back_populates="workspace"
    )
    clusters: Mapped[list["ExceptionCluster"]] = relationship(
        back_populates="workspace"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="workspace")
