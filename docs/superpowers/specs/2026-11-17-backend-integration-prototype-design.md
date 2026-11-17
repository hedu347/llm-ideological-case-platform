# 前后端打通的原型系统 — 设计文档

- 日期：2026-11-17
- 状态：待批准
- 分支：`feature/backend-integration-demo`
- 依据：《需求规格文档 V1.0》§3–§6、《详细设计文档 V1.0》§3 接口契约、现有前端实现

## 1. 意图与动机

老师催得紧，需要向老师展示一个**前后端真正打通、可现场演示**的完整系统。目前只有前端，且全部数据来自 `src/api/index.js` 的 mock；后端只有 FastAPI 骨架（健康检查、配置、数据库会话、MaxKB 适配器），业务表与业务接口为零。

本设计要把这半套系统补成能跑通"登录 → 检索浏览 → AI 生成 → 保存草稿 → 提交审核 → 管理员审核 → 发布上线 → 学生可检索"完整业务闭环的演示系统。

**这不是最终版本。** 详细设计文档目前仍有"暂时空缺"章节（§1、§2、§3.4/§3.7），本工程的定位是演示原型，接口形状以现有前端为准、以文档为辅；正式实现时以补齐后的详细设计为准。

## 2. 目标 / 非目标 / 反目标

### 目标

1. 三个角色（学生 / 教师 / 管理员）都能用真实账号登录，菜单与权限按角色生效。
2. 需求文档 §6 的 40 个接口全部由后端实现，前端不再返回 mock 数据。
3. 主业务闭环可演示：教师 AI 生成 → 存草稿 → 提交审核 → 管理员通过 → 案例出现在案例库 → 学生可检索、收藏、问答。
4. **演示不依赖外网**：AI 生成与问答在后端内置确定性生成器下也能完整工作（SSE 流式效果不变）。
5. 一键启动：数据库、迁移、种子数据、后端、前端各自一条命令，README 写清演示步骤。

### 非目标

- 不做生产部署、HTTPS、反向代理、多实例。
- 不做真实 PDF / docx 解析：`POST /cases/parse` 只做文本抽取（txt 直读，docx 提取正文，pdf 提示不支持）。
- 不做案例版本历史表：`version` 字段保留，但不存历史快照。
- 不做真实内容安全引擎：敏感词 / 价值观检测用简单规则占位，返回通过。
- 不做 MaxKB 真实联调（保留适配器与配置，默认不启用）。
- 不做前端单元测试；后端只做接口冒烟测试。

### 反目标

- **演示时不能因为没网、没 API key 而失败。**
- **不能重写前端页面逻辑**：只允许改 `src/api/`、`src/stores/` 的对接层、`vite.config.js` 和少量字段名审计。
- **不能把演示数据写死在前端**：页面看到的数据必须来自 PostgreSQL。

## 3. 约束

- 本机环境已确认：Python 3.13（`py -3.13`）、Docker 29 + Compose v5、Node 24 / npm 11。
- 后端要求 Python `>=3.13,<3.14`，而 `python` 默认是 3.14，**必须显式使用 3.13 建 venv**。
- 数据库为 PostgreSQL 17（`infra/compose.yaml`，映射到本机 `127.0.0.1:5433`）。
- 前后端联调用 Vite 代理，开发期同源，不依赖 CORS 放行。
- npm 安装使用国内镜像 `--registry=https://registry.npmmirror.com`；pip 使用清华镜像。
- 现有前端开发端口 `5174`，后端端口以 `.env` 中 `APP_PORT` 为准（默认 8000）。

## 4. 方案（已选定）

| 方案 | 说明 | 取舍 |
|---|---|---|
| A 全栈真实版 | 全部接口接真实 LLM | 演示依赖 key 与网络，风险高 |
| **B 全栈打通 + AI 可切换（选定）** | 真实数据库与真实接口；AI 默认内置生成器，可配置真实模型 | 真实性经得起检查，演示稳定 |
| C 轻量打通 | SQLite、只做主线 | 前后端不彻底，老师抽查容易露馅 |

