"""业务模型注册的单元测试。

这些测试只检查 SQLAlchemy metadata，不建立数据库连接，因此可以在
没有 PostgreSQL 的情况下快速运行。
"""

from app.db.base import Base
from app.models import entities  # noqa: F401  导入以注册模型


def test_all_business_tables_registered() -> None:
    """八张业务表必须全部注册到统一 metadata。"""
    assert set(Base.metadata.tables) == {
        "users",
        "cases",
        "favorites",
        "ai_records",
        "ask_records",
        "audit_logs",
        "tags",
        "professions",
    }


def test_case_multi_value_columns_exist() -> None:
    """案例表必须包含四个多值字段，供前端以数组消费。"""
    columns = Base.metadata.tables["cases"].columns
    for name in (
        "profession",
        "keywords",
        "professional_knowledge",
        "ideological_elements",
    ):
        assert name in columns
