"""对话契约：MessageIn（入参校验）与 PlanStepOut / TurnOut（响应）。

TurnOut.status 是 RunStatus 五值但只表示规划本身成败——执行状态在
ToolRun（步骤卡片经 useRun 读取），两层抽象不混用。
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.agent_run import AgentRun
from app.models.tool_run import RunStatus
from app.tools import label_of

MAX_MESSAGE = 1000


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_MESSAGE)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("消息不能为空白")
        return value


class PlanStepOut(BaseModel):
    tool: str
    label: str  # 注册表文案；步骤卡与历史列表共用
    run_id: uuid.UUID | None = None  # 校验被拒的步骤没有 run


class TurnOut(BaseModel):
    id: uuid.UUID
    revision: int  # 规划时的会话修订号（规划基准）
    goal: str
    reply: str
    status: RunStatus
    error: str | None
    created_at: datetime
    steps: list[PlanStepOut]

    @classmethod
    def of(cls, record: AgentRun) -> "TurnOut":
        steps = [
            PlanStepOut(
                tool=str(step.get("tool", "")),
                label=label_of(str(step.get("tool", ""))),
                run_id=uuid.UUID(step["run_id"]) if step.get("run_id") else None,
            )
            for step in (record.plan or [])
        ]
        return cls(
            id=record.id,
            revision=record.revision,
            goal=record.goal,
            reply=record.reply,
            status=record.status,
            error=record.error,
            created_at=record.created_at,
            steps=steps,
        )
