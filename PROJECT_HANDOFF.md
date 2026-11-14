# PROJECT_HANDOFF — AI Writing Coach

**生成时间：** 2026-11-14（所有测试结果为当日实际运行，非历史报告）
**用途：** 供全新 Codex 会话接手全产品自主开发。仅凭 `AGENTS.md` + `docs/` 正式设计文档 + 本文件即可理解现状并继续。
**生成方式：** 只读盘点 + 实测 + 本文档生成；未修改业务代码、数据库、Git 状态，未删除任何文件。

## 0. 阅读顺序（新会话必读）

1. `AGENTS.md` — 最高优先级工程约束（技术栈、架构规则、领域不变量、测试要求）
2. `docs/AI_Writing_Coach_System_Design_V1.1.md` — **系统设计基线已到位**（959 行；此前长期缺失，现已由用户补入，尚未提交 Git）。注意：`docs/README.md` 与 `docs/DEVELOPMENT_PLAN.md` 中"System Design MISSING"的记载已**过时**，以本文件与实物为准
3. `docs/DATABASE_ERD.md`（ERD V1.2，29 实体）、`docs/API_SPECIFICATION.md`（V1.1.1）、`contracts/openapi.yaml`（OpenAPI 3.1，info.version 1.1.1，唯一机器可读契约）
4. `docs/DEVELOPMENT_PLAN.md` — 阶段记录（Stage 0/1/2 Slice 1/1.5/2A）
5. 本文件其余章节

文档权威顺序：AGENTS.md > 契约（形状）> ERD/API Spec（业务语义）> 系统设计（架构）。冲突时停下报告，不擅自取舍。

---

## 1. Git 状态

| 项 | 值 |
|---|---|
| 仓库根 | `D:\DOCUMENTS\Projects\ai-writing-coach`（父目录 `Projects` **不是**仓库，禁止在父级 init） |
| 当前分支 | `main` |
| 最新提交 | `7e4aa60` — `feat: complete infrastructure and authentication`（根提交，111 文件：Stage 1 + Slice 1 后端认证 + Slice 1.5 前端认证 + register 409 契约修复） |
| 暂存区 | 空（无 staged 内容） |
| Git 身份 | 已配置（user.name/user.email 见 git config），可直接提交 |
| 行尾 | 系统级 `core.autocrlf=true`（Git for Windows 默认）；仓库存 LF，工作区 CRLF 警告属正常 |

### 已修改未提交（9 个，全部属于 Slice 2A，等待人工审查后才能提交）

```
README.md
backend/README.md
backend/app/api/v1/router.py          # 挂载 essays 路由
backend/tests/auth/conftest.py        # 改用共享夹具 tests/pg_fixtures.py
docs/DEVELOPMENT_PLAN.md
frontend/README.md
frontend/src/app/profile/page.tsx     # 增加 Dashboard 导航链接
frontend/src/components/auth-nav.tsx  # 增加 Dashboard 导航链接
frontend/src/types/api.ts             # 增加 essay 类型镜像
```

### 未跟踪文件（全部保留，不得清理）

```
backend/alembic/versions/0003_essay_tables.py
backend/app/api/v1/essays.py
backend/app/modules/essays/           # __init__/models/repository/service/schemas
backend/tests/essays/                 # conftest/essay_helpers/test_essays（16 用例）
backend/tests/pg_fixtures.py          # auth+essays 共享的隔离 PG 夹具
docs/AI_Writing_Coach_System_Design_V1.1.md   # 用户新补入的系统设计基线！
frontend/e2e/essays.spec.ts           # 7 个 E2E 用例
frontend/src/app/dashboard/           # Dashboard 页
frontend/src/app/essays/              # /essays/[id] 详情页
frontend/src/components/dialog.tsx    # 可访问模态框
frontend/src/features/essays/         # essay-dialogs / essay-detail
frontend/src/services/essays.ts
```

被 .gitignore 排除（不提交）：`.env`、`frontend/.env.local`、`node_modules/`、`.venv/`、`.tools/`、`.next/`、`test-results/`（含 3 张 UI 截图）、各类缓存、egg-info。

---

## 2. 已完成的功能（四级分类）

### 2.1 已实现并通过测试