选择 B 的核心权衡：**"前后端真打通"靠数据库和 HTTP 保证，"AI 效果"靠可切换适配器保证。** 两者解耦，任一环节出问题都不会让整场演示失败。

## 5. 总体架构

```
┌──────────────┐   HTTP / SSE    ┌─────────────────────┐   asyncpg   ┌──────────────┐
│ Vue3 + Vite  │ ──────────────► │ FastAPI (app/api)   │ ──────────► │ PostgreSQL 17│
│ :5174        │ ◄────────────── │  JWT + 权限 + 业务   │             │ :5433        │
└──────────────┘                 └─────────┬───────────┘             └──────────────┘
       │ vite proxy /api                     │
       │                                     ▼
       │                          ┌─────────────────────┐
       │                          │ integrations/llm    │
       │                          │ builtin | openai |  │
       │                          │ maxkb               │
       │                          └─────────────────────┘
```

### 5.1 响应形状：以现有前端为准

前端 40 个 API 函数与页面已经彼此适配。**后端按 `frontend/src/api/index.js` 中 mock 的返回形状实现**，前端只需把函数体换成真实请求，页面不感知。与文档字段名的差异在下面统一列明，不与文档逐字对齐。

统一响应体（文档 §3.1.2）：`{ "code": 0, "message": "ok", "data": ... }`；分页 `data = {records, total, page, size}`。

### 5.2 字段命名差异表（以此为准）

| 语义 | 文档写法 | 本项目采用（前端形状） |
|---|---|---|
| 昵称 | `nickname` | `nickName` |
| 账号状态 | `active` / `frozen` | `0`（正常）/ `1`（冻结） |
| 创建时间 | `created_at`（ISO8601） | `createTime`（`YYYY-MM-DD HH:mm`） |
| 案例发布日期 | `publish_date`（YYYYMMDD） | 同左 |
| 案例状态 | 中文六态 | 同左 |

**登录响应**兼容两端：`{ token, expires_in, username, role, avatar, user: {id, username, nickName, role, status} }`。前端取 `token/username/role/avatar`，文档要求者取 `user/expires_in`。

### 5.3 案例标识

- 数据库：`cases.id` 为自增整数主键（内部用），`cases.case_no` 为对外编号 `case_001`。
- 对前端：
  - 案例库 / 详情 / 收藏 / 问答相关接口，`id` 一律返回 `case_no`（字符串），因为前端 `CaseList`、`CaseDetailDialog` 用列表项的 `id` 直接调详情。
  - 教师工作区（我的案例）与审核队列接口，`id` 返回整数主键，因为前端历史代码用数字 `caseSubmitId` 做提交/审核。
  - 路径参数两种都接受：`/cases/{id}` 先按 `case_no` 查，再按整数查。

### 5.4 认证与权限

- 登录签发 JWT（HS256，`secret_key` 来自 `.env`，有效期 `access_token_expire_minutes`）。
- JWT payload 只放 `sub=user.id`，**不放角色**；每次请求从数据库读用户，角色调整、账号冻结即时生效（文档 §2.5 要求既有令牌失效）。
- 密码使用标准库 `hashlib.pbkdf2_hmac` 加盐哈希，不引入额外依赖。
- 权限按文档 §2.4 矩阵实现；越权规则按文档 §6.1.6：教师只能操作本人案例，后端校验，不依赖前端隐藏。

### 5.5 错误码与 HTTP 状态策略

前端 `request.js` 的拦截器按 **HTTP 状态** 判断 401/403/500，按 **业务码** 判断其他错误。因此：

| 情况 | HTTP | 业务 code | 说明 |
|---|---|---|---|
| 成功 | 200 | 0 | |
| 参数/业务校验失败（含登录账号密码错误） | **200** | 400/1001 | 前端 `loginApi` 会弹 `message`，不跳登录页 |
| 未登录或令牌失效 | **401** | 2000 | axios 走 error 分支，自动清 token 跳登录 |
| 角色/归属不足 | **403** | 2001 | axios 走 error 分支，弹无权限 |
| 资源不存在 | **404** | 3000 | |
| 账号冻结 | **403** | 2002 | 登录时返回 |
| 服务器异常 | **500** | 7000 | |

