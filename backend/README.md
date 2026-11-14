# Backend — AI Writing Coach (FastAPI)

Stage 1 bootstrap + **Stage 2 Slice 1 后端认证**：FastAPI 模块化单体 + SQLAlchemy 2.x +
Alembic + 数据库感知健康检查 + 完整认证模块（注册/登录/刷新/登出/会话/用户资料）。
**无 Essay 等业务功能、无 LLM**。工程约束见仓库根 `AGENTS.md`。

## 环境

- Python **3.13.9**，虚拟环境 `.venv`（已创建，隔离于 Anaconda base）。
- 激活（cmd）：`.venv\Scripts\activate.bat`；PowerShell：`.venv\Scripts\Activate.ps1`。
- 依赖安装（全局 pip 镜像不可用，必须显式指定官方源）：

```bat
.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -e ".[dev]"
```

## 配置

配置由 `app/core/config.py`（pydantic-settings）加载，环境变量优先，
其次读取**仓库根** `.env`（从 `.env.example` 复制）。关键项：

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://awc:awc_local_dev@127.0.0.1:5432/ai_writing_coach` | 本地开发默认值；用 `127.0.0.1` 而非 `localhost`（db 仅绑定 IPv4 回环，`localhost` 可能先解析到被黑洞的 `::1`） |
| `DATABASE_CONNECT_TIMEOUT` | `5` | 连接超时（秒），健康探测与 Alembic 均不会无限挂起 |
| `CORS_ORIGINS` | `["http://localhost:3500"]` | 仅本地前端源（3000 被系统保留端口段占用，见根 README） |

CORS 方法与请求头为**显式白名单**（`app/main.py`）：方法 `GET/POST/PUT/PATCH/DELETE`
（契约所用），请求头 `Content-Type/Authorization/Idempotency-Key`（契约文档化头）。

认证相关配置（完整列表见 `.env.example`）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `JWT_SECRET` | dev-only 占位 | **真实部署必须改为 ≥64 字符随机值** |
| `JWT_ISSUER` / `JWT_AUDIENCE` | `ai-writing-coach` / `ai-writing-coach-api` | JWT 校验强制匹配 |
| `ACCESS_TOKEN_TTL_SECONDS` | `900` | Access Token 15 分钟 |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | Refresh Token 与设备会话有效期 |
| `REFRESH_COOKIE_NAME` / `REFRESH_COOKIE_PATH` | `awc_refresh_token` / `/api/v1/auth` | Cookie 作用域限定认证路径 |
| `AUTH_RATE_LIMIT_MAX_REQUESTS` / `AUTH_RATE_LIMIT_WINDOW_SECONDS` | `20` / `300` | 注册/登录进程内限流预留（按 IP） |

应用导入不需要任何生产凭据。

## 认证模块（Stage 2 Slice 1）

接口（均在 `/api/v1` 下，契约 `contracts/openapi.yaml`）：
`POST /auth/register`、`POST /auth/login`、`POST /auth/refresh`、`POST /auth/logout`、
`POST /auth/logout-all`、`GET /auth/sessions`、`DELETE /auth/sessions/{session_id}`、
`GET /users/me`、`PATCH /users/me`。

安全设计：

- **密码**：Argon2id（argon2-cffi）；未知邮箱用诱饵哈希保持时序一致；明文不落库、不落日志。
- **Access Token**：JWT HS256 固定算法，校验签名/过期/issuer/audience；claims 含
  `sub`（用户）、`sid`（设备会话）、`jti`；前端只存内存。
- **Refresh Token**：`secrets.token_urlsafe(64)` 高熵不透明令牌；服务端只存 SHA-256 哈希
  （唯一约束）；仅经 `HttpOnly + Secure + SameSite=Strict + Path=/api/v1/auth` Cookie 传递，
  **不出现在 JSON 响应体**。
- **设备会话与轮换**：`auth_sessions` 为稳定设备会话；轮换在同一事务内消费旧 Token 并
  创建新 Token（同一 `token_family_id`、`replaced_by_token_id` 链接），**不创建新会话**。
  部分唯一索引保证每会话至多一个有效未消费 Token。
- **重用检测**：已消费 Token 被再次使用 → 撤销整个 Token Family 并撤销会话
  （`REFRESH_TOKEN_REUSE_DETECTED`）。并发刷新由会话行锁 + Token 行锁 + 状态复查保证
  恰好一个成功；前端配套 single-flight。锁查询使用 `populate_existing` 防止 ORM 旧读。
- **CSRF**：SameSite=Strict Cookie + refresh 端点 Origin 校验（仅允许配置的本地源）；
  不引入契约之外的请求头。