**后端（FastAPI 模块化单体，Router→Service→Repository→SQLAlchemy）**
- `GET /api/v1/health`：真实 `SELECT 1` 探测；200 健康 / 503 `DATABASE_UNAVAILABLE` 信封
- 认证全模块（9 接口）：register/login/refresh/logout/logout-all/sessions 列表/会话撤销/users.me GET/PATCH
  - Argon2id 密码哈希（含未知邮箱时序诱饵）；HS256 JWT（签名/exp/iss/aud/固定算法）；高熵不透明 Refresh Token 仅存 SHA-256 哈希；HttpOnly+Secure+SameSite=Strict Cookie（Path=/api/v1/auth）；事务内轮换不建新会话；已消费 Token 重用→撤销 Family+会话；会话先锁的统一锁序 + `populate_existing` 防 ORM 旧读；CSRF=SameSite+Origin 校验；注册/登录进程内滑动窗口限流
- Essay CRUD（5 接口）：原子创建 Essay+空工作文档+Original 快照（单事务，回滚测试证明）；游标分页（opaque base64，limit 1–100 默认 20）；仅 title 可 PATCH；软删除；用户隔离（他人/已删除一律 404）
- 统一错误信封 `{error:{code,message,details},meta:{request_id}}`（API Spec §19 错误码）；422 校验信封
- Alembic 0001–0003；URL 不经 ConfigParser 插值（百分号密码可用）；迁移引擎带 connect_timeout

**前端（Next.js 16.4.6 App Router + TS strict + Tailwind 4 + TanStack Query）**
- 页面：`/`（落地+健康状态+认证导航）、`/login`、`/register`、`/profile`（受保护：资料+设备会话+Dashboard 入口）、`/dashboard`（受保护：列表/创建/改名/删除确认，加载/空/错误三态）、`/essays/[id]`（受保护：元数据+工作文档摘要；Suspense 包裹动态参数）
- 认证基础设施：Access Token 仅内存；单飞 refresh（并发 401 共享一个请求）；401 后原请求仅重试一次（仅 401 重试，非幂等安全）；refresh 失败清 token+Query 缓存并退出登录；页面刷新静默恢复会话；RequireAuth 路由守卫；Refresh Token 绝不进 JSON/localStorage/日志
- E2E 隔离栈：Playwright webServer 自动起停后端 :8001（测试库、TTL 2s）+ 前端 :3600

### 2.2 已实现但测试不完整 / 有意预留

- `Idempotency-Key` 请求头：按契约接受，**去重存储未实现**（预留，后续切片）
- 限流：进程内存储，仅单 worker 正确；扩容需共享存储（存储点已隔离在 `app/core/rate_limit.py`）
- `essays.status` / `users.status` 的 CHECK 取值集合为 bootstrap 决策（见 §4.4），无产品级验证
- 快照不可变性：应用层保证（无任何可变路径+测试断言），**无 DB 触发器**兜底
- 前端 API 类型为手写镜像（`src/types/api.ts`），非 OpenAPI 生成（契约含 YAML 锚点，生成需先解析）

### 2.3 仅有基础框架

- `app/modules/` 模块化目录结构（auth/users/essays 已填充；grammar/expressions/learning/ielts/workflows 等待首个真实文件时创建，**不要预建空目录**）
- TanStack Query Provider、Dialog 组件、api-client 传输层（可直接复用）
- `infrastructure/postgres/init.sql`（仅 pgvector 幂等启用）
- Redis/Celery/LanguageTool/LangGraph：**未引入**（AGENTS 禁止在 bootstrap 期加入）

### 2.4 尚未实现（契约 87 个操作中的 72 个）

Working Document 读写/自动保存、快照与版本 API、restore、Writing Sessions、Grammar Check、Issue 生命周期（validate/reveal/teaching/ignore）、表达润色/中文翻译/建议接受、个人知识库 CRUD/搜索/提取、学习复习/计划/任务/摘要、错误画像、IELTS 题库/收藏、评分/改写/接受、大纲/节点、LangGraph 工作流、AI 用量分析、`/users/me/preferences`。
前端：TipTap 编辑器、语法反馈 UI、教学浮层、知识库 UI、IELTS UI、Dashboard 完整功能。

---

## 3. 数据库状态

