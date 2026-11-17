# 一键启动：PostgreSQL → 迁移 → 种子 → FastAPI
# 用法：powershell -ExecutionPolicy Bypass -File scripts/dev.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root "backend/.venv/Scripts/python.exe"
$Py313 = "C:/Users/22975/AppData/Local/Programs/Python/Python313/python.exe"

Write-Host "==> [1/5] 检查 .env" -ForegroundColor Cyan
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "已从 .env.example 生成 .env，请按需修改数据库密码与 SECRET_KEY。" -ForegroundColor Yellow
}

Write-Host "==> [2/5] 启动 PostgreSQL" -ForegroundColor Cyan
docker compose --env-file .env -f infra/compose.yaml up -d postgres

Write-Host "==> [3/5] 等待数据库健康" -ForegroundColor Cyan
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    $status = docker inspect --format "{{.State.Health.Status}}" llm-ideological-case-platform-postgres-1 2>$null
    if ($status -eq "healthy") {
        $healthy = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $healthy) {
    throw "PostgreSQL 未在预期时间内就绪，请检查 Docker Desktop 与 5433 端口。"
}

Write-Host "==> [4/5] 准备 Python 3.13 环境" -ForegroundColor Cyan
if (-not (Test-Path $Python)) {
    if (-not (Test-Path $Py313)) {
        throw "未找到 Python 3.13。请先安装 https://www.python.org/downloads/release/python-3139/"
    }
    & $Py313 -m venv "$Root/backend/.venv"
}
& $Python -c "import fastapi" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "安装后端依赖（清华镜像）..." -ForegroundColor Yellow
    & $Python -m pip install -e "$Root/backend[test]" -i https://pypi.tuna.tsinghua.edu.cn/simple
}

Write-Host "==> [5/5] 迁移与种子数据" -ForegroundColor Cyan
Push-Location "$Root/backend"
try {
    & $Python -m alembic upgrade head
    & $Python -m app.db.seed
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "数据库与种子数据已就绪。" -ForegroundColor Green
Write-Host "后端即将启动：http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "请在另一个终端运行前端：" -ForegroundColor Yellow
Write-Host "  cd frontend" -ForegroundColor Yellow
Write-Host "  npm install --registry=https://registry.npmmirror.com" -ForegroundColor Yellow
Write-Host "  npm run dev" -ForegroundColor Yellow
Write-Host ""
Write-Host "演示账号：student01 / teacher01 / admin01，密码均为 123456" -ForegroundColor Green
Write-Host ""

Push-Location "$Root/backend"
try {
    & $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}
