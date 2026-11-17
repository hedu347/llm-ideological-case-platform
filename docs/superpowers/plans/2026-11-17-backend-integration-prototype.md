# 前后端打通原型 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有 Vue3 前端从 mock 切到真实 FastAPI + PostgreSQL 后端，形成可现场演示的完整前后端系统。

**Architecture:** 在 4B03 骨架之上新增业务层：`models`（8 张表）→ `services`（业务规则）→ `api/v1`（路由）；认证用 JWT + 每次请求查库校验；AI 走可切换适配层，默认内置确定性生成器。前端只改 `src/api/` 对接层与 `vite.config.js`，页面逻辑不动。

**Tech Stack:** Python 3.13、FastAPI、SQLAlchemy 2 async、asyncpg、Alembic、PostgreSQL 17、PyJWT、Pydantic 2；Vue 3 + Vite + Element Plus。

**Spec:** `docs/superpowers/specs/2026-11-17-backend-integration-prototype-design.md`

## Global Constraints

- 分支：`feature/backend-integration-demo`，每个任务独立提交。
- Python 版本：`>=3.13,<3.14`；本机用 `py -3.13`，Git Bash 下失败时用 `"C:/Users/22975/AppData/Local/Programs/Python/Python313/python.exe"`。
- 后端依赖版本与 `backend/pyproject.toml` 保持精确锁定风格；新增依赖写精确版本。
- 数据库：PostgreSQL 17，Docker Compose，本机 `127.0.0.1:5433`。
- 统一响应：业务成功与业务失败（HTTP 200）返回 `{code, message, data}`，`code=0` 成功；HTTP 非 2xx 沿用现有 `{error:{code,message}}` 结构（前端按 HTTP 状态处理）。
- 业务错误码：400 参数/业务校验、401 未认证、403 无权限、404 不存在、500 异常。登录失败用 HTTP 200 + `code=400`。
- 日期 `publish_date` / `collect_date` 用 `YYYYMMDD`；时间字段 `createTime` / `time` 用 `YYYY-MM-DD HH:mm`。
- 多值字段（profession/keywords/professional_knowledge/ideological_elements）用 JSON 数组。
- 所有代码注释、docstring 用简体中文，与现有代码风格一致。
- 前端 npm 安装带 `--registry=https://registry.npmmirror.com`。
- 前端接口返回形状以 `frontend/src/api/index.js` 现有 mock 为准（spec §5.2）。

## Review Focus

- **冻结账号的旧令牌**：账号被冻结后，已签发 token 再访问任何受保护接口应返回 403，而不是继续可用（文档 §2.5）。
- **教师越权**：教师读取/修改/删除他人案例应返回 403/404，不能仅靠前端隐藏入口。
- **非已发布案例可见性**：公开列表与详情只能看到「已发布」；草稿/待审核/需补充/驳回/已下线对学生不可见。
- **分页边界**：`page` 超出总页数返回空 `records` 而不是报错；`size > 100` 截断为 100；`size <= 0` 用默认 10。
- **SSE 中断**：LLM 不可用或生成异常时，必须发出 `error` 事件或降级到内置生成器，不能挂起或返回半截 JSON。

---

### Task 1: 响应工具与安全基础

**Files:**
- Create: `backend/app/core/response.py`
- Create: `backend/app/core/security.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/pyproject.toml`
- Modify: `.env.example`
- Test: `backend/tests/unit/test_security.py`

**Interfaces:**
- Produces:
  - `ok(data: Any, message: str = "success") -> dict[str, Any]`
  - `hash_password(password: str) -> str`
  - `verify_password(password: str, stored: str) -> bool`
  - `create_access_token(user_id: int, expires_minutes: int, secret_key: str) -> str`
  - `decode_access_token(token: str, secret_key: str) -> int | None`（返回 user_id，失败返回 None）
  - `Settings.llm_provider: Literal["builtin","openai","maxkb"]`、`llm_base_url`、`llm_api_key`、`llm_model`、`llm_timeout_seconds`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_security.py`

```python
from app.core.security import (
    create_access_token, decode_access_token, hash_password, verify_password,
)

def test_password_hash_roundtrip():
    stored = hash_password("123456")
    assert stored != "123456"
    assert verify_password("123456", stored) is True
    assert verify_password("wrong", stored) is False

def test_token_roundtrip_returns_user_id():
    token = create_access_token(7, 60, "secret-1234567890")
    assert decode_access_token(token, "secret-1234567890") == 7

def test_token_with_wrong_secret_is_rejected():
    token = create_access_token(7, 60, "secret-1234567890")
    assert decode_access_token(token, "other-secret") is None

