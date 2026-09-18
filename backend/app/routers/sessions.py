"""编辑会话路由：协议与状态码翻译；规则与事务在服务层。

会话接口全程不碰 Redis 与队列——纯同步 CRUD 事务。
"""
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.db import SessionDep
from app.deps import CurrentUser
from app.schemas.session import (
    HistoryOut,
    SessionCreateIn,
    SessionDetailOut,
    SessionOut,
    SessionPatchIn,
    wall_out,
)
from app.services import sessions

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionDetailOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreateIn, user: CurrentUser, session: SessionDep
) -> SessionDetailOut:
    try:
        row = await sessions.create(
            session,
            user.id,
            current_asset_id=payload.current_asset_id,
            asset_ids=payload.asset_ids,
            title=payload.title,
        )
    except sessions.AssetNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=sessions.ASSET_NOT_FOUND
        ) from None
    wall = [
        wall_out(position, asset)
        for position, asset in await sessions.wall_assets(session, row.id)
    ]
    return SessionDetailOut.of(row, wall)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SessionOut]:
    rows = await sessions.list_for_user(session, user.id, limit)
    return [
        SessionOut(
            id=row.id,
            title=row.title,
            revision=row.revision,
            current_asset_id=row.current_asset_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


async def _detail(session, user_id: uuid.UUID, session_id: uuid.UUID) -> SessionDetailOut:
    try:
        row = await sessions.get_for_user(session, user_id, session_id)
    except sessions.SessionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=sessions.SESSION_NOT_FOUND
        ) from None
    wall = [
        wall_out(position, asset)
        for position, asset in await sessions.wall_assets(session, row.id)
    ]
    return SessionDetailOut.of(row, wall)


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
async def get_session(
    session_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> SessionDetailOut:
    return await _detail(session, user.id, session_id)


@router.patch("/sessions/{session_id}", response_model=SessionDetailOut)
async def patch_session(
    session_id: uuid.UUID,
    payload: SessionPatchIn,
    user: CurrentUser,
    session: SessionDep,
) -> SessionDetailOut:
    try:
        await sessions.update(session, user.id, session_id, payload.model_dump(exclude_unset=True))
    except sessions.SessionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=sessions.SESSION_NOT_FOUND
        ) from None
    except sessions.AssetNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=sessions.ASSET_NOT_FOUND
        ) from None
    return await _detail(session, user.id, session_id)


@router.get("/sessions/{session_id}/history", response_model=list[HistoryOut])
async def get_session_history(
    session_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> list[HistoryOut]:
    try:
        rows = await sessions.history_of(session, user.id, session_id)
    except sessions.SessionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=sessions.SESSION_NOT_FOUND
        ) from None
    return [HistoryOut.of(row) for row in rows]
