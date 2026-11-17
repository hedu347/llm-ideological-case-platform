"""Pytest 公共配置与隔离测试夹具。"""

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.core.config import Settings
from app.db.base import Base
from app.factory import create_app


def pytest_addoption(parser: pytest.Parser) -> None:
    """注册需要开发者主动选择的本地集成测试开关。"""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="运行需要本地 PostgreSQL 等外部服务的集成测试",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """默认跳过依赖外部服务的测试，保持普通测试可离线重复执行。"""
    if config.getoption("--run-integration"):
        return

    skip_integration = pytest.mark.skip(
        reason="需要使用 --run-integration 显式启用本地集成测试"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture
def settings_values() -> dict[str, Any]:
    """返回完整的合成配置，不读取或复用根目录 .env 的真实值。"""
    return {
        "app_name": "test-backend",
        "app_env": "testing",
        "app_host": "127.0.0.1",
        "app_port": 8000,
        "app_debug": False,
        "api_v1_prefix": "/api/v1",
        "log_level": "CRITICAL",
        # 端口 1 不提供 PostgreSQL 服务，用于证明普通测试不会建立数据库连接。
        "database_url": (
            "postgresql+asyncpg://synthetic_user:synthetic_password"
            "@127.0.0.1:1/synthetic_database"
        ),
        "cors_origins": "http://testserver",
        "secret_key": "synthetic-secret-key-for-tests-only-1234567890",
        "access_token_expire_minutes": 60,
        "maxkb_base_url": None,
        "maxkb_api_key": None,
        "maxkb_timeout_seconds": 0.1,
        "maxkb_mock_enabled": True,
        "maxkb_qa_application_id": None,
        "maxkb_generation_application_id": None,
        "maxkb_evaluation_application_id": None,
    }


@pytest.fixture
def test_settings(settings_values: dict[str, Any]) -> Settings:
    """从合成字典直接创建测试配置，绕过 BaseSettings 环境变量来源。"""
    return Settings.model_validate(settings_values)


def _test_database_url() -> str:
    """返回集成测试使用的独立数据库地址。

    优先读取 ``TEST_DATABASE_URL``；否则从应用配置继承主机、端口和凭据，
    只把库名替换为 ``ideological_case_platform_test``，避免测试清空演示库。
    """
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    settings = Settings()
    base = str(settings.database_url)
    return base.rsplit("/", 1)[0] + "/ideological_case_platform_test"


@pytest_asyncio.fixture
async def app(
    request: pytest.FixtureRequest,
    settings_values: dict[str, Any],
) -> AsyncIterator[FastAPI]:
    """创建并完整进入、退出应用生命周期的测试应用。

    普通测试使用合成配置（不连接数据库）；带 ``--run-integration`` 时
    切换到独立测试库，使接口测试可以执行真实 SQL。
    """
    values = dict(settings_values)
    if request.config.getoption("--run-integration"):
        values["database_url"] = _test_database_url()
    test_settings = Settings.model_validate(values)
    test_app = create_app(test_settings)
    async with test_app.router.lifespan_context(test_app):
        yield test_app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """提供不打开真实网络端口的异步 ASGI 测试客户端。"""
    transport = httpx.ASGITransport(
        app=app,
        raise_app_exceptions=False,
    )
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def db_session(app: FastAPI) -> AsyncIterator[Any]:
    """为集成测试提供已建表的独立数据库会话。

    每次使用前重建全部业务表，保证测试之间互不污染；测试结束后由下一次
    使用或测试库整体删除清理。
    """
    database = app.state.database
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async with database.session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_db(db_session: Any) -> AsyncIterator[Any]:
    """在独立测试库中写入幂等种子数据后交给测试使用。"""
    from app.db.seed import seed

    await seed(db_session)
    await db_session.commit()
    yield db_session


@pytest.fixture
def auth() -> Any:
    """构造 Bearer 认证请求头的小工具。"""

    def _auth(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _auth