def test_expired_token_is_rejected(monkeypatch):
    token = create_access_token(7, -1, "secret-1234567890")
    assert decode_access_token(token, "secret-1234567890") is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python -m pytest tests/unit/test_security.py -v`
Expected: FAIL，`ModuleNotFoundError: app.core.security`

- [ ] **Step 3: 实现**

- `response.py`：`ok()` 返回 `{"code": 0, "message": message, "data": data}`。
- `security.py`：`hash_password` 用 `hashlib.pbkdf2_hmac("sha256", pwd, salt, 120000)`，存储格式 `pbkdf2_sha256$120000$<salt_hex>$<hash_hex>`；`verify_password` 用 `hmac.compare_digest`。
- JWT 用 `jwt.encode({"sub": str(user_id), "exp": now+minutes}, secret, "HS256")`；`decode` 捕获 `jwt.PyJWTError` 与 `ExpiredSignatureError` 返回 None。
- `config.py` 增加 LLM 配置字段，默认 `llm_provider="builtin"`、`llm_timeout_seconds=30`。
- `pyproject.toml` 依赖增加 `pyjwt==2.10.1`。
- `.env.example` 增加 `LLM_PROVIDER=builtin`、`LLM_BASE_URL=`、`LLM_API_KEY=`、`LLM_MODEL=`、`LLM_TIMEOUT_SECONDS=30`；`CORS_ORIGINS` 追加 `http://localhost:5174`。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python -m pytest tests/unit/test_security.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/response.py backend/app/core/security.py backend/app/core/config.py backend/pyproject.toml .env.example backend/tests/unit/test_security.py
git commit -m "feat(backend): 增加统一响应、密码哈希与 JWT 基础"
```

---

### Task 2: 数据模型与迁移

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/entities.py`
- Create: `backend/alembic/versions/20261117_0002_create_business_tables.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/unit/test_models.py`

**Interfaces:**
- Produces SQLAlchemy 模型：`User`、`Case`、`Favorite`、`AiRecord`、`AskRecord`、`AuditLog`、`Tag`、`Profession`，表名分别为 `users/cases/favorites/ai_records/ask_records/audit_logs/tags/professions`。
- `Base.metadata.tables` 包含上述 8 张表。

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_models.py`

```python
from app.db.base import Base
from app.models import entities  # noqa: F401  导入以注册模型

def test_all_business_tables_registered():
    assert set(Base.metadata.tables) == {
        "users", "cases", "favorites", "ai_records",
        "ask_records", "audit_logs", "tags", "professions",
    }

def test_case_multi_value_columns_exist():
    columns = Base.metadata.tables["cases"].columns
    for name in ("profession", "keywords", "professional_knowledge", "ideological_elements"):
        assert name in columns
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python -m pytest tests/unit/test_models.py -v`
Expected: FAIL，表集合为空

- [ ] **Step 3: 实现模型与迁移**

字段按 spec §6。要点：

- `users.status`：`SmallInteger`，0 正常 / 1 冻结。
- `cases.case_no`：`String(16)` UNIQUE；`cases.id`：自增 PK；多值字段用 `JSONB`；`review_status` 用 `String(16)` 存中文；`author_id` FK `users.id`。
- `favorites` 联合唯一 `(user_id, case_id)`。
- `ai_records.evaluation/drafts/generated_data` 用 `JSONB`。
- 所有表带 `create_time`（`String(19)`，与前端 `YYYY-MM-DD HH:mm` 一致）或 `created_at` 语义字段，按 spec 采用 `create_time`。
- 在 `alembic/env.py` 的 `Base` 导入后加 `from app.models import entities  # noqa: F401`，让 metadata 非空。
- 迁移文件：手写 `op.create_table(...)` 8 张表与索引（`cases.review_status`、`cases.publish_date`、`favorites` 唯一约束）。`down_revision = "20260728_0001"`。

- [ ] **Step 4: 运行单元测试与迁移**

Run: `cd backend && .venv/Scripts/python -m pytest tests/unit/test_models.py -v`
Expected: 2 passed

Run: `cd backend && .venv/Scripts/python -m alembic upgrade head`
Expected: 输出迁移版本 `20261117_0002`，无报错

- [ ] **Step 5: 提交**

```bash
git add backend/app/models backend/alembic/env.py backend/alembic/versions/20261117_0002_create_business_tables.py backend/tests/unit/test_models.py
git commit -m "feat(backend): 创建业务数据模型与迁移"
```

---

### Task 3: 种子数据

