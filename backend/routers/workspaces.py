from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from database import get_db
from models.workspace import Workspace
from models.exception_case import ExceptionCase
from schemas import WorkspaceCreate, WorkspaceRead

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("/", response_model=WorkspaceRead, status_code=201)
async def create_workspace(
    payload: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new ExceptionLoop workspace for one AI agent workflow."""
    workspace = Workspace(
        name=payload.name,
        agent_type=payload.agent_type,
        zendesk_webhook_secret=payload.zendesk_webhook_secret,
        created_by=payload.created_by,
    )
    db.add(workspace)
    await db.flush()

    result = WorkspaceRead.model_validate(workspace)
    result.case_count = 0
    return result


@router.get("/", response_model=list[WorkspaceRead])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """List all workspaces with their exception case counts."""
    result = await db.execute(
        select(Workspace).order_by(Workspace.created_at.desc()).limit(limit).offset(offset)
    )
    workspaces = result.scalars().all()

    if workspaces:
        ws_ids = [w.id for w in workspaces]
        count_result = await db.execute(
            select(ExceptionCase.workspace_id, func.count(ExceptionCase.id).label("cnt"))
            .where(ExceptionCase.workspace_id.in_(ws_ids))
            .group_by(ExceptionCase.workspace_id)
        )
        counts = {row.workspace_id: row.cnt for row in count_result}
    else:
        counts = {}

    output = []
    for ws in workspaces:
        item = WorkspaceRead.model_validate(ws)
        item.case_count = counts.get(ws.id, 0)
        output.append(item)
    return output


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a workspace by ID with case count."""
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    count_result = await db.execute(
        select(func.count(ExceptionCase.id))
        .where(ExceptionCase.workspace_id == workspace_id)
    )
    case_count = count_result.scalar() or 0

    item = WorkspaceRead.model_validate(workspace)
    item.case_count = case_count
    return item