| 项 | 值 |
|---|---|
| Alembic head | `0003`（开发库与测试库一致） |
| 已执行迁移 | `0001_enable_pgvector`（CREATE EXTENSION vector，downgrade 为有意空操作）→ `0002_auth_tables` → `0003_essay_tables` |
| 容器 | `awc-db`，镜像 `pgvector/pgvector:pg17`，healthy，**仅绑定 127.0.0.1:5432**，命名卷 `pgdata` 持久化 |
| 扩展 | vector 0.8.7 |
| 开发库 | `ai_writing_coach`（含少量 smoke/截图测试账号，无害） |
| 测试库 | `ai_writing_coach_test`（pytest 夹具与 E2E globalSetup 自动创建/迁移，每测试 TRUNCATE；含累积 E2E 用户） |

### 实际实体（7/29，ERD V1.2）

`users`、`user_profiles`、`auth_sessions`、`auth_refresh_tokens`（ERD §5）；
`essays`、`essay_working_documents`、`essay_versions`（ERD §6.1–6.4）。另有 `alembic_version`。

关键约束（已建）：邮箱唯一；token_hash 唯一；**每会话至多一个有效未消费 Token 的部分唯一索引**；会话/Token 索引按 ERD；essays `(user_id, updated_at DESC)`；essay_versions UNIQUE(essay_id, version_no)、UNIQUE(essay_id, id)、**复合 FK** 保证 original/final 指针与 parent 链属于同一 Essay；writing_type/version_type/status CHECK。

### ERD 与实际差异 / 未解决约束

1. **22 个实体未建**（ERD §6.5 起：edit_events、issues、suggestions、teachings、evaluations、rewrites、expressions 系列、progress/reviews、weaknesses、IELTS 系列、outlines、learning 系列、ai_usage_logs）
2. `essays.question_id`：UUID 列已建，**FK 延后**（目标表 ielts_questions 属后续切片，本阶段禁建）；当前仅 UUID 格式校验，无存在性校验
3. `essays.status` CHECK ('active','archived') 为**临时决策，ERD 未枚举，待用户批准**
4. `users.status` CHECK ('active','disabled') 同为 bootstrap 决策
5. essay_versions 不可变无 DB 触发器（见 §2.2）
6. ERD §15.6 的 Token 历史保留窗口清理、作文永久删除清理流程未实现

---

## 4. API 状态

**契约 87 个操作，已实现 15 个，全部与契约路径/方法一致，无契约外接口**（实测比对：契约 paths vs FastAPI 生成的 OpenAPI）。

已实现：health GET；auth register/login/refresh/logout/logout-all/sessions GET/sessions DELETE；users/me GET/PATCH；essays POST/GET、essays/{id} GET/PATCH/DELETE。

### OpenAPI 与 FastAPI 的差异（均为已报告的决策，非擅自变更）

1. 契约对 auth/essay **响应体只有描述无 Schema** → 实现按 API Spec §3.2 示例（auth）与 §2 信封+ERD 字段（essay：列表 `{items,next_cursor,limit}`，详情含 `working_document` 摘要）——**形状待用户确认**
2. register 409 `RESOURCE_ALREADY_EXISTS`：已获批准补入契约（基线提交内），有回归测试
3. PATCH /users/me：契约是开放对象，实现为**显式字段白名单**（更严格，未知字段 422）
4. PATCH /essays/{id}：仅接受 title
5. Idempotency-Key：接受但去重未实现（预留）
6. 契约 `info.version` 保持 1.1.1；YAML 锚点/别名仍在（类型生成前需解析）

### 未完成的 API Contract 工作

- 后续切片若需新增/调整契约：**先说明原因获批准**，只增不改已批准业务语义
- 前端类型生成管线未建（契约锚点问题）

---

## 5. 测试状态（2026-11-14 实际运行结果）

| 套件 | 命令（目录） | 结果 |
|---|---|---|
| 后端全量 | `pytest`（backend/，venv） | **94 passed**（health 3、contract 5、CORS 10、compose 1、alembic URL 1、health 集成 2、迁移 downgrade 1、auth 55、essays 16），约 8s |
| 后端 lint/格式 | `ruff check .` / `ruff format --check .` | 全部通过（65 文件） |
| 前端类型 | `npx tsc --noEmit`（frontend/） | 通过 |
| 前端 lint | `npm run lint` | 通过 |
| 前端构建 | `npm run build` | 通过（9 路由；/essays/[id] 为 Partial Prerender） |
| E2E | `npx playwright test`（frontend/） | **18 passed**（auth 11 + essays 7），43.8s，Edge 通道 |