这条策略优先于文档 §3.1.3：**前端能否正确处理高于与文档逐字一致**。登录失败刻意用 HTTP 200 + code 400，避免触发全局 401 跳转。

## 6. 数据模型（8 张表）

| 表 | 关键字段 | 说明 |
|---|---|---|
| `users` | `id` PK、`username` UNIQUE、`password_hash`、`role`（student/teacher/admin）、`nick_name`、`avatar`、`phone`、`intro`、`status`（0/1）、`create_time` | 账号由管理员创建 |
| `cases` | `id` PK、`case_no` UNIQUE、`title`、`category`、`source`、`source_url`、`source_type`、`publish_date`、`collect_date`、`version`、`review_status`、`background`、`content`、`process`、`result`、`profession` JSONB、`keywords` JSONB、`professional_knowledge` JSONB、`ideological_elements` JSONB、`teaching_value`、`views`、`author_id` FK、`submitter_name`、`submit_time`、`update_time`、`reject_reason`、`offline_reason`、`reviewer_id`、`review_time` | 一张表承载六种状态，审核通过即改状态，不复制 |
| `favorites` | `user_id` FK、`case_id` FK、`create_time` | 联合唯一 |
| `ai_records` | `id` PK、`user_id` FK、`category`、`topic`、`ideological_direction`、`profession` JSONB、`content_preview`、`content`、`publish_date`、`version`、`evaluation` JSONB、`draft_count`、`drafts` JSONB、`generated_data` JSONB、`create_time` | 生成历史 |
| `ask_records` | `id` PK、`user_id` FK、`case_no`、`case_title`、`question`、`answer`、`create_time` | 问答历史 |
| `audit_logs` | `id` PK、`operator`、`username`、`action`、`target`、`detail`、`time` | 关键操作留痕 |
| `tags` | `id` PK、`name` UNIQUE、`use_count`、`status`、`create_time` | 思政标签，初始 18 个 |
| `professions` | `id` PK、`name` UNIQUE、`case_count`、`status`、`create_time` | 专业字典，初始 58 个 |

> 关键词、思政元素、专业、知识点等多值字段统一用 JSONB 存数组，与前端直接消费的数组结构一致。
> 暂不建 `case_versions` 表（非目标）。

## 7. API 实现清单（40 个）

路径前缀 `/api/v1`。下表的"前端函数"对应 `src/api/index.js` 现有导出，改造后保持同名同参。

### 7.1 账号与权限（9）

| # | 方法 路径 | 前端函数 | 要点 |
|---|---|---|---|
| 01 | POST `/auth/login` | `loginApi` | 校验密码与状态；冻结返回失败 |
| 02 | POST `/auth/logout` | `logoutApi` | 无状态，直接返回成功 |
| 03 | GET `/users/me` | `getUserInfoApi` | 返回前端形状 |
| 04 | PATCH `/users/me` | `updateUserInfoApi` | 局部更新 |
| 05 | PUT `/users/me/password` | `changePasswordApi` | 校验原密码 |
| 06 | POST `/users` | `createUserApi` | 管理员；默认密码 123456 |
| 07 | PATCH `/users/{id}` | `updateUserApi` | 调整角色 / 冻结 |
| 08 | POST `/users/{id}/reset-password` | `resetUserPwdApi` | 重置为 123456 |
| 09 | GET `/audit-logs` | `getAuditLogsApi` | 关键操作分页 |

### 7.2 案例检索、浏览与收藏（5）

| # | 方法 路径 | 前端函数 | 要点 |
|---|---|---|---|
| 10 | GET `/cases` | `getCaseListApi` | 仅已发布；支持 keyword/category/profession/tag/page/size/sort；`includeAll` 与 `status` 供管理复用 |
| 11 | GET `/cases/{id}` | `getCaseDetailApi` | case_no 或整数 |
| 12 | POST `/cases/{id}/favorite` | `addFavoriteApi` | 幂等收藏 |
| 13 | DELETE `/cases/{id}/favorite` | `removeFavoriteApi` | 幂等取消 |
| 14 | GET `/users/me/favorites` | `getFavoriteListApi` | 分页 |