**Files:**
- Create: `backend/app/db/seed.py`
- Test: `backend/tests/integration/test_seed.py`

**Interfaces:**
- Produces: `async def seed(session: AsyncSession) -> None`（幂等：按 `username` / `case_no` / 标签名判重）
- 可执行入口：`python -m app.db.seed`

- [ ] **Step 1: 写失败测试** `backend/tests/integration/test_seed.py`（标记 `@pytest.mark.integration`）

```python
async def test_seed_is_idempotent(db_session):
    await seed(db_session)
    await seed(db_session)
    users = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    cases = (await db_session.execute(select(func.count()).select_from(Case))).scalar_one()
    assert users == 8
    assert cases >= 12
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_seed.py -v --run-integration`
Expected: FAIL（`db_session` 或 `seed` 不存在）

- [ ] **Step 3: 实现种子数据**

数据来源：`frontend/src/api/mockData.js`。
- 8 个用户，密码统一 `123456`（用 `hash_password`），角色 student/teacher/admin。
- 12 条已发布案例（case_001…case_012，字段照搬 mock）。
- 4 条不同状态的提交案例（草稿/待审核/审核驳回/待审核）。
- 18 个思政标签、58 个专业。
- 2 条 AI 记录、2 条问答记录、5 条审计日志。
- 统计与首页数据不落种子表，由接口聚合计算。

在 `tests/conftest.py` 增加集成测试支持（关键，现有 `app` fixture 用的是端口 1 的假库）：

- `app` fixture 改造：读取 `--run-integration`；为真时用 `TEST_DATABASE_URL`（默认 `postgresql+asyncpg://postgres:...@localhost:5433/ideological_case_platform_test`）构造 `Settings`，为假时维持现有合成配置。
- `seeded_db` fixture：在集成模式下对 `Base.metadata` 执行 `create_all`，调用 `seed()`，测试结束 `drop_all`。它通过 `app.state.database.session_factory` 拿会话，保证和 `client` 用同一个库。
- `auth(token)` helper：返回 `{"Authorization": f"Bearer {token}"}`。
- `student_token` / `teacher_token` / `admin_token` fixture 放到 Task 4（依赖登录接口），登录对应 `student01` / `teacher01` / `admin01`。
- 所有 Task 4–10 的集成测试统一使用 `client` + `seeded_db` 组合，运行命令带 `--run-integration`。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_seed.py -v --run-integration`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/db/seed.py backend/tests/integration/test_seed.py backend/tests/conftest.py
git commit -m "feat(backend): 增加幂等种子数据与集成测试夹具"
```

---

### Task 4: 认证、用户与权限依赖

**Files:**
- Create: `backend/app/core/deps.py`
- Create: `backend/app/api/v1/auth.py`
- Create: `backend/app/api/v1/users.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/integration/test_auth.py`

**Interfaces:**
- Produces:
  - `get_current_user(request, session) -> User`（依赖，401 抛 `ApplicationError`）
  - `require_roles(*roles) -> Callable`（依赖工厂，403）
  - `get_optional_user(...) -> User | None`
- 路由：`POST /auth/login`、`POST /auth/logout`、`GET/PATCH /users/me`、`PUT /users/me/password`、`POST /users`、`PATCH /users/{id}`、`POST /users/{id}/reset-password`、`GET /audit-logs`、`GET /users`。

- [ ] **Step 1: 写失败测试** `backend/tests/integration/test_auth.py`

```python
async def test_login_ok_returns_token_and_user(client, seeded_db):
    r = await client.post("/api/v1/auth/login", json={"username": "teacher01", "password": "123456"})
    body = r.json()
    assert r.status_code == 200 and body["code"] == 0
    assert body["data"]["token"]
    assert body["data"]["role"] == "teacher"

async def test_login_wrong_password_is_business_error_with_http_200(client, seeded_db):
    r = await client.post("/api/v1/auth/login", json={"username": "teacher01", "password": "bad"})
    assert r.status_code == 200
    assert r.json()["code"] == 400

async def test_frozen_account_cannot_use_old_token(client, seeded_db):
    # 用 student01 登录拿 token，管理员冻结后，旧 token 访问 /users/me 应 403
    ...
    assert r.status_code == 403

async def test_teacher_cannot_access_admin_users(client, seeded_db):
    ...
    assert r.status_code == 403
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_auth.py -v --run-integration`
Expected: FAIL（404）

- [ ] **Step 3: 实现**

