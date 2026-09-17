"""ORM 模型包。

新增模型后需在此导出——Alembic autogenerate 依赖本包被导入来发现全部表。
"""

from app.models.user import User

__all__: list[str] = ["User"]