### 7.3 案例生产（教师工作区）（8）

| # | 方法 路径 | 前端函数 | 要点 |
|---|---|---|---|
| 15 | POST `/cases` | `saveDraftApi` | 新建草稿；带 id 则更新 |
| 16 | GET `/cases/{id}` | （复用） | 本人可看各状态 |
| 17 | PATCH `/cases/{id}` | `saveDraftApi`（更新分支） | 编辑本人草稿/需补充 |
| 18 | DELETE `/cases/{id}` | `deleteDraftApi` | 仅草稿可删 |
| 19 | POST `/cases/{id}/submit` | `submitCaseApi` | 完整性校验后转待审核 |
| 20 | POST `/cases/parse` | `parseCaseApi` | 文本/文档抽取候选字段 |
| 21 | GET `/users/me/cases` | `getMyCasesApi` | 本人各状态分页 |
| 22 | GET `/cases/{id}/review` | `getReviewOpinionApi` | 状态、审核人、时间、意见 |

### 7.4 AI 生成与辅助评价（4）

| # | 方法 路径 | 前端函数 | 要点 |
|---|---|---|---|
| 23 | POST `/ai/generate`（SSE） | `generateCaseStreamApi` | 多稿 → 评分 → 择优 → 流式正文；结束推送评价与参考案例 |
| 24 | GET `/ai/records` | `getAiRecordListApi` | 本人 |
| 25 | GET `/ai/records/{id}` | `getAiRecordApi` | 单条详情 |
| 26 | DELETE `/ai/records/{id}` | `deleteAiRecordApi` | 本人 |

### 7.5 AI 智能问答（2）

| # | 方法 路径 | 前端函数 | 要点 |
|---|---|---|---|
| 27 | POST `/ai/ask/{caseId}`（SSE） | `chatAskApi` | 基于案例上下文流式回答；落问答记录 |
| 28 | GET `/users/me/ask-records` | `getAskRecordsApi` | 分页 |

### 7.6 管理后台（12）

| # | 方法 路径 | 前端函数 | 要点 |
|---|---|---|---|
| 29 | GET `/admin/reviews` | `getReviewListApi` | 审核队列，可按状态过滤 |
| 30 | POST `/admin/cases/{id}/review` | `reviewCaseApi` | 通过→已发布；需补充/驳回→附意见 |
| 31 | GET `/admin/cases` | `getCaseListApi(includeAll)` | 全量案例 |
| 32 | PATCH `/admin/cases/{id}` | `updateCaseApi` | 维护 |
| 33 | POST `/admin/cases/{id}/offline` | `offlineCaseApi` | 已发布→已下线，记原因 |
| 34 | POST `/admin/cases/import` | `importCasesApi` | 接收 JSON 行数组 |
| 35 | GET `/admin/cases/export` | `exportCasesApi` | 返回 CSV 文件流 |
| 36 | GET/POST `/admin/tags` | `getTagListApi` / `addTagApi` | 标签查询/新增 |
| 37 | PATCH `/admin/tags/{id}` | `updateTagApi` | 编辑/停用 |
| 38 | GET/POST `/admin/professions` | `getProfessionListApi` / `addProfessionApi` | 专业查询/新增 |
| 39 | PATCH `/admin/professions/{id}` | `updateProfessionApi` | 编辑/停用 |
| 40 | POST `/admin/statistics/home` | `getStatisticsApi` | 见下 |

补充两个前端已在用、文档 §6 未覆盖的接口（接口核对清单 A1/A2），一并实现：

| 编号 | 方法 路径 | 前端函数 | 说明 |
|---|---|---|---|
| A1 | GET `/users` | `getUserListApi` | 管理员用户列表 |
| A2 | GET `/home/index-data` | `getHomeIndexApi` | 首页平台数据 |

> 另：前端还调用了 `DELETE /admin/tags/{id}`（清单 B1）与 `getReviewListApi` 的删除路径，按前端现实一并实现。

### 7.7 SSE 协议

