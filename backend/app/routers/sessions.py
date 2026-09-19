"""编辑会话路由：协议与状态码翻译；规则与事务在服务层。

会话接口全程不碰队列——撤销/重做是快照恢复的同步事务；tools 端点受理后
由 services.tools 分叉（文档工具同步执行、像素工具投队列）。
"""
import uuid

import redis.exceptions
from fastapi import APIRouter, HTTPException, Query, status

from app.db import SessionDep
from app.deps import CurrentUser
from app.schemas.agent import MessageIn, TurnOut
from app.schemas.run import RunOut
from app.schemas.session import (
    HistoryOut,
    SessionCreateIn,
    SessionDetailOut,
    SessionOut,
    SessionPatchIn,
    ToolInvokeIn,
    ToolInvokeOut,
    wall_out,
)
from app.services import agent as agent_service
from app.services import sessions, tools

router = APIRouter(tags=["sessions"])

NO_UNDO_MESSAGE = "没有可撤销的操作"
NO_REDO_MESSAGE = "没有可重做的操作"


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
            history_seq=row.history_seq,
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
    previous = await sessions.previous_document(session, row)
    can_undo, can_redo = await sessions.undo_state(session, row)
    return SessionDetailOut.of(
        row, wall, previous_document=previous, can_undo=can_undo, can_redo=can_redo
    )


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


@router.post(
    "/sessions/{session_id}/tools",
    response_model=ToolInvokeOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def invoke_session_tool(
    session_id: uuid.UUID,
    payload: ToolInvokeIn,
    user: CurrentUser,
    session: SessionDep,
) -> ToolInvokeOut:
    """界面直发工具：202 受理即完成也是受理——同步工具响应一次带回终态 run 与新会话。"""
    try:
        row = await sessions.get_for_user(session, user.id, session_id)
    except sessions.SessionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=sessions.SESSION_NOT_FOUND
        ) from None
    # 同步执行可能 rollback（失败落终态前）：会话与用户对象随后都会过期，
    # 之后只允许使用原始值——user_id / session_id 在此先捕获
    user_id = user.id
    try:
        run = await tools.submit(session, user_id, payload.tool, payload.params, session_id=row.id)
    except tools.InvalidParams as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None
    except tools.UnknownTool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="工具不存在"
        ) from None
    except redis.exceptions.RedisError:
        # 异步工具受理要投队列：队列不可达是环境故障而非用户错误，
        # 与生图受理同一 503 语义（同步文档工具不触碰这条路径）
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="队列服务暂时不可用，请稍后再试",
        ) from None
    return ToolInvokeOut(
        run=await RunOut.of(session, run),
        session=await _detail(session, user_id, session_id),
    )


@router.post("/sessions/{session_id}/undo", response_model=SessionDetailOut)
async def undo_session(
    session_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> SessionDetailOut:
    user_id = user.id  # undo 的并发落败路径会 rollback，之后只用原始值
    try:
        row = await sessions.get_for_user(session, user_id, session_id)
        await sessions.undo(session, row)
    except sessions.SessionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=sessions.SESSION_NOT_FOUND
        ) from None
    except sessions.CannotUndo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=NO_UNDO_MESSAGE
        ) from None
    return await _detail(session, user_id, session_id)


@router.post("/sessions/{session_id}/redo", response_model=SessionDetailOut)
async def redo_session(
    session_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> SessionDetailOut:
    user_id = user.id
    try:
        row = await sessions.get_for_user(session, user_id, session_id)
        await sessions.redo(session, row)
    except sessions.SessionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=sessions.SESSION_NOT_FOUND
        ) from None
    except sessions.CannotRedo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=NO_REDO_MESSAGE
        ) from None
    return await _detail(session, user_id, session_id)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=TurnOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_message(
    session_id: uuid.UUID, payload: MessageIn, user: CurrentUser, session: SessionDep
) -> TurnOut:
    """发一句话：规划失败也是 201，失败信息在 status/error 里——环境故障不抛 503。"""
    try:
        record = await sessions.get_for_user(session, user.id, session_id)
    except sessions.SessionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=sessions.SESSION_NOT_FOUND
        ) from None
    turn = await agent_service.respond(session, record, payload.text.strip())
    return TurnOut.of(turn)


@router.get("/sessions/{session_id}/messages", response_model=list[TurnOut])
async def get_messages(
    session_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> list[TurnOut]:
    try:
        await sessions.get_for_user(session, user.id, session_id)
    except sessions.SessionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=sessions.SESSION_NOT_FOUND
        ) from None
    rows = await agent_service.turns_of(session, user.id, session_id)
    return [TurnOut.of(row) for row in rows]