- `deps.py`：从 `Authorization: Bearer` 解析 token → `decode_access_token` → 查 `User`；`status == 1` 抛 403；角色不足抛 403；未登录抛 401。**每次请求查库**，使冻结与改角色即时生效。
- 登录：校验用户名、密码、角色；成功返回 `{token, expires_in, username, role, avatar, user:{...}}`；失败 HTTP 200 + `code=400`；冻结 HTTP 403 + `code=2002`。
- 用户 CRUD 按 spec 字段形状（`nickName`、`status` 0/1、`createTime`）。
- 关键操作写 `audit_logs`。
- `router.py` 注册 `auth_router`、`users_router`。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_auth.py -v --run-integration`
Expected: passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/deps.py backend/app/api/v1/auth.py backend/app/api/v1/users.py backend/app/api/v1/router.py backend/tests/integration/test_auth.py
git commit -m "feat(backend): 实现认证、用户管理与权限依赖"
```

---

### Task 5: 案例检索、详情与收藏

**Files:**
- Create: `backend/app/services/cases.py`
- Create: `backend/app/api/v1/cases.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/integration/test_cases_public.py`

**Interfaces:**
- Produces:
  - `list_cases(session, *, keyword, category, profession, tag, page, size, sort, include_all, status, user_id) -> dict`
  - `case_to_public(case: Case, is_favorite: bool) -> dict`（`id` = `case_no`）
  - `paginate(records, total, page, size) -> dict`
- 路由：`GET /cases`、`GET /cases/{id}`、`POST/DELETE /cases/{id}/favorite`、`GET /users/me/favorites`。

- [ ] **Step 1: 写失败测试** `backend/tests/integration/test_cases_public.py`

```python
async def test_public_list_only_returns_published(client, seeded_db):
    r = await client.get("/api/v1/cases")
    records = r.json()["data"]["records"]
    assert records and all(x["review_status"] == "已发布" for x in records)

async def test_keyword_and_tag_filter(client, seeded_db):
    r = await client.get("/api/v1/cases", params={"keyword": "钱学森"})
    assert any("钱学森" in x["title"] for x in r.json()["data"]["records"])

async def test_detail_of_draft_is_not_visible_to_student(client, seeded_db):
    r = await client.get("/api/v1/cases/case_draft_001")
    assert r.status_code == 404

async def test_pagination_bounds(client, seeded_db):
    r = await client.get("/api/v1/cases", params={"page": 999, "size": 999})
    assert r.json()["data"]["records"] == []
    assert r.json()["data"]["size"] == 100

async def test_favorite_is_idempotent(client, seeded_db, student_token):
    await client.post("/api/v1/cases/case_001/favorite", headers=auth(student_token))
    await client.post("/api/v1/cases/case_001/favorite", headers=auth(student_token))
    ...
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_cases_public.py -v --run-integration`
Expected: FAIL（404）

- [ ] **Step 3: 实现**

- `sort`：`new` 按 `publish_date desc`，`views` 按 `views desc`；也接受 `publish_date,desc` 形式。
- `keyword` 匹配 title/keywords/teaching_value/content（与前端 mock 一致）。
- `size` 上限 100、下限 1；`page` 至少 1。
- 详情只返回已发布；`id` 先按 `case_no` 查，再按整数查。
- 收藏幂等：已存在则不重复插入。
- 返回对象的 `id` 用 `case_no`，并带 `isFavorite`。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_cases_public.py -v --run-integration`
Expected: passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/cases.py backend/app/api/v1/cases.py backend/app/api/v1/router.py backend/tests/integration/test_cases_public.py
git commit -m "feat(backend): 实现案例检索、详情与收藏"
```

---

### Task 6: 教师工作区

**Files:**
- Create: `backend/app/api/v1/teacher_cases.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/integration/test_teacher_cases.py`

**Interfaces:**
- 路由：`POST /cases`、`PATCH /cases/{id}`、`DELETE /cases/{id}`、`POST /cases/{id}/submit`、`POST /cases/parse`、`GET /users/me/cases`、`GET /cases/{id}/review`。
- 返回「我的案例」记录 `id` 用**整数主键**（兼容前端历史逻辑），同时带 `case_no`。

- [ ] **Step 1: 写失败测试**

