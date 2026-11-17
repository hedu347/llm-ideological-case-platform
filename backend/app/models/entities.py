"""业务数据模型。

时间字段统一存为 ``YYYY-MM-DD HH:mm`` 字符串，日期字段存 ``YYYYMMDD``，
与前端现有消费的形状保持一致。多值字段使用 PostgreSQL 的 JSONB，存储
字符串数组或对象。
"""

from sqlalchemy import (
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """平台账号。状态 0 为正常，1 为冻结。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="student")
    nick_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    avatar: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    intro: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    create_time: Mapped[str] = mapped_column(String(19), nullable=False, default="")


class Case(Base):
    """案例主表，承载草稿、审核与已发布等全部状态。"""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_no: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    source_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    publish_date: Mapped[str] = mapped_column(String(8), nullable=False, default="", index=True)
    collect_date: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="V1.1")
    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="草稿", index=True
    )
    background: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    process: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    profession: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    professional_knowledge: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    ideological_elements: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    teaching_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    submitter_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    submit_time: Mapped[str] = mapped_column(String(19), nullable=False, default="")
    update_time: Mapped[str] = mapped_column(String(19), nullable=False, default="")
    reject_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    offline_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    review_time: Mapped[str] = mapped_column(String(19), nullable=False, default="")
    create_time: Mapped[str] = mapped_column(String(19), nullable=False, default="")


class Favorite(Base):
    """用户收藏关系，同一用户对同一案例只保留一条。"""

    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "case_id", name="uq_favorites_user_id_case_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    create_time: Mapped[str] = mapped_column(String(19), nullable=False, default="")


class AiRecord(Base):
    """AI 生成记录，含辅助评价与候选稿得分。"""

    __tablename__ = "ai_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    topic: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    ideological_direction: Mapped[str] = mapped_column(
        String(64), nullable=False, default=""
    )
    profession: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    content_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    publish_date: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="V1.0")
    evaluation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    draft_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    drafts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    generated_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    create_time: Mapped[str] = mapped_column(String(19), nullable=False, default="")


class AskRecord(Base):
    """用户针对案例的智能问答记录。"""

    __tablename__ = "ask_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    case_no: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    case_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    create_time: Mapped[str] = mapped_column(String(19), nullable=False, default="")


class AuditLog(Base):
    """管理员关键操作留痕。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operator: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    time: Mapped[str] = mapped_column(String(19), nullable=False, default="")


class Tag(Base):
    """思政标签字典。状态 1 为启用，0 为停用。"""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    create_time: Mapped[str] = mapped_column(String(19), nullable=False, default="")


class Profession(Base):
    """专业字典。状态 1 为启用，0 为停用。"""

    __tablename__ = "professions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    create_time: Mapped[str] = mapped_column(String(19), nullable=False, default="")