覆盖要点：认证全场景（含并发刷新单飞计数=1、重用撤销、Cookie 属性与 JS 不可见）；Essay 原子性/回滚/分页/隔离/软删除/非法 question_id/同 Essay 约束/快照不可变；前端加载态/空态/创建/改名/删除确认/详情导航/保护路由。

已知警告（不影响结果）：Starlette TestClient 建议 httpx2 的弃用提示；httpx 每请求 cookies 弃用提示；HS512 拒绝测试触发的 InsecureKeyLengthWarning（预期）。

**运行 E2E 的前置条件**：必须先暂停 :3500 dev server（Next 16 同目录单实例锁），Playwright 自管 :3600/:8001 隔离栈；跑完恢复。E2E 不触碰开发库。

---

## 6. 环境状态（不含任何凭据值）

| 项 | 值 |
|---|---|
| Node.js | **v22.23.5 便携版**，`.tools/node-v22.23.5-win-x64/`，**不在系统 PATH**；npm 10.9.9。每个新终端先：`set "PATH=D:\DOCUMENTS\Projects\ai-writing-coach\.tools\node-v22.23.5-win-x64;%PATH%"` |
| Python | **3.13.9**，venv `backend/.venv`（勿用 Anaconda base；勿用 `py` 默认 3.14） |
| Docker | client/server 29.9.2，Compose v5.6.1；Docker Desktop **由用户手动启动**；`awc-db` healthy |
| 端口 | 后端 **8000**；前端 **3500**（3000 落在 Windows Hyper-V/WinNAT 保留段 2955–3054，EACCES）；DB **5432**（仅 127.0.0.1）；E2E 专用 **8001/3600** |
| 测试库 | `ai_writing_coach_test`（自动创建/迁移） |
| 凭据 | 全部在 `.env`（gitignored）与 `frontend/.env.local`；模板见 `.env.example` / `frontend/.env.example`。**JWT_SECRET 当前为 dev 占位值，部署前必须更换**；本地 DB 密码为文档化的本地开发默认值 |
| 运行中进程 | uvicorn :8000（含 essays 模块）、next dev :3500、awc-db 容器 |

### 本机特殊配置 / 已知坑（重要）

1. **pip 全局镜像不可用**：安装必须 `--index-url https://pypi.org/simple`（不改全局配置）
2. **npm 极慢**：单包可达分钟级；安装放后台长任务，勿误判卡死重试
3. **Playwright CDN 停滞**：浏览器下载不动；E2E 配置用系统 Edge（`channel:"msedge"`，Chromium 内核）；恢复 bundled Chromium 的方法见 playwright.config.ts 注释
4. **IPv6 黑洞**：`localhost` 优先解析 `::1`；Docker 端口仅绑 IPv4 后 `::1` 连接被接受但无响应。**本地连接串一律用 127.0.0.1**；所有 DB 引擎带 connect_timeout
5. **Next 16 单 dev server 锁**：同目录不能同时跑两个 dev server（即使不同端口）
6. **Next 16 预渲染**：动态路由参数组件必须包在 `<Suspense>` 内（见 /essays/[id]）
7. **FastAPI 0.162**：`include_router` 产生 `_IncludedRouter` 包装，`app.routes` 不扁平；路由断言用 `app.openapi()`
8. **psycopg INET** 返回 ipaddress 对象，Pydantic str 字段需 before 校验器转换（已处理）
9. 禁止修改系统 PATH/WSL/Docker 配置/全局 Python（用户决策 D/E/F）

---

## 7. 产品设计决策（已确认，出处标注）