```python
async def test_teacher_creates_draft_and_submits(client, seeded_db, teacher_token):
    r = await client.post("/api/v1/cases", json={"title": "新案例", "category": "行业案例"}, headers=auth(teacher_token))
    assert r.json()["data"]["status"] == "草稿"
    cid = r.json()["data"]["id"]
    s = await client.post(f"/api/v1/cases/{cid}/submit", headers=auth(teacher_token))
    assert s.json()["data"]["status"] == "待审核"

async def test_teacher_cannot_edit_other_teacher_case(client, seeded_db, teacher_token):
    r = await client.patch("/api/v1/cases/201", json={"title": "改"}, headers=auth(teacher_token))
    assert r.status_code in (403, 404)

async def test_only_draft_can_be_deleted(client, seeded_db, teacher_token):
    r = await client.delete("/api/v1/cases/201", headers=auth(teacher_token))
    assert r.json()["code"] == 400

async def test_submit_requires_title_and_category(client, seeded_db, teacher_token):
    r = await client.post("/api/v1/cases/999/submit", json={}, headers=auth(teacher_token))
    assert r.json()["code"] in (400, 404)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_teacher_cases.py -v --run-integration`
Expected: FAIL（404）

- [ ] **Step 3: 实现**

- 创建草稿时分配 `case_no`（`case_%03d`，取当前最大编号 +1），写 `author_id`。
- 更新/删除/提交校验 `author_id == current_user.id`，否则 403。
- 删除仅 `review_status == "草稿"`，否则 HTTP 200 + `code=400`。
- 提交校验必填字段（title、category），转 `待审核`。
- `/cases/parse`：`multipart/form-data`，txt 直读、docx 用 `python-docx` 提取（若未装则提示仅支持 txt）；返回 `{title, background, process, result}` 候选字段。
- `/cases/{id}/review` 返回 `{status, opinion, reviewer, time}`。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_teacher_cases.py -v --run-integration`
Expected: passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/v1/teacher_cases.py backend/app/api/v1/router.py backend/tests/integration/test_teacher_cases.py
git commit -m "feat(backend): 实现教师案例生产与提交审核"
```

---

### Task 7: 管理后台

**Files:**
- Create: `backend/app/api/v1/admin.py`
- Create: `backend/app/services/stats.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/integration/test_admin.py`

**Interfaces:**
- 路由：`GET /admin/reviews`、`POST /admin/cases/{id}/review`、`GET /admin/cases`、`PATCH /admin/cases/{id}`、`DELETE /admin/cases/{id}`、`POST /admin/cases/{id}/offline`、`POST /admin/cases/import`、`GET /admin/cases/export`、`GET/POST /admin/tags`、`PATCH/DELETE /admin/tags/{id}`、`GET/POST /admin/professions`、`PATCH /admin/professions/{id}`、`GET /admin/statistics/home`。

- [ ] **Step 1: 写失败测试**

```python
async def test_approve_moves_case_to_published_and_public_list(client, seeded_db, admin_token):
    r = await client.post("/api/v1/admin/cases/201/review", json={"status": "已发布", "opinion": ""}, headers=auth(admin_token))
    assert r.json()["code"] == 0
    pub = await client.get("/api/v1/cases", params={"keyword": "区块链"})
    assert pub.json()["data"]["total"] >= 1

async def test_reject_records_opinion_visible_to_author(client, seeded_db, admin_token, teacher_token):
    await client.post("/api/v1/admin/cases/201/review", json={"status": "审核驳回", "opinion": "内容不足"}, headers=auth(admin_token))
    r = await client.get("/api/v1/cases/201/review", headers=auth(teacher_token))
    assert r.json()["data"]["opinion"] == "内容不足"

async def test_offline_only_published(client, seeded_db, admin_token):
    r = await client.post("/api/v1/admin/cases/case_001/offline", json={"reason": "链接失效"}, headers=auth(admin_token))
    assert r.json()["data"]["review_status"] == "已下线"

async def test_student_blocked_from_admin(client, seeded_db, student_token):
    r = await client.get("/api/v1/admin/reviews", headers=auth(student_token))
    assert r.status_code == 403
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_admin.py -v --run-integration`
Expected: FAIL（404）

- [ ] **Step 3: 实现**

- 审核：同一行改 `review_status`；通过 → `已发布`，驳回/需补充 → 记录 `reject_reason`、`reviewer_id`、`review_time`；写审计日志。
- 下线：仅 `已发布` 可下线，记录 `offline_reason`。
- 导入：接收 JSON 行数组，逐行校验 title/category，返回 `{success, fail}`。
- 导出：返回 `text/csv`，UTF-8 BOM。
- 标签/专业：`{id, name, useCount/caseCount, status, createTime}`。
- 统计：按真实表聚合，字段同 `mockStats`：`totalCases`、`collectedCaseCount`、`totalUsers`、`todayAiCount`、`pendingReviewCount`、`categoryDistribution`、`sourceDistribution`。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_admin.py -v --run-integration`
Expected: passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/v1/admin.py backend/app/services/stats.py backend/app/api/v1/router.py backend/tests/integration/test_admin.py
git commit -m "feat(backend): 实现管理后台审核、字典与统计"
```

