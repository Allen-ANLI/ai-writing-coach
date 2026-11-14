# Frontend — AI Writing Coach (Next.js)

Next.js 16 App Router + TypeScript strict + Tailwind CSS 4 + ESLint 9 + TanStack Query。
当前进度：Stage 1 骨架 + **Stage 2 Slice 1.5 前端认证**（注册/登录/会话恢复/自动刷新/
保护路由/当前用户资料）。Essay CRUD、编辑器等产品功能仍为后续阶段。
工程约束见仓库根 `AGENTS.md`。

## 环境

- 使用仓库内**便携 Node.js v22.23.5**（`.tools/node-v22.23.5-win-x64/`）。
  每个新终端先执行（仅当前会话生效）：

```bat
set "PATH=D:\DOCUMENTS\Projects\ai-writing-coach\.tools\node-v22.23.5-win-x64;%PATH%"
```

## 安装与运行

```bat
npm install
copy .env.example .env.local   :: 首次
npm run dev                    :: http://localhost:3500（3000 被 Windows 保留端口段占用）
```

后端需同时在 8000 端口运行（见 `backend/README.md`）。

## 认证架构（Slice 1.5）

- **Access Token 仅存内存**（`lib/api-client.ts` 模块级变量）；不写 localStorage /
  sessionStorage / cookie / 日志。
- **Refresh Token 完全由 HttpOnly Cookie 管理**（后端设置 `Secure + SameSite=Strict +
  Path=/api/v1/auth`）；前端所有请求 `credentials: "include"`，从不读取 cookie 值。
- **页面刷新恢复**：AuthProvider 挂载时执行一次静默 refresh（单飞），成功则拉取
  `/users/me` 恢复会话，失败则进入未认证态。
- **自动刷新 + 单飞**：任意 API 收到 401 → 共享同一个 refresh Promise（并发 401 只
  触发一次 refresh）→ 成功后原请求**仅重试一次**。仅对 401 重试（后端在业务逻辑前
  拒绝，无副作用，非幂等请求安全）；网络错误/5xx 一律不重试。
- **Refresh 失败**：清空内存 token 与 TanStack Query 缓存，退出认证态并跳转登录页。
- **CSRF**：浏览器自动附带 Origin，后端校验；前端不绕过、不伪造。
- **保护路由**：`RequireAuth` 在会话恢复完成前不渲染受保护内容，未认证重定向 `/login`。
- 服务端状态（资料、设备会话）用 TanStack Query；认证会话状态用 React Context。

页面：`/`（落地页 + 健康状态 + 认证导航）、`/login`、`/register`、`/profile`（受保护，
展示当前用户资料与设备会话，含 Refresh data / Sign out）。

## 检查命令

```bat
npm run lint          :: ESLint（eslint-config-next）
npx tsc --noEmit      :: TypeScript strict 检查
npm run build         :: 生产构建
npm run start         :: 运行生产构建
```

## E2E 测试（Playwright）

```bat
npx playwright install chromium   :: 首次（下载浏览器）
npx playwright test               :: 运行 e2e/auth.spec.ts
```

测试使用**完全隔离的栈**（`playwright.config.ts` 的 webServer 自动起停）：

- 后端 `:8001` → `ai_writing_coach_test` 库（globalSetup 自动建库+迁移），
  `ACCESS_TOKEN_TTL_SECONDS=2` 以便验证过期/刷新路径，CORS 允许 `:3600`。
- 前端 dev `:3600` → 指向 `:8001`。
- 不触碰开发环境（`:8000`/`:3500` 与开发库数据）。

覆盖：注册、登录成功/失败、页面刷新恢复、过期自动刷新、并发 401 单飞刷新（计数断言
恰好 1 次）、refresh 失败退出、logout 后会话不可恢复、未登录保护重定向、登录后正常
访问、Cookie 对 JavaScript 不可见且 HttpOnly/Secure/SameSite=Strict/Path 正确。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` | 后端 API 基址（含 `/api/v1` 前缀） |

Next.js 只读取 `frontend/` 目录下的 env 文件；`.env.local` 已被 `.gitignore` 排除。

## 结构

```text
src/
├── app/                    # layout + providers、/、/login、/register、/profile
├── components/             # health-status.tsx、auth-nav.tsx
├── features/auth/          # auth-provider（Context）、require-auth、login/register 表单
├── lib/                    # config.ts、api-client.ts（内存 token + 单飞刷新 + 一次性重试）
├── services/               # health.ts、auth.ts（类型化 API 调用）
└── types/                  # api.ts（契约类型手写镜像：health + auth + me + sessions）
e2e/                        # global-setup.ts、auth.spec.ts
playwright.config.ts        # 隔离 E2E 栈定义
```

API 类型手写在 `src/types/api.ts` 并与 `contracts/openapi.yaml` / API Spec §3.2 对齐；
完整的 OpenAPI 类型生成在后续阶段引入（契约含 YAML 锚点，需先解析）。