严格按详细设计 §3.1.5：`Content-Type: text/event-stream`，事件 `progress | content | references | evaluation | done | error`，`data` 为 JSON 字符串。前端 `api/sse.js` 用 `fetch` + `ReadableStream` 解析，转换成现有回调约定：

- `progress` → `onEvent({ type:'progress', message, step:index, total })`
- `content` → `onChunk(delta, accumulated)`
- `references` / `evaluation` / `done` → 收集到返回结果

## 8. AI 适配层

```
app/integrations/llm/
├── base.py                # 抽象：generate(params) -> drafts；ask(case, question) -> text
├── builtin.py             # 默认：确定性模板生成 + 评分 + 切片流式
├── openai_compatible.py   # 可选：OpenAI 兼容接口（DeepSeek 等）
└── factory.py             # 按配置选择
```

配置（`.env`）：

```
LLM_PROVIDER=builtin          # builtin | openai | maxkb
LLM_BASE_URL=                 # openai/maxkb 时必填
LLM_API_KEY=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=30
```

- **builtin（默认）**：把前端 `buildGeneratedCase` / `evaluateDraft` 的逻辑用 Python 重写为确定性模板（同样 3 稿、同样四个评分维度、按 2–4 字符切片流式）。无网、无 key 也能演示。
- **openai**：调用 OpenAI 兼容 `/chat/completions`，按同一套事件协议切分流式输出；失败自动降级到 builtin（`error` 事件前先尝试，避免演示中断）。
- **maxkb**：复用骨架中已有适配器，默认不启用。

## 9. 前端对接改造

只动对接层，不动页面：

1. **重写 `src/api/index.js`**：保留全部现有导出名、参数签名、返回形状；函数体改为调用 `request.js` 的 `get/post/put/del`。
2. **新增 `src/api/sse.js`**：SSE 解析器，供生成与问答使用。
3. **运行开关**：`VITE_USE_MOCK=true` 时沿用旧 mock（保留原实现到 `src/api/mock/index.js`），默认走真实请求。演示出问题可一键回退。
4. **`vite.config.js`**：开启代理 `/api` → `http://127.0.0.1:8000`。
5. **常量字典**：views 里从 `@/api/mockData` 导入的 `CASE_CATEGORIES / PROFESSIONS / IDEOLOGICAL_TAGS / REVIEW_STATUSES` 迁到 `src/api/constants.js`；`mockData.js` 仅保留旧 mock 分支使用。
6. **字段审计**：检查 views 对 `id`、`Number(id)`、`status` 的假设，保证后端返回形状下不出现 `NaN`。这是实现期必做项，不是页面重构。

### 9.1 需要前端 api 层处理的三个转换

这几处现有函数依赖 mock 的内存行为，改成真实请求时要显式处理：

1. **`submitCaseApi(data)` 无 id**：原 mock 在无 id 时"新建并提交"。真实实现需先 `POST /cases` 拿到 `id`，再 `POST /cases/{id}/submit`，最后返回 `{submitId, status:'待审核'}`。
2. **`chatAskApi(caseData, question)` 的原型**：AI 生成页可能对尚未入库的内容提问，此时没有 `caseId`。约定：有 `caseData.id` 时用真实编号；否则路径用 `draft`，并在请求体附带 `{ question, caseContext: caseData }`，后端基于上下文作答、不落案例关联。
3. **`generateCaseStreamApi` / `chatAskApi` 的 `fetch` 细节**：`fetch` 不走 axios，需手动带 `Authorization: Bearer <token>`、`Accept: text/event-stream`；解析失败时回落到一次性返回。**不依赖 axios 拦截器处理 401。**

### 9.2 案例编号的分配时机

`case_no` 在**创建草稿时**分配（`case_001` 递增），而不是发布时。原因是前端在草稿阶段就用 `id` 作为列表 key 与编辑标识。审核通过只改 `review_status`，不重新编号。

## 10. 种子数据

`backend/app/db/seed.py`（幂等，可重复执行）：