1. **两种写作模式**（System Design §10；API Spec §5）：辅助学习 assisted / 独立写作 independent。独立模式关闭：程序化实时检查、LLM 实时辅助、中文转英文、历史表达推荐、Ghost Text、实时段落分析；自动保存两者都开。考试条件（类型/Task/时间/字数）是独立模式的**配置**，不是第三种模式。**模式限制必须后端校验**，不能只靠前端隐藏控件。
2. **Inline-first 编辑器**（SD §1.1；AGENTS；API Spec §1）：纠错与表达建议出现在原文附近，**不设常驻右侧 AI 面板**；TipTap/ProseMirror；编辑器装饰不得进入持久化正文与字数。
3. **灰色简短提示 + 模糊答案**（SD §1.1 Progressive Teaching、§5.4；API Spec §6.2/§6.5）：默认只给简短提示；建议以 `display_text:"••••"`、`answer_revealed:false` 呈现，**未 Reveal 前完整 suggested_text 不得出现在响应/隐藏字段/HTML/日志**；Reveal 必须用户主动触发，查看答案≠接受。（灰色等视觉细节源自 PRD V1.1 DOCX 与交互决策，DOCX 无法文本扫描，实现时以 PRD 为准。）
4. **用户自主纠错 + 快捷键**（SD §5.6、§13.4）：用户**直接在原文修改**，不用独立输入框；验证走"规则优先、复杂按需 LLM"，**不得只比对唯一标准答案**，须考虑语境合法替代；正确→标记消失保留历史，错误→继续标红；原子事务（文档+Issue 状态+resolved revision+Edit Event），LLM 判断在事务外、提交前二次校验 base_revision，冲突 409 不部分提交。E2E 须覆盖快捷键冲突与中文输入法组合输入（具体快捷键定义在 PRD DOCX）。
5. **点击后基于当前句子的详细教学**（SD §5.5；API Spec §7；AGENTS）：**不建通用教学库**，不"先查模板"；提交错误 ID+当前句子+上下文+revision，LLM 针对当前句子生成；可含重复错误提醒与针对性练习；仅同用户/同 Issue/同 revision/同 context hash 可缓存，文本变化须重判；上下文过期 409 `STALE_AI_RESULT`。
6. **Rule-first / LLM-on-demand**（SD §5.3/§5.4；AGENTS）：先 LanguageTool+自定义规则（拼写/主谓一致/单复数/冠词/基础时态/标点）；确定性命中直接返回不调 LLM；仅复杂/不确定按需调 LLM；规则没命中≠句子正确。
7. **中文转英文**（SD §7；API Spec §8）：选中文短语+句子上下文，返回 2–4 候选；独立模式关闭。
8. **个人知识库**（SD §8；ERD §9；API Spec §9）：表达收集/归档/搜索；embedding 可重建、维度匹配 VECTOR(n)；**语义检索查询阶段限定当前用户**；提取候选先用户确认再保存。
9. **Previously Learned 表达推荐**（API Spec §8 `previously_learned`；SD §8）：润色时推荐历史学过的表达，**须先做语境适用性判断**，不盲目推送。
10. **重复语法错误提醒**（SD §5.5 第 5 步；ERD §10 user_weaknesses；API Spec §11）：结合历史错误画像判断是否指出重复问题；趋势须结合写作量/错误密度，不只比次数。
11. **IELTS 题库/评分/改写**（API Spec §12–13；ERD §11–12；SD）：只公开已授权内容；评分**必须绑定不可变 version_id**，202 队列化，AI 分数标记估分；改写接受用服务端完成结果（不接受客户端任意文本），单事务更新文档+ai_rewrite 快照+result_version_id+Edit Event，Original 不可覆盖。
12. **用户观点驱动的 Writing Planner**（SD §9.1）：用户输入题目**与观点** → Topic Analyzer → Argument Generator → Personal Expression Retrieval → Outline Generator → Quality Checker →（可循环调整）→ **等待用户确认** → 保存大纲。
13. **LangGraph 适用范围**（SD §9；AGENTS §3）：**仅**用于需要多步骤状态/条件分支/暂停恢复的流程：Writing Planner、Learning Extractor（提取先用户确认，保存由业务服务执行）、Personalized Study Planner（复习调度/任务数/掌握状态由确定性算法控制）。**不用**于：基础语法检查、简单 LLM 调用、中文翻译、表达润色、普通 RAG、作文 CRUD、复习时间计算、权限/订阅/支付。MVP 工作流轮询，后期按需 SSE。
14. 其他已确认：Document+Snapshot+Edit Events（不做完整 Event Sourcing）；自动保存不建快照；Original 永不被 AI 覆盖；LLM 成本全量记录（SD §12.4）；前端不直连 LLM Provider；权限/版本/调度等确定性业务逻辑不交给 Agent。