---

### Task 8: 首页数据

**Files:**
- Create: `backend/app/api/v1/home.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/integration/test_home.py`

**Interfaces:**
- `GET /home/index-data` 返回 `{totalCases, collectedCaseCount, totalProfessions, totalTags, totalAiGenerated}`。

- [ ] **Step 1: 写失败测试**

```python
async def test_home_index_returns_all_fields(client, seeded_db):
    r = await client.get("/api/v1/home/index-data")
    data = r.json()["data"]
    assert set(data) == {"totalCases", "collectedCaseCount", "totalProfessions", "totalTags", "totalAiGenerated"}
    assert data["totalCases"] >= 12
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_home.py -v --run-integration`
Expected: FAIL（404）

- [ ] **Step 3: 实现**：聚合已发布案例、专业、标签、AI 记录数量。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_home.py -v --run-integration`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/v1/home.py backend/app/api/v1/router.py backend/tests/integration/test_home.py
git commit -m "feat(backend): 实现首页平台数据"
```

---

### Task 9: AI 适配层与流式接口

**Files:**
- Create: `backend/app/integrations/llm/__init__.py`
- Create: `backend/app/integrations/llm/base.py`
- Create: `backend/app/integrations/llm/builtin.py`
- Create: `backend/app/integrations/llm/factory.py`
- Create: `backend/app/services/ai.py`
- Create: `backend/app/api/v1/ai.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/unit/test_llm_builtin.py`
- Test: `backend/tests/integration/test_ai.py`

**Interfaces:**
- Produces:
  - `LLMProvider.generate(ideological: str, knowledge: str, profession: list[str]) -> list[Draft]`
  - `LLMProvider.ask(case_context: dict, question: str) -> str`
  - `builtin.generate(...)` 返回 3 个候选稿，每稿含 `case`、`evaluation`
  - `ai_service.stream_generate(params) -> AsyncIterator[tuple[str, dict]]`，逐项产出 `(事件名, data)`，异常时产出 `error`
- SSE 事件：`progress`、`content`、`references`、`evaluation`、`done`、`error`。

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_llm_builtin.py`

```python
def test_builtin_generates_three_scored_drafts():
    drafts = builtin.generate("科技报国", "系统工程", ["航空航天工程"])
    assert len(drafts) == 3
    assert all(d.case["title"] and d.case["background"] for d in drafts)
    assert all(0 <= d.evaluation["totalScore"] <= 100 for d in drafts)

def test_builtin_ask_includes_case_context():
    answer = builtin.ask({"title": "案例A", "background": "背景"}, "这案例的思政点？")
    assert "案例A" in answer

@pytest.mark.asyncio
async def test_stream_generate_emits_error_event_when_provider_fails(monkeypatch):
    from app.services import ai as ai_service
    def boom(*args, **kwargs):
        raise RuntimeError("model down")
    monkeypatch.setattr(builtin, "generate", boom)
    events = [name async for name, _ in ai_service.stream_generate(
        {"ideological": "科技报国", "knowledge": "系统工程", "profession": []}
    )]
    assert "error" in events
```
（`backend/tests/unit/test_llm_builtin.py` 顶部加 `import pytest` 与 `pytestmark = pytest.mark.asyncio`，或只给该测试加装饰器。）
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python -m pytest tests/unit/test_llm_builtin.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

- 把前端 `buildGeneratedCase` / `evaluateDraft` 的确定性逻辑用 Python 重写（3 稿、4 个评分维度、择优）。
- `factory.get_provider(settings)` 按 `llm_provider` 返回；`openai` 实现失败时降级 builtin。
- `ai.py`：
  - `POST /ai/generate`：用 `StreamingResponse`，`media_type="text/event-stream"`；先发 progress，再逐块发 content（每块 2–4 字符），结束发 references/evaluation/done；落 `ai_records`。
  - `POST /ai/ask/{caseId}`：路径 `draft` 时用 body 的 `caseContext`；否则按 `case_no` 查案例。
  - `GET /ai/records`、`GET/DELETE /ai/records/{id}`、`GET /users/me/ask-records`。
- 发生异常时发 `event: error`，不停在半截。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python -m pytest tests/unit/test_llm_builtin.py -v`
Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_ai.py -v --run-integration`
Expected: passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/integrations/llm backend/app/services/ai.py backend/app/api/v1/ai.py backend/app/api/v1/router.py backend/tests/unit/test_llm_builtin.py backend/tests/integration/test_ai.py
git commit -m "feat(backend): 实现 AI 生成、问答与流式协议"
```

