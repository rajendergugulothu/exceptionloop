"""Sprint 4+5 — Cluster, readiness, workflow spec, pipeline routers."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime, timezone
from typing import Literal

from database import get_db
from models.cluster import ExceptionCluster, ReadinessScore, WorkflowSpec
from models.audit import AuditLog
from services.clustering import run_clustering, assess_purity
from services.readiness import score_readiness
from services.workflow_generator import generate_workflow_spec

router = APIRouter(tags=["clusters"])


class ClusterRead(BaseModel):
    id: UUID
    workspace_id: UUID
    label: str
    case_count: int
    purity_score: float | None
    resolution_consistency: float | None
    status: str
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    model_config = {"from_attributes": True}


class ReadinessScoreRead(BaseModel):
    id: UUID
    cluster_id: UUID
    frequency_score: float | None
    consistency_score: float | None
    data_completeness_score: float | None
    risk_score: float | None
    reversibility_score: float | None
    policy_clarity_score: float | None
    integration_stability_score: float | None
    evaluation_feasibility_score: float | None
    total_score: float | None
    blockers: list[str]
    scored_at: datetime
    model_config = {"from_attributes": True}


class WorkflowSpecRead(BaseModel):
    id: UUID
    cluster_id: UUID
    trigger: str
    required_inputs: list[str]
    steps: list[dict]
    edge_cases: str | None
    test_cases: str | None
    rollback_trigger: str | None
    pipeline_stage: str
    approved_by: str | None
    approved_at: datetime | None
    deployed_at: datetime | None
    model_config = {"from_attributes": True}


class PurityAssessment(BaseModel):
    reviewer: str
    purity_score: float = Field(..., ge=0.0, le=1.0)
    notes: str | None = None


class PipelineAdvance(BaseModel):
    actor: str
    new_stage: Literal["approved", "in_development", "shipped"]
    notes: str | None = None


class PipelineView(BaseModel):
    candidates: list[ClusterRead]
    approved: list[ClusterRead]
    in_development: list[ClusterRead]
    shipped: list[ClusterRead]
    total_patterns: int
    shipped_count: int


@router.post("/workspaces/{workspace_id}/cluster", response_model=list[ClusterRead])
async def trigger_clustering(workspace_id: UUID, db: AsyncSession = Depends(get_db)):
    clusters = await run_clustering(db, str(workspace_id))
    if not clusters:
        raise HTTPException(
            status_code=422,
            detail="No recurring patterns found. Need >= 3 pipeline-ready resolutions of the same exception type."
        )
    return clusters


@router.get("/workspaces/{workspace_id}/clusters", response_model=list[ClusterRead])
async def list_clusters(workspace_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ExceptionCluster)
        .where(ExceptionCluster.workspace_id == workspace_id)
        .order_by(ExceptionCluster.case_count.desc())
    )
    return result.scalars().all()


@router.get("/clusters/{cluster_id}", response_model=ClusterRead)
async def get_cluster(cluster_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExceptionCluster).where(ExceptionCluster.id == cluster_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Cluster not found.")
    return c


@router.post("/clusters/{cluster_id}/purity-review", response_model=ClusterRead)
async def submit_purity_review(cluster_id: UUID, payload: PurityAssessment, db: AsyncSession = Depends(get_db)):
    try:
        cluster = await assess_purity(db, str(cluster_id), payload.reviewer, payload.purity_score, payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return cluster


@router.post("/clusters/{cluster_id}/score-readiness", response_model=ReadinessScoreRead)
async def run_readiness_scoring(cluster_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        score = await score_readiness(db, str(cluster_id))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return score


@router.get("/clusters/{cluster_id}/readiness", response_model=ReadinessScoreRead)
async def get_readiness(cluster_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ReadinessScore).where(ReadinessScore.cluster_id == cluster_id))
    rs = result.scalar_one_or_none()
    if not rs:
        raise HTTPException(status_code=404, detail="No readiness score yet. Run /score-readiness first.")
    return rs


@router.post("/clusters/{cluster_id}/generate-spec", response_model=WorkflowSpecRead)
async def generate_spec(cluster_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        spec = await generate_workflow_spec(db, str(cluster_id))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return spec


@router.get("/clusters/{cluster_id}/spec", response_model=WorkflowSpecRead)
async def get_spec(cluster_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkflowSpec).where(WorkflowSpec.cluster_id == cluster_id))
    spec = result.scalar_one_or_none()
    if not spec:
        raise HTTPException(status_code=404, detail="No spec yet. Run /generate-spec first.")
    return spec


@router.post("/specs/{spec_id}/advance", response_model=WorkflowSpecRead)
async def advance_pipeline_stage(spec_id: UUID, payload: PipelineAdvance, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkflowSpec).where(WorkflowSpec.id == spec_id))
    spec = result.scalar_one_or_none()
    if not spec:
        raise HTTPException(status_code=404, detail="Workflow spec not found.")

    cluster_result = await db.execute(select(ExceptionCluster).where(ExceptionCluster.id == spec.cluster_id))
    cluster = cluster_result.scalar_one()

    old_stage = spec.pipeline_stage
    spec.pipeline_stage = payload.new_stage
    cluster.status = payload.new_stage

    if payload.new_stage == "approved":
        spec.approved_by = payload.actor
        spec.approved_at = datetime.now(timezone.utc)
    if payload.new_stage == "shipped":
        spec.deployed_at = datetime.now(timezone.utc)

    db.add(AuditLog(
        workspace_id=cluster.workspace_id,
        entity_type="workflow_spec",
        entity_id=spec.id,
        action="pipeline_stage_advanced",
        actor=payload.actor,
        old_value={"stage": old_stage},
        new_value={"stage": payload.new_stage},
    ))
    return spec


@router.get("/workspaces/{workspace_id}/pipeline", response_model=PipelineView)
async def get_pipeline_view(workspace_id: UUID, db: AsyncSession = Depends(get_db)):
    all_clusters = (await db.execute(
        select(ExceptionCluster).where(ExceptionCluster.workspace_id == workspace_id)
    )).scalars().all()

    CANDIDATE_STATUSES = {"forming", "purity_review", "ready_for_scoring", "scored", "workflow_generated"}
    return PipelineView(
        candidates=[c for c in all_clusters if c.status in CANDIDATE_STATUSES],
        approved=[c for c in all_clusters if c.status == "approved"],
        in_development=[c for c in all_clusters if c.status == "in_development"],
        shipped=[c for c in all_clusters if c.status == "shipped"],
        total_patterns=len(all_clusters),
        shipped_count=len([c for c in all_clusters if c.status == "shipped"]),
    )