- **身份来源**：用户 ID 一律取自验证后的 JWT + 服务端会话状态（`app/api/deps.py`），
  不信任客户端传入的 `user_id`；会话撤销后 Access Token 立即失效。
- **限流**：注册/登录进程内滑动窗口（按 IP），429 `RATE_LIMIT_EXCEEDED`；
  存储点隔离，后续可换共享存储。
- **错误信封**：统一 `{"error":{"code","message","details"},"meta":{"request_id"}}`，
  错误码遵循 API Spec §19。

## 运行

```bat
.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

- 健康检查：`GET http://localhost:8000/api/v1/health`
- 交互式文档：`http://localhost:8000/docs`

## 数据库与迁移

先启动数据库（仓库根）：`docker compose up -d db`。

```bat
.venv\Scripts\alembic.exe upgrade head        :: 应用迁移（0001 pgvector；0002 认证四表）
.venv\Scripts\alembic.exe current             :: 查看当前版本
.venv\Scripts\alembic.exe downgrade -1        :: 回退一步
.venv\Scripts\alembic.exe revision --autogenerate -m "..."   :: 未来新增模型后生成迁移
```

- `alembic/env.py` 从 `Settings` 读取连接串，`alembic.ini` 不含凭据。URL 不经
  ConfigParser 插值，百分号编码密码（如 `p%40ss`）可正常使用。
- 迁移 `0001` 仅幂等启用 `vector` 扩展。**downgrade 为有意的空操作**：回滚不删除扩展，
  避免未来存在 vector 依赖对象时误删；移除 pgvector 须作为显式人工操作。
- 迁移 `0002` 创建 `users`、`user_profiles`、`auth_sessions`、`auth_refresh_tokens`
  （ERD V1.2 §5）：邮箱唯一、Token 哈希唯一、每会话至多一个有效未消费 Token 的部分唯一
  索引、ERD 指定索引、替换链自引用外键。downgrade 按依赖逆序删表。
- Docker 首次初始化也会执行 `infrastructure/postgres/init.sql`（同样幂等）。

## 测试

```bat
.venv\Scripts\pytest.exe
```

| 文件 | 内容 | 需要数据库 |
|---|---|---|
| `tests/test_health.py` | 200/503 信封、错误码、无需认证（mock 探测） | 否 |
| `tests/test_contract.py` | OpenAPI 3.1 全量校验；路由/方法与契约一致；Pydantic 信封与契约 Schema 语义一致 | 否 |
| `tests/test_cors.py` | 方法/请求头白名单、非法方法/头/源被拒、本地源放行 | 否 |
| `tests/test_compose.py` | PostgreSQL 端口仅绑定 127.0.0.1 | 否 |
| `tests/test_alembic_url.py` | 百分号编码密码的 URL 可生成离线迁移 SQL（真实 env.py） | 否 |
| `tests/test_health_integration.py` | 真实 `SELECT 1` 健康检查、pgvector 扩展存在 | 是（不可达时自动 skip） |
| `tests/test_migration_downgrade.py` | downgrade 不删除 vector 扩展，随后恢复 head | 是（不可达时自动 skip） |
| `tests/auth/` | 认证全量集成测试：注册/登录/哈希、Access Token 校验、轮换与重用检测、会话与登出、资料隔离、Cookie/CSRF/限流、并发刷新、唯一约束 | 是（独立测试库） |

认证测试使用**独立测试数据库** `ai_writing_coach_test`（会话级夹具自动创建并迁移，
每个测试前 TRUNCATE 隔离），不触碰开发库数据；开发库不可达时认证测试会失败而非静默跳过。

## Lint / 格式

```bat
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
```

## 结构

```text
app/
├── main.py               # create_app：CORS 白名单 + 错误信封处理器 + /api/v1 路由
├── api/
│   ├── deps.py           # 认证上下文 DI（JWT + 会话状态）、refresh Origin 校验
│   └── v1/               # 薄路由：health.py、auth.py、users.py、router.py
├── core/                 # config、security（Argon2id/JWT/Token）、rate_limit、
│                         # exceptions（ApiError）、errors、time
├── infrastructure/       # database.py：engine、get_db 依赖、SELECT 1 探测
├── modules/
│   ├── auth/             # models（AuthSession/AuthRefreshToken）、repository、
│   │                     # service（轮换/重用检测/撤销）、schemas
│   └── users/            # models（User/UserProfile）、repository、service、schemas
└── schemas/              # common（信封）、health（对齐契约）
alembic/                  # env.py + versions/0001_enable_pgvector.py、0002_auth_tables.py
tests/                    # Stage 1 测试 + tests/auth/ 认证集成测试
```

分层约定：**Router → Service → Repository → SQLAlchemy**；密码哈希/JWT/Token
生成与验证集中在 `core/security.py`；路由不写业务逻辑。