---

### Task 10: 路由汇总与全量接口自检

**Files:**
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/integration/test_routes_contract.py`

**Interfaces:**
- `/api/v1` 下应存在 spec §7 列出的全部路径。

- [ ] **Step 1: 写失败测试**

```python
EXPECTED = {
    ("POST", "/api/v1/auth/login"), ("POST", "/api/v1/auth/logout"),
    ("GET", "/api/v1/users/me"), ("PATCH", "/api/v1/users/me"),
    ("PUT", "/api/v1/users/me/password"), ("POST", "/api/v1/users"),
    ("PATCH", "/api/v1/users/{id}"), ("POST", "/api/v1/users/{id}/reset-password"),
    ("GET", "/api/v1/audit-logs"), ("GET", "/api/v1/users"),
    ("GET", "/api/v1/cases"), ("GET", "/api/v1/cases/{id}"),
    ("POST", "/api/v1/cases/{id}/favorite"), ("DELETE", "/api/v1/cases/{id}/favorite"),
    ("GET", "/api/v1/users/me/favorites"), ("POST", "/api/v1/cases"),
    ("PATCH", "/api/v1/cases/{id}"), ("DELETE", "/api/v1/cases/{id}"),
    ("POST", "/api/v1/cases/{id}/submit"), ("POST", "/api/v1/cases/parse"),
    ("GET", "/api/v1/users/me/cases"), ("GET", "/api/v1/cases/{id}/review"),
    ("POST", "/api/v1/ai/generate"), ("GET", "/api/v1/ai/records"),
    ("GET", "/api/v1/ai/records/{id}"), ("DELETE", "/api/v1/ai/records/{id}"),
    ("POST", "/api/v1/ai/ask/{caseId}"), ("GET", "/api/v1/users/me/ask-records"),
    ("GET", "/api/v1/admin/reviews"), ("POST", "/api/v1/admin/cases/{id}/review"),
    ("GET", "/api/v1/admin/cases"), ("PATCH", "/api/v1/admin/cases/{id}"),
    ("DELETE", "/api/v1/admin/cases/{id}"),
    ("POST", "/api/v1/admin/cases/{id}/offline"), ("POST", "/api/v1/admin/cases/import"),
    ("GET", "/api/v1/admin/cases/export"), ("GET", "/api/v1/admin/tags"),
    ("POST", "/api/v1/admin/tags"), ("PATCH", "/api/v1/admin/tags/{id}"),
    ("DELETE", "/api/v1/admin/tags/{id}"),
    ("GET", "/api/v1/admin/professions"), ("POST", "/api/v1/admin/professions"),
    ("PATCH", "/api/v1/admin/professions/{id}"), ("GET", "/api/v1/admin/statistics/home"),
    ("GET", "/api/v1/home/index-data"),
}

