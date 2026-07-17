"""
Sprint 4 — Clustering pipeline.

Groups resolved pipeline-ready cases by exception_type.
Requires >= 3 cases of the same type to form a cluster.
Purity check >= 80% required before advancing to readiness scoring.
"""

from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.exception_case import ExceptionCase
from models.resolution import Resolution
from models.cluster import ExceptionCluster


async def run_clustering(db: AsyncSession, workspace_id: str) -> list[ExceptionCluster]:
    # Get all pipeline-ready resolutions for this workspace
    result = await db.execute(
        select(
            ExceptionCase.exception_type,
            func.count(ExceptionCase.id).label("case_count"),
            func.min(ExceptionCase.received_at).label("first_seen"),
            func.max(ExceptionCase.received_at).label("last_seen"),
        )
        .join(Resolution, Resolution.exception_case_id == ExceptionCase.id)
        .where(
            ExceptionCase.workspace_id == workspace_id,
            Resolution.entered_pipeline == True,  # noqa: E712
            ExceptionCase.exception_type.isnot(None),
        )
        .group_by(ExceptionCase.exception_type)
        .having(func.count(ExceptionCase.id) >= 3)
    )
    rows = result.fetchall()

    clusters = []
    for row in rows:
        # Check if cluster already exists for this type
        existing = await db.execute(
            select(ExceptionCluster).where(
                ExceptionCluster.workspace_id == workspace_id,
                ExceptionCluster.label == row.exception_type,
            )
        )
        cluster = existing.scalar_one_or_none()

        if cluster:
            cluster.case_count = row.case_count
            cluster.last_seen_at = row.last_seen
        else:
            cluster = ExceptionCluster(
                workspace_id=workspace_id,
                label=row.exception_type,
                case_count=row.case_count,
                first_seen_at=row.first_seen,
                last_seen_at=row.last_seen,
                status="forming",
            )
            db.add(cluster)

        await db.flush()
        clusters.append(cluster)

    return clusters


async def assess_purity(
    db: AsyncSession,
    cluster_id: str,
    reviewer: str,
    purity_score: float,
    notes: str | None,
) -> ExceptionCluster:
    result = await db.execute(
        select(ExceptionCluster).where(ExceptionCluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise ValueError(f"Cluster {cluster_id} not found.")

    cluster.purity_score = purity_score

    if purity_score >= 0.80:
        cluster.status = "ready_for_scoring"
    else:
        cluster.status = "purity_review"

    await db.flush()
    return cluster
