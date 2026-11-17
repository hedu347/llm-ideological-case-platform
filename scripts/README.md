# 演示与联调脚本

## 一键启动后端

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

脚本会依次完成：检查 `.env` → 启动 PostgreSQL → 等待健康 → 准备 Python 3.13 虚拟环境 → 执行迁移 → 写入种子数据 → 启动 FastAPI。

## 启动前端

另开一个终端：

```bash
cd frontend
npm install --registry=https://registry.npmmirror.com
npm run dev
```

访问 `http://localhost:5174`，Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 演示账号

| 角色 | 账号 | 密码 |
|---|---|---|
| 学生 | student01 | 123456 |
| 教师 | teacher01 | 123456 |
| 管理员 | admin01 | 123456 |

## 端到端冒烟

后端启动后，在项目根目录执行：

```bash
backend/.venv/Scripts/python scripts/e2e_smoke.py
```

覆盖登录、检索、AI 生成、提交审核、审核发布、学生可检索与问答。

## 回退到 Mock

如果现场后端异常，可让前端回到旧的假数据：

```bash
cd frontend
VITE_USE_MOCK=true npm run dev
```

Windows PowerShell：

```powershell
$env:VITE_USE_MOCK="true"; npm run dev
```
