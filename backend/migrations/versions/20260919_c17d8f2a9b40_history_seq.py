"""edit_sessions 加撤销指针 history_seq（带数据回填的三段式）

Revision ID: c17d8f2a9b40
Revises: 43c2712f8543
Create Date: 2026-09-19

三段式：先带 server_default 落列（存量行有值）→ UPDATE 回填每会话
MAX(edit_history.seq)（无历史归 1）→ 去掉 default。撤销指针语义见
app/services/sessions.py：seq 分配从 history_seq+1 走，截断重做后与 max(seq) 分离。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c17d8f2a9b40"
down_revision: str | None = "43c2712f8543"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "edit_sessions",
        sa.Column("history_seq", sa.Integer(), nullable=False, server_default="1"),
    )
    op.execute(
        """
        UPDATE edit_sessions
        SET history_seq = history_max.max_seq
        FROM (
            SELECT session_id, MAX(seq) AS max_seq
            FROM edit_history
            GROUP BY session_id
        ) AS history_max
        WHERE edit_sessions.id = history_max.session_id
        """
    )
    op.alter_column("edit_sessions", "history_seq", server_default=None)


def downgrade() -> None:
    op.drop_column("edit_sessions", "history_seq")