- 用户 8 个（沿用 `mockData.js`：student01/teacher01/admin01 等，密码统一 `123456`）。
- 案例约 12 条已发布 + 4 条提交记录（草稿/待审核/驳回/待审核）。
- 思政标签 18 个（文档 §5.5 一级标签）。
- 专业 58 个（文档 §5.4）。
- AI 生成记录 2 条、问答记录 2 条、审计日志 5 条。
- 统计与首页数据按真实聚合计算，演示时数字自洽。

## 11. 启动与演示

新增 `scripts/dev.ps1`（Windows）与 README 演示章节：

1. `cp .env.example .env`（首次）。
2. `docker compose --env-file .env -f infra/compose.yaml up -d postgres`。
3. 用 **Python 3.13** 建 venv：`py -3.13 -m venv backend/.venv`，安装依赖（清华镜像）。
   - 本机在 Git Bash 下 `py -3.13` 可能因路径含中文报 "Unable to create process"，此时改用绝对路径：`"C:/Users/22975/AppData/Local/Programs/Python/Python313/python.exe" -m venv backend/.venv`。启动脚本需自动探测并回退。
4. `alembic upgrade head` + `python -m app.db.seed`。
5. 启动后端：`uvicorn app.main:app --reload --port 8000`。
6. 启动前端：`npm install --registry=https://registry.npmmirror.com` + `npm run dev`。

演示账号：`student01 / teacher01 / admin01`，密码均 `123456`。

## 12. 验收标准

**功能闭环**

- [ ] 三个角色都能登录，菜单按角色显示，越权访问被后端拒绝（403）。
- [ ] 学生：检索（关键词/分类/专业/标签）、详情、收藏/取消、AI 问答流式出字。
- [ ] 教师：AI 生成出 3 稿择优、流式正文、辅助评价、参考案例；保存草稿；提交审核。
- [ ] 管理员：待审核队列看到教师提交；通过后学生能检索到；驳回后教师看到意见。
- [ ] 管理员：下线已发布案例；用户管理（创建/调角色/冻结/重置密码）；标签与专业增改；统计页有数。
- [ ] 全部数据来自 PostgreSQL：重启后端数据仍在，换浏览器仍能看到。

**稳定性**

- [ ] 断开外网、不配 `LLM_API_KEY`，AI 生成与问答仍完整可用。
- [ ] `VITE_USE_MOCK=true` 可回退到旧 mock 演示。
- [ ] 后端 `pytest` 冒烟（健康检查、登录、案例列表、审核流转）通过。

## 13. 风险与对策

| 风险 | 对策 |
|---|---|
| `python` 默认 3.14，不符合后端要求 | 启动脚本与文档强制 `py -3.13` / venv 绝对路径 |
| 精确版本依赖在 Windows 装不上 | 先按 `pyproject.toml` 装；受阻则放宽为兼容范围，并在文档注明 |
| Docker 端口 5433 被占用 | 启动脚本先 `compose ps` 检查，冲突时提示改端口 |
| 前端 id / 字段假设导致页面异常 | 实现后逐页冒烟；必要时只改 api 层做形状转换 |
| SSE 在浏览器与代理下的缓冲 | 后端关闭响应缓冲，前端用 `fetch` 流式读取；Vite 代理设置 `ws`/`stream` |
| 现场网络不稳 | builtin 生成器兜底；mock 开关兜底 |

## 14. 留给实现者的决定

- 密码哈希轮数、JWT 过期时长（取 `.env`，默认 7200 秒）。
- CSV 导出编码（建议 UTF-8 BOM，Excel 打开不乱码）。
- 统计接口的聚合口径（按真实表统计，字段名沿用 `mockStats` / `mockHomeIndex`）。
- `cases` 表索引（`review_status`、`category`、`publish_date`）——演示规模下可选。

## 15. 与文档的已知偏差（演示原型范围内接受）

1. 字段命名与文档不一致（见 §5.2），以现有前端为准。
2. 文档 §3.1.1 要求路径 `{id}` 统一为 `case_xxx`；本项目在教师工作区兼容整数主键。
3. 案例版本历史、真实内容安全、真实文档解析未实现。
4. 接口核对清单中的 A3（全部案例查询路径）按前端现实采用 `/cases?includeAll=true`，并在文档中记录该决议。