async def test_openapi_contains_all_contract_paths(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    missing = [(m, p) for m, p in EXPECTED if p not in paths or m.lower() not in paths[p]]
    assert not missing, missing
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_routes_contract.py -v --run-integration`
Expected: FAIL，列出缺失路径

- [ ] **Step 3: 补齐 `router.py` 注册并修复缺失**

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/Scripts/python -m pytest tests/integration/test_routes_contract.py -v --run-integration`
Expected: passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/v1/router.py backend/tests/integration/test_routes_contract.py
git commit -m "test(backend): 校验 §6 接口契约完整覆盖"
```

---

### Task 11: 前端对接层

**Files:**
- Create: `frontend/src/api/constants.js`
- Create: `frontend/src/api/utils.js`
- Create: `frontend/src/api/sse.js`
- Create: `frontend/scripts/api-smoke.mjs`
- Modify: `frontend/src/api/index.js`（整体重写为真实请求，保留 mock 分支）
- Modify: `frontend/vite.config.js`
- Modify: `frontend/src/views/CaseList.vue`、`AIGenerate.vue`、`MyCases.vue`、`admin/Review.vue`、`components/ManualUploadForm.vue`（仅改常量 import 来源）

**Interfaces:**
- 保持 `src/api/index.js` 全部现有导出名与参数签名不变。
- 新增 `VITE_USE_MOCK` 开关：`'true'` 时 `import('./mock/index.js')`，否则真实请求。
- SSE：`streamSSE(url, body, { onEvent, onChunk }) -> Promise<{data, evaluation, references, drafts}>`。

- [ ] **Step 1: 写可执行的冒烟检查**

`normalizePage` 是纯函数，放在 `frontend/src/api/utils.js`（不依赖 Vue/Vite），由 `index.js` 复用。新增 `frontend/scripts/api-smoke.mjs`：

```js
import { normalizePage } from '../src/api/utils.js'
console.assert(normalizePage(undefined).size === 10, 'default size')
console.assert(normalizePage({ size: 999 }).size === 100, 'size cap')
console.assert(normalizePage({ page: 0 }).page === 1, 'page floor')
console.log('api smoke ok')
```

Run: `cd frontend && node scripts/api-smoke.mjs`
Expected: 无输出、退出码 0

- [ ] **Step 2: 确认当前失败**

Run: `cd frontend && node scripts/api-smoke.mjs`
Expected: `Cannot find module .../src/api/utils.js`

- [ ] **Step 3: 实现对接层**

- `constants.js`：迁移 `CASE_CATEGORIES`、`REVIEW_STATUSES`、`IDEOLOGICAL_TAGS`、`PROFESSIONS`、`SOURCE_TYPES`。
- `index.js`：每个函数体改为 `get/post/put/del` 或 `streamSSE`；保留返回形状；`normalizePage` 做分页边界；`submitCaseApi` 无 id 时先建后提交；`chatAskApi` 无 id 时用 `draft` + `caseContext`。
  - 登录失败（HTTP 200 + code 400）直接返回，不抛异常。
  - 新增 `frontend/src/api/mock/index.js`：把现有 mock 实现整体移入，供回退。
- `sse.js`：`fetch` + `ReadableStream` 解析 `event:` / `data:`，按事件名回调；手动带 `Authorization`；非 2xx 抛错。
- `vite.config.js`：开启代理 `/api` → `http://127.0.0.1:8000`，`changeOrigin: true`。
- 5 个 views/components 的常量 import 从 `@/api/mockData` 改为 `@/api/constants`。

- [ ] **Step 4: 运行构建与冒烟**

Run: `cd frontend && node scripts/api-smoke.mjs`
Expected: 退出码 0

Run: `cd frontend && npm run build`
Expected: 构建成功，无未解析导入

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api frontend/vite.config.js frontend/src/views frontend/src/components
git commit -m "feat(frontend): API 层切换到真实后端并保留 mock 回退"
```

---

### Task 12: 一键启动、联调冒烟与收尾

**Files:**
- Create: `scripts/dev.ps1`
- Create: `scripts/README.md`
- Modify: `README.md`（演示步骤）
- Test: 手工冒烟清单

**Interfaces:**
- `scripts/dev.ps1` 依次：检查 `.env` → 起 postgres → 等健康 → venv 就绪 → `alembic upgrade head` → seed → 启动 uvicorn；另起窗口提示前端命令。

- [ ] **Step 1: 写启动脚本与文档**

脚本要点：
- 探测 Python 3.13（`py -3.13` 失败时用绝对路径）。
- 检测 5433 端口占用。
- 幂等：重复执行不重复种子。

- [ ] **Step 2: 端到端冒烟（逐条勾选）**

- [ ] `docker compose --env-file .env -f infra/compose.yaml up -d postgres` 后 `alembic upgrade head` 成功
- [ ] `python -m app.db.seed` 输出创建数量
- [ ] `uvicorn app.main:app --port 8000` 启动
- [ ] 前端 `npm run dev` 后三个账号都能登录
- [ ] 学生：检索、详情、收藏、问答流式出字
- [ ] 教师：AI 生成 3 稿、保存草稿、提交审核
- [ ] 管理员：审核通过后学生能搜到；驳回后教师看到意见；下线；用户管理；标签；统计
- [ ] 断网 + 不配 LLM key，AI 仍可用
- [ ] `VITE_USE_MOCK=true` 可回退

- [ ] **Step 3: 运行后端全量测试**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Run: `cd backend && .venv/Scripts/python -m pytest -q --run-integration`
Expected: 全部通过（integration 需 postgres 运行）

- [ ] **Step 4: 提交**

```bash
git add scripts README.md
git commit -m "chore: 增加一键启动脚本与演示说明"
```

---

## 执行顺序说明

Task 1–3 是基础设施，必须按序；Task 4–9 依赖模型与权限依赖，建议按序；Task 10 是契约收口；Task 11 依赖后端全部路由就绪（至少 Task 4–9），可最后做；Task 12 收尾。

每个任务完成后运行 `git status` 确认只包含该任务文件，再进入下一任务。
