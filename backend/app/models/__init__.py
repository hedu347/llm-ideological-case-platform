"""集中导出业务模型，便于 Alembic 在导入时注册全部表。"""

from app.models.entities import (
    AiRecord,
    AskRecord,
    AuditLog,
    Case,
    Favorite,
    Profession,
    Tag,
    User,
)

__all__ = [
    "AiRecord",
    "AskRecord",
    "AuditLog",
    "Case",
    "Favorite",
    "Profession",
    "Tag",
    "User",
]
