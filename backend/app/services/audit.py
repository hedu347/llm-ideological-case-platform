"""管理员关键操作留痕。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import now_text
from app.models import AuditLog, User


def add_audit(
    session: AsyncSession,
    operator: User,
    action: str,
    target: str,
    detail: str,
) -> None:
    """把操作写入审计日志，随当前事务一起提交。"""
    session.add(
        AuditLog(
            operator=operator.nick_name or operator.username,
            username=operator.username,
            action=action,
            target=target,
            detail=detail,
            time=now_text(),
        )
    )