---

## 8. 下一步（最合理开发起点）

**推荐：Stage 2 Slice 2B — Working Document + 自动保存 + 快照/版本 API**

理由：Essay 骨架与认证已就绪，这是解锁 TipTap 编辑器切片的前置垂直切片，且完全落在已批准 ERD/API Spec 内：
- `GET/PUT /essays/{id}/working-document`（乐观并发 base_revision，冲突 409 `WORKING_DOCUMENT_CONFLICT`，revision 递增，不建快照）
- `POST /essays/{id}/snapshots`（只归档 source_server_revision 精确匹配的 Issue——Issue 表尚未建，本切片可先只做快照创建）、`GET versions`、`GET versions/{id}`、`POST restore`
- 迁移 0004（如需 essay_edit_events 则按 ERD §6.5；快照/版本表已存在，无需重建）
- 随后 Slice 2C：TipTap 编辑器 + 自动保存前端（unicode_codepoint ↔ ProseMirror 位置映射是 AGENTS 硬性不变量）

**开工前需用户拍板的事项**：
1. `essays.status` 取值集合（当前临时 CHECK）
2. essay 列表/详情响应形状确认（契约未定义，已按 API Spec 实现）
3. Idempotency-Key 去重是否本阶段实现
4. **Slice 2A 代码审查与提交**（当前全部未提交）
5. 将 `docs/README.md`、`docs/DEVELOPMENT_PLAN.md` 中"System Design MISSING"更新为已到位（新会话首批文档维护）

并行可选：LanguageTool 服务评估（SD §5.3，Grammar 切片前置）；LLM Provider 抽象与 prompt 版本管理设计（SD §7）。

---

## 9. 重要约束（继承自用户决策与 AGENTS.md）

- **审批门**：每个切片完成即停，报告后等用户确认再开下一阶段；**Git 提交必须用户明确批准**（当前 Slice 2A 未提交）
- 决策 A：仓库根仅 `ai-writing-coach/`，禁止父级 init；B：文档移动非复制、唯一 OpenAPI 源；C：Health 为纯新增；D：便携 Node，禁机器级安装/改 PATH/注册表；E：Docker Desktop 用户手动启动，禁改 Docker/WSL/系统配置；F：Python 3.13.9 venv，禁 Anaconda base；G：PRD 保留 DOCX
- 不修改已批准业务 API 语义；契约调整先说明原因获批
- 不引入 Redis/Celery/K8s/微服务/LangChain/LangGraph（后者仅 §7.13 场景且需 ADR）
- 用户数据严格按认证身份隔离；不信任客户端 user_id；未揭示答案不泄露；LLM 输出 Pydantic 校验+位置校验；不在长事务中调 LLM
- 测试要求：每个任务带测试、跑最窄相关套件+lint/类型检查、如实报告（不得以历史报告冒充当前结果）
- 本次盘点约束（对后续会话同样适用直至用户解除）：不随意清理/覆盖/丢弃现有修改与未跟踪文件

## 10. 关键命令速查

```bat
:: 环境（每个新终端）
set "PATH=D:\DOCUMENTS\Projects\ai-writing-coach\.tools\node-v22.23.5-win-x64;%PATH%"

:: 基础设施（仓库根）
docker compose up -d db
docker compose ps

:: 后端（backend/）
.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -e ".[dev]"
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
.venv\Scripts\pytest.exe
.venv\Scripts\ruff.exe check . && .venv\Scripts\ruff.exe format --check .

:: 前端（frontend/）
npm install
npm run dev            :: :3500
npx tsc --noEmit && npm run lint && npm run build
npx playwright test    :: 先暂停 :3500 dev server（Next 16 单实例锁）
```

环境变量模板：`.env.example`（根）、`frontend/.env.example`；真实值在 gitignored 的 `.env` / `frontend/.env.local`。

---

**完整性自检**：本文件覆盖 Git（分支/提交/未提交/未跟踪）、功能四级分类、数据库（head/迁移/实体/ERD 差异/未决约束）、API（15/87 实现清单+契约差异）、当日实测结果、环境（版本/端口/测试库/特殊配置，无凭据）、13+1 项产品设计决策（含出处）、下一步与待批事项、继承约束。新会话读取 AGENTS.md + docs/ 设计文档 + 本文件即可继续开发。