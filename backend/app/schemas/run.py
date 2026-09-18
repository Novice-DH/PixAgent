"""生图任务契约：GenerateIn（入参校验）与 RunOut（任务快照响应）。

签名 URL 永不落库：RunOut.of() 每次现算——URL 是视图不是资产。
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.tool_run import RunStatus, ToolRun
from app.ratios import Ratio
from app.storage import signed_url

PROMPT_MAX_LENGTH = 1500


class GenerateIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=PROMPT_MAX_LENGTH)
    ratio: Ratio = Ratio.ONE_ONE
    count: int = Field(default=4, ge=1, le=6)
    negative_prompt: str | None = Field(default=None, max_length=PROMPT_MAX_LENGTH)
    seed: int | None = Field(default=None, ge=0, le=2147483647)
    reference_asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt 不能为空白")
        return value

    @field_validator("negative_prompt")
    @classmethod
    def blank_negative_becomes_none(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            return None
        return value

    def to_params(self) -> dict[str, Any]:
        """落库为 JSONB 的入参形态：枚举与 UUID 全部转为字符串。"""
        return self.model_dump(mode="json", exclude_none=True)


class CandidateOut(BaseModel):
    id: uuid.UUID
    width: int
    height: int
    url: str = ""  # 现算签名 URL，由 of() 填充


class RunOut(BaseModel):
    id: uuid.UUID
    tool: str
    status: RunStatus
    progress: int
    stage: str
    error: str | None
    candidates: list[CandidateOut]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    async def of(cls, session: AsyncSession, run: ToolRun) -> "RunOut":
        candidates: list[CandidateOut] = []
        asset_ids = ((run.result or {}).get("asset_ids") or []) if run.result else []
        if asset_ids:
            result = await session.execute(
                select(Asset).where(Asset.id.in_([uuid.UUID(a) for a in asset_ids]))
            )
            by_id = {asset.id: asset for asset in result.scalars()}
            candidates = [
                CandidateOut(
                    id=asset_id,
                    width=by_id[asset_id].width,
                    height=by_id[asset_id].height,
                    url=signed_url(by_id[asset_id].storage_key),
                )
                for asset_id in (uuid.UUID(a) for a in asset_ids)
                if asset_id in by_id
            ]
        return cls(
            id=run.id,
            tool=run.tool,
            status=run.status,
            progress=run.progress,
            stage=run.stage,
            error=run.error,
            candidates=candidates,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )
