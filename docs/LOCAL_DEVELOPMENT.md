# 本地开发指南（Windows）

> 本文档于 2026-11-25 自根目录 `README.md` 移入，留存原 README 中的本地开发与运维细节
> （含本机特有配置）。原 README 中已过时的进度描述（bootstrap 阶段状态、"System Design
> 缺失"、"Git 尚无提交"、"未实现业务功能"等）已剔除，现状以
> [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md) 为准。
> 项目介绍见根目录 [README](../README.md)。

- 工程约束：[`AGENTS.md`](../AGENTS.md)（必读）
- API 契约：[`contracts/openapi.yaml`](../contracts/openapi.yaml)（OpenAPI 3.1，唯一事实来源）
- 文档权威索引：[`README.md`](README.md)
- 阶段计划：[`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md)

## 一键启动 / 停止 / 状态（推荐）

仓库根目录提供三个 PowerShell 脚本（Windows PowerShell 5.1+，无需管理员权限）：

| 脚本 | 作用 |
|---|---|
| `start-dev.ps1` | 检查 Docker Desktop → 启动并等待 `awc-db` / `awc-languagetool` 健康 → 用项目内 venv 启动 FastAPI（:8000）、便携 Node 22 启动 Next.js（:3500）→ 健康检查 → 自动打开浏览器 |
| `stop-dev.ps1` | **只停止本项目的后端/前端进程**（按命令行特征精确匹配，不误杀其他项目；排除 E2E 的 :8001/:3600）。默认保留容器；加 `-Infrastructure` 同时停止容器（容器与数据卷保留） |
| `status-dev.ps1` | 只读查看 Docker / 容器健康 / 前后端进程 PID / 端点健康 / 日志位置 |

```powershell
powershell -ExecutionPolicy Bypass -File .\start-dev.ps1
powershell -ExecutionPolicy Bypass -File .\status-dev.ps1
powershell -ExecutionPolicy Bypass -File .\stop-dev.ps1
powershell -ExecutionPolicy Bypass -File .\stop-dev.ps1 -Infrastructure   # 同时停止容器（不删数据卷）
```

行为与安全保证：

- **幂等**：已运行且健康的服务不会重复启动（端口 + 健康检查 + 进程特征识别）；
  端口被占用但健康检查失败时报错退出，不会盲目再起一个实例。
- **仅项目内工具链**：`backend\.venv` 的 Python、`.tools\` 便携 Node 22；
  PATH 前置仅作用于脚本进程及其子进程，**不修改系统 PATH / 注册表 / 全局 Python**。
- **Docker Desktop 由用户手动启动**：脚本只检查，未运行时提示并退出，不改动任何系统配置。
- **停止策略**：应用进程与基础设施分离。默认只停应用；`-Infrastructure` 用
  `docker compose stop` 停容器，**从不执行 `down -v`，数据卷（pgdata）永不删除**。
- **不输出任何密钥或环境变量值**；日志只含进程/健康/容器状态信息。
- **日志**：`.dev\logs\`（已 gitignore）——`start-dev.log` / `stop-dev.log` /
  `status-dev.log`、`backend.out.log` / `backend.err.log`（uvicorn 日志在 stderr）、
  `frontend.out.log` / `frontend.err.log`（每次启动覆盖为最新一次运行）。
  进程 PID 记录在 `.dev\state.json`。
- `start-dev.ps1 -NoBrowser` 可跳过自动打开浏览器。

首次使用前请先完成下方「快速开始」的第 1、3 步（`.env` / `.env.local` 与依赖安装），
并确保数据库已迁移（第 4 步）。

## 环境要求（本机已按以下方式准备）

| 组件 | 说明 |
|---|---|
| Node.js | **便携版 v22.23.5**，位于 `.tools/node-v22.23.5-win-x64/`，不在系统 PATH |
| Python | **3.13.9** 虚拟环境 `backend/.venv`（勿用 `py` 默认的 3.14，勿装进 Anaconda base） |
| Docker | Docker Desktop **由用户手动启动**；本仓库不修改 Docker/WSL/系统配置 |

每个新终端会话先临时前置便携 Node 到 PATH（仅当前会话生效，不改系统设置；在仓库根执行）：

```bat
set "PATH=%CD%\.tools\node-v22.23.5-win-x64;%PATH%"
```

## 快速开始（clean local start）

以下命令均在仓库根 `ai-writing-coach/` 执行（Windows cmd）。

```bat
:: 0) 前置便携 Node（见上）

:: 1) 环境变量（首次）
copy .env.example .env
copy frontend\.env.example frontend\.env.local

:: 2) 启动 PostgreSQL + pgvector（需 Docker Desktop 已运行）
docker compose up -d db

:: 3) 后端依赖（首次；全局 pip 镜像不可用时必须显式指定官方源）
backend\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -e "backend[dev]"

:: 4) 数据库迁移（启用 pgvector 扩展）
cd backend
.venv\Scripts\alembic.exe upgrade head
cd ..

:: 5) 启动后端（新终端，端口 8000）
cd backend
.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000

:: 6) 启动前端（新终端，端口 3500；先执行第 0 步的 PATH 前置）
cd frontend
npm install
npm run dev
```

> 第 3 步也可在 `backend/` 目录内执行 `.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -e ".[dev]"`。

打开 http://localhost:3500 ，首页会实时显示后端健康状态；
直接访问 http://localhost:8000/api/v1/health 可看到原始 JSON。

> **为什么是 3500 而不是 3000？** 本机的 Windows Hyper-V/WinNAT 将 2955–3054
> 等端口段列为系统保留（`netsh interface ipv4 show excludedportrange protocol=tcp`
> 可查），绑定 3000 会报 `EACCES`。按约束不修改系统配置，故前端改用 3500，
> CORS 默认源同步为 `http://localhost:3500`。

## 健康检查语义（契约 v1.1.1 §23）

- `GET /api/v1/health`，无需认证。
- **200**：服务存活且 PostgreSQL 可达（真实 `SELECT 1` 探测）：
  `{"data": {"status": "ok", "database": "connected"}, "meta": {"request_id": "..."}}`
- **503**：服务存活但数据库不可达：
  `{"error": {"code": "DATABASE_UNAVAILABLE", "message": "Database is not reachable."}, "meta": {...}}`
- 不检查 LanguageTool / LLM / Redis；不返回连接串或凭据。

## 质量检查命令

| 检查 | 命令（目录） |
|---|---|
| 后端测试 | `pytest`（backend/，venv 内） |
| 后端 lint / 格式 | `ruff check .` / `ruff format --check .`（backend/） |
| 前端单元测试 | `npm run test:unit`（frontend/，Vitest） |
| 前端 lint | `npm run lint`（frontend/） |
| 前端类型检查 | `npx tsc --noEmit`（frontend/） |
| 前端生产构建 | `npm run build`（frontend/） |
| 前端 API 类型生成 | `npm run generate:api`（frontend/，读取 contracts/openapi.yaml） |
| OpenAPI 契约校验 | 由 `backend/tests/test_contract.py` 随 pytest 执行 |

数据库集成测试（`tests/test_health_integration.py`、`tests/test_migration_downgrade.py`）
在 PostgreSQL 不可达时**自动跳过**，不会谎报通过。启动数据库后重跑 pytest 即可执行真实集成验证。

E2E（`npx playwright test`，frontend/）使用隔离栈（后端 :8001 + 前端 :3600，测试库），
运行前需先暂停 :3500 dev server（Next 16 同目录单实例锁）。

## Docker 常用命令

端口仅绑定 `127.0.0.1`，不向其他网络接口暴露；因此 `DATABASE_URL` 使用
`127.0.0.1` 而非 `localhost`（本机 `localhost` 可能先解析到无响应的 `::1`）。

```bat
docker compose up -d db          :: 启动
docker compose ps                :: 状态（healthy 表示 pg_isready 通过）
docker compose logs -f db        :: 日志
docker compose stop db           :: 停止（数据保留在命名卷 pgdata）
docker compose down              :: 停止并删除容器（数据卷仍保留）
docker compose down -v           :: 重置：删除数据卷（ destructive，首次初始化脚本会重新执行）
```

## 环境变量

见 [`.env.example`](../.env.example)。要点：

- `DATABASE_URL`：SQLAlchemy 2.x + psycopg 3 连接串，须与 `POSTGRES_*` 一致。
- `CORS_ORIGINS`：JSON 数组，默认仅允许 `http://localhost:3500`。
- `NEXT_PUBLIC_API_BASE_URL`：Next.js 只读 `frontend/` 下的 env 文件，
  因此需同时写入 `frontend/.env.local`。
- `LLM_PROVIDER` / `EMBEDDING_PROVIDER`：默认 `mock`（开发/测试用，零成本）；
  真实 AI 效果需在 `.env` 配置真实 provider 与密钥（密钥永不提交）。
- `.env`、`frontend/.env.local` 均已被 `.gitignore` 排除。

## 现状与更多细节

- 功能完成状态与验证证据：[TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md)
- 公开发布前置事项：[LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md)
- 本机特殊配置与已知坑（pip 镜像、npm 速度、Playwright CDN、IPv6 黑洞、
  Next 16 单实例锁等）：[`PROJECT_HANDOFF.md`](../PROJECT_HANDOFF.md) §6