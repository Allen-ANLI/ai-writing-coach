# Frontend — AI Writing Coach (Next.js)

Next.js 16 App Router + TypeScript strict + Tailwind CSS 4 + ESLint 9 + TanStack Query。
当前进度：Stage 1 骨架 + Slice 1.5 前端认证 + Slice 2A Essay 管理 + Slice 2B 文档生命周期
API + **Slice 2C TipTap 写作编辑器**（自动保存/冲突恢复/字数/撤销重做/左侧大纲/版本历史
与恢复）。语法反馈、AI 辅助等为后续切片。工程约束见仓库根 `AGENTS.md`。

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
npm run test:unit     :: Vitest 单元测试（位置映射 / 字数规则）
npm run generate:api  :: 从 contracts/openapi.yaml 生成 src/types/generated.ts
```

## E2E 测试（Playwright）

```bat
npx playwright install chromium   :: 首次（下载浏览器；本机 CDN 停滞时配置已用 msedge 通道）
npx playwright test               :: 运行 e2e/auth.spec.ts + e2e/essays.spec.ts
```

测试使用**完全隔离的栈**（`playwright.config.ts` 的 webServer 自动起停）：

- 后端 `:8001` → `ai_writing_coach_test` 库（globalSetup 自动建库+迁移），
  `ACCESS_TOKEN_TTL_SECONDS=2` 以便验证过期/刷新路径，CORS 允许 `:3600`。
- 前端 dev `:3600` → 指向 `:8001`。
- 不触碰开发环境（`:8000`/`:3500` 与开发库数据）。

覆盖：注册、登录成功/失败、页面刷新恢复、过期自动刷新、并发 401 单飞刷新（计数断言
恰好 1 次）、refresh 失败退出、logout 后会话不可恢复、未登录保护重定向、登录后正常
访问、Cookie 对 JavaScript 不可见且 HttpOnly/Secure/SameSite=Strict/Path 正确；
Essay：Dashboard 加载态/空态、创建与列表刷新、改名、删除确认（取消保留）、详情导航、
删除后详情错误态、未登录保护；编辑器：输入自动保存并刷新后保留、字数、撤销重做、
Ctrl+S、checkpoint + 恢复、保存冲突保留本地并可恢复、标题生成左侧大纲。
E2E 后端放宽注册限流（`AUTH_RATE_LIMIT_MAX_REQUESTS`，仅隔离栈；生产默认不变）。

## Essay 管理（Stage 2 Slice 2A）

- `/dashboard`（受保护）：Essay 列表、创建（标题可选 + writing_type）、改名、
  删除需确认对话框；加载/空/错误三态齐全；TanStack Query mutation + 失效刷新。

## 写作编辑器（Stage 2 Slice 2C）

`/essays/[id]`（受保护）即写作编辑器，确认布局：宽中央编辑区 + 左侧可折叠大纲
（默认展开，窄屏为浮层），**无常驻右侧 AI 面板**。

- **TipTap / ProseMirror**（StarterKit）：段落/标题/加粗/斜体/列表/引用/撤销重做。
- **自动保存**：编辑防抖 1.5s 后 PUT working-document（乐观并发 base_revision）；
  Ctrl/Cmd+S 立即保存；底部状态条显示 Saved / Unsaved / Saving… / 冲突 / 失败。
- **冲突恢复**：409 时保留本地编辑、暂停保存，提供「Copy my text」与
  「Load latest version」；绝不静默覆盖。
- **字数**：与后端同一规则（空白分词），服务端会再次推导校验。
- **中文输入法**：composition 期间不触发保存，compositionend 后再保存。
- **版本历史**：History 对话框列出不可变快照，可只读查看、创建 checkpoint
  （可选 label，Idempotency-Key 去重）、确认后恢复（原子更新 + Edit Event）。
- **位置映射**：`lib/text-positions.ts` 提供 unicode_codepoint ↔ UTF-16 ↔
  ProseMirror 位置转换（AGENTS 硬性不变量），Vitest 单测覆盖 emoji/CJK。
- 装饰与提示不进入持久化正文（后续语法切片同样遵守）。

## UI 截图（审查用）

```bat
node awc-screenshots.mjs   :: 需 :8000 后端 + :3500 前端运行中；输出 test-results/screenshots/
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` | 后端 API 基址（含 `/api/v1` 前缀） |

Next.js 只读取 `frontend/` 目录下的 env 文件；`.env.local` 已被 `.gitignore` 排除。

## 结构

```text
src/
├── app/                    # layout + providers、/、/login、/register、/profile、
│                           # /dashboard、/essays/[id]（写作编辑器）
├── components/             # health-status、auth-nav、dialog（可访问模态框）
├── features/auth/          # auth-provider（Context）、require-auth、login/register 表单
├── features/essays/        # essay-dialogs（创建/改名/删除确认）
├── features/editor/        # writing-editor、use-autosave、outline-panel、
│                           # version-history、editor-route
├── lib/                    # config、api-client（内存 token + 单飞刷新）、
│                           # text-positions（codepoint↔UTF-16↔PM）、document-text
├── services/               # health、auth、essays、documents（类型化 API 调用）
└── types/                  # api.ts（开放响应体手写镜像）+ generated.ts（契约生成）
e2e/                        # global-setup、auth.spec、essays.spec、editor.spec
scripts/generate-api-types.mjs  # 契约 → TS 类型生成（解析 YAML 锚点）
awc-screenshots.mjs         # UI 截图审查工具
playwright.config.ts        # 隔离 E2E 栈定义
vitest.config.ts            # 单元测试配置
```

API 类型：契约中封闭的 schema 由 `npm run generate:api` 生成到 `src/types/generated.ts`
并在 `api.ts` 重导出；契约未定义形状的响应体仍在 `api.ts` 手写镜像并与
`contracts/openapi.yaml` / API Spec 对齐。契约变更后需重新生成。
