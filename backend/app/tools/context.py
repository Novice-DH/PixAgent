"""工具层公共上下文：会话装载、画布文档读取、拍平合成——handler 的公共前置。

LayerMissing / EditError / MattingError 在各工具 handler 里翻译为 ToolError
（可直接展示的失败），由统一外壳落 failed；工具层之下是纯函数领域包（app/edits/）。
"""
import io
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.edits import render
from app.layers import LayerDocument, LayerKind
from app.models.edit_session import EditSession
from app.models.tool_run import ToolRun
from app.services import assets as assets_service
from app.services import sessions
from app.storage import get_object


class ToolError(Exception):
    """可直接展示给用户的工具失败——统一外壳透出原文落 failed。"""


async def require_session(session: AsyncSession, run: ToolRun) -> EditSession:
    """装载工具作用的编辑会话；缺失/已删都是明确失败而不是静默成功。"""
    if run.session_id is None:
        raise ToolError("此工具需要在编辑会话中使用")
    try:
        return await sessions.load(session, run.session_id)
    except sessions.SessionNotFound:
        raise ToolError("会话不存在") from None


def current_document(row: EditSession) -> LayerDocument:
    return LayerDocument.model_validate(row.document)


async def flatten_session(
    session: AsyncSession,
    row: EditSession,
    document: LayerDocument | None = None,
    *,
    background: tuple[int, ...] = render.WHITE,
) -> bytes:
    """把会话画布拍平为 PNG 字节：像素工具的作用对象是当前画布的合成结果。

    拆层之前画布与单图层等价，这个等价将来拆层后依然成立（拍平自动处理多层）。
    """
    doc = document if document is not None else current_document(row)
    images: dict[str, bytes] = {}
    for layer in doc.layers:
        if (
            layer.kind is LayerKind.image
            and layer.visible
            and layer.asset_id is not None
            and layer.asset_id not in images
        ):
            asset = await assets_service.get_for_user(
                session, row.user_id, uuid.UUID(layer.asset_id)
            )
            if asset is None:
                raise ToolError("画布引用的素材不存在")
            images[layer.asset_id] = await get_object(asset.storage_key)
    flat = render.flatten(doc, images, background=background)
    buffer = io.BytesIO()
    flat.save(buffer, format="PNG")
    return buffer.getvalue()
