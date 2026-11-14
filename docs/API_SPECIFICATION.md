# AI Writing Coach — API Specification V1.1

**状态：** Final Development Baseline  
**依据：** PRD V1.1、System Design V1.1、Database ERD V1.2  
**后端：** FastAPI + Python | **API：** RESTful | **Prefix：** `/api/v1` | **契约：** OpenAPI 3.1  
**修订：** V1.1.1 — 新增基础设施健康检查 `GET /api/v1/health`（见 §23）与错误代码 `DATABASE_UNAVAILABLE`。已批准业务接口语义未改动。对应契约 `contracts/openapi.yaml` `info.version: 1.1.1`。

## 1. 核心原则

1. Inline-first；不设常驻右侧 AI 面板。
2. Rule-first；基础语法先执行程序化检查。
3. LLM-on-demand；复杂判断或用户主动请求教学时才调用。
4. 默认简短提示，点击后结合当前句子生成详细教学。
5. AI 建议不自动覆盖正文。
6. 自动保存更新 Working Document，不创建快照。
7. Essay Version 不可变；Original Snapshot 不可覆盖。
8. 实时 Issue 绑定 `source_server_revision`，`essay_version_id` 可空。
9. 评分必须绑定不可变 `version_id`。
10. 自主纠错保存、验证、Issue 状态和 Edit Event 是一个原子化业务操作。
11. 外部 LLM 调用不在持有数据库行锁的长事务中执行。
12. 前端不直接调用模型 Provider，不接触 LangGraph 内部 State。

## 2. 通用规范

- UUID 主键；JSON；snake_case；UTC ISO 8601。
- 成功响应：`{"data":...,"meta":{"request_id":"..."}}`。
- 错误响应：`{"error":{"code":"...","message":"...","details":[]},"meta":{"request_id":"..."}}`。
- 状态码：200、201、202、204、400、401、403、404、409、422、429、500、502、503、504。
- Cursor Pagination：`limit`、`cursor`。
- 重要写操作支持 `Idempotency-Key`。
- 文本位置统一为 `unicode_codepoint`；前端转换 ProseMirror Position。

## 3. 认证与用户 API

### 3.1 认证机制

Access Token 是建议 15 分钟有效的 JWT，前端仅保存在内存。Refresh Token 是高熵不透明令牌，通过 HttpOnly + Secure Cookie 发送，服务端只保存哈希。

`auth_sessions` 表示稳定设备 Session；`auth_refresh_tokens` 表示每次轮换的 Token 记录。刷新在事务中消费旧 Token 并创建新 Token，不创建新设备 Session。检测到旧 Token 重用时撤销 Token Family，并按策略撤销 Session。Cookie 端点实施 CSRF 防护；前端使用 single-flight refresh。SameSite、Domain、Path 和 CORS 根据部署域名确定。

### 3.2 接口清单

| Method | Endpoint | 功能 |
|---|---|---|
| POST | `/auth/register` | 注册 |
| POST | `/auth/login` | 登录 |
| POST | `/auth/refresh` | 轮换 Refresh Token |
| POST | `/auth/logout` | 登出当前设备 |
| POST | `/auth/logout-all` | 全设备登出 |
| GET | `/auth/sessions` | 设备会话列表 |
| DELETE | `/auth/sessions/{session_id}` | 撤销设备 Session |
| GET/PATCH | `/users/me` | 获取/修改资料 |
| GET/PATCH | `/users/me/preferences` | 获取/修改偏好 |

注册/登录 Request：

```json
{"email":"user@example.com","password":"SecurePassword123","display_name":"Alex"}
```

响应：

```json
{
  "data": {
    "access_token":"<jwt>",
    "token_type":"bearer",
    "expires_in":900,
    "user":{"id":"user_uuid","email":"user@example.com","display_name":"Alex"}
  }
}
```

Refresh Token 仅通过 Set-Cookie 返回。密码使用 Argon2id 等安全哈希，不存明文。

## 4. 作文管理与版本 API

| Method | Endpoint | 功能 |
|---|---|---|
| POST | `/essays` | 创建作文 |
| GET | `/essays` | 作文列表 |
| GET/PATCH/DELETE | `/essays/{essay_id}` | 详情/元数据/软删除 |
| GET | `/essays/{essay_id}/working-document` | 获取当前工作文档 |
| PUT | `/essays/{essay_id}/working-document` | 自动保存 |
| POST | `/essays/{essay_id}/snapshots` | 创建重要快照 |
| GET | `/essays/{essay_id}/versions` | 版本列表 |
| GET | `/essays/{essay_id}/versions/{version_id}` | 版本详情 |
| POST | `/essays/{essay_id}/restore` | 恢复快照 |

### 4.1 创建作文

`POST /essays`

```json
{"title":"Education and University Majors","writing_type":"ielts_task2","question_id":null}
```

在一个事务中创建 Essay、Working Document、Original Snapshot。

### 4.2 自动保存

`PUT /essays/{essay_id}/working-document`

```json
{
  "base_revision":18,
  "client_revision":26,
  "content_json":{"type":"doc","content":[]},
  "plain_text":"I believe students should choose...",
  "word_count":160
}
```

成功响应：

```json
{"data":{"essay_id":"essay_uuid","server_revision":19,"client_revision":26,"saved":true,"saved_at":"2026-11-14T03:05:00Z"}}
```

`base_revision` 必须匹配当前服务端 revision；成功后 `server_revision` 递增。`client_revision` 只是客户端编辑序号。自动保存不创建快照。服务端从 TipTap JSON 生成或校验纯文本和字数。建议 Debounce 1–2 秒。冲突返回 `409 WORKING_DOCUMENT_CONFLICT`，不得静默覆盖。

### 4.3 创建快照

`POST /essays/{essay_id}/snapshots`

```json
{"source_revision":19,"version_type":"checkpoint","label":"Before AI-assisted revision"}
```

类型：`original`、`checkpoint`、`assisted`、`ai_rewrite`、`final`。只将 `source_server_revision` 与 `source_revision` 完全匹配的 Issue 归档关联到该快照；不匹配的 Issue 不得被错误关联。

### 4.4 恢复快照

`POST /essays/{essay_id}/restore`

```json
{"version_id":"version_uuid","base_revision":19}
```

复制快照到 Working Document，递增 revision 并记录 Edit Event；源快照不变。

## 5. 写作会话 API

| Method | Endpoint | 功能 |
|---|---|---|
| POST/GET | `/essays/{essay_id}/sessions` | 创建/列出会话 |
| GET/PATCH | `/writing-sessions/{session_id}` | 查询/更新会话 |
| POST | `/writing-sessions/{session_id}/submit` | 提交作文 |

辅助模式：`{"mode":"assisted","activity_type":"practice","exam_config":null}`。

独立考试示例：

```json
{"mode":"independent","activity_type":"mock_exam","exam_config":{"exam_type":"IELTS","task_type":"task2","duration_minutes":40,"word_limit":250}}
```

后端根据 mode 决定 enabled_features；独立模式关闭实时辅助。

提交：

`POST /writing-sessions/{session_id}/submit`

```json
{"expected_server_revision":20}
```

在一个事务中校验 revision、创建 Final Snapshot、更新 Essay 指针、更新 Session 状态并记录事件。无辅助修改且 Original/Final 内容相同，可共用同一快照。

## 6. 语法检查与自主纠错 API

### 6.1 接口

| Method | Endpoint | 功能 |
|---|---|---|
| POST | `/essays/{essay_id}/grammar-check` | 检查当前文本 |
| GET | `/essays/{essay_id}/issues` | Issue 列表 |
| GET | `/essays/{essay_id}/issues/{issue_id}` | Issue 详情 |
| POST | `/essays/{essay_id}/issues/validate` | 保存修改并验证 |
| PATCH | `/essays/{essay_id}/issues/{issue_id}` | 忽略 Issue |
| POST | `/essays/{essay_id}/issues/{issue_id}/reveal` | 显示答案 |
| POST | `/essays/{essay_id}/issues/{issue_id}/teaching` | 详细教学 |

### 6.2 Grammar Check

`POST /essays/{essay_id}/grammar-check`

```json
{
  "session_id":"session_uuid",
  "server_revision":19,
  "client_revision":26,
  "text":"He go to school yesterday.",
  "text_range":{"start":0,"end":27,"offset_unit":"unicode_codepoint"},
  "context":{"previous_sentence":null,"next_sentence":null,"paragraph_text":"He go to school yesterday."}
}
```

后端验证用户、Essay、Session、模式和 revision；执行 LanguageTool + 自定义规则。无规则命中不调用 LLM；确定性错误用规则模板生成短提示；复杂或不确定问题按需调用 LLM。Issue 保存 `source_server_revision`，`essay_version_id` 初始可空。

响应：

```json
{
  "data":{
    "server_revision":19,
    "client_revision":26,
    "check_status":"completed",
    "issues":[{
      "id":"issue_uuid",
      "category":"grammar",
      "sub_category":"verb_tense",
      "source":"rule_engine",
      "severity":"high",
      "source_server_revision":19,
      "essay_version_id":null,
      "start_offset":3,
      "end_offset":5,
      "offset_unit":"unicode_codepoint",
      "anchor_text":"go",
      "short_explanation":"yesterday 表示过去时间，动词需要使用过去式。",
      "suggestions":[{"id":"suggestion_uuid","display_text":"••••","answer_revealed":false}],
      "status":"detected"
    }]
  }
}
```

未 Reveal 前，完整 `suggested_text` 不得出现在响应、隐藏字段、HTML 或浏览器可读取载荷中。

### 6.3 Issue 生命周期

实时 Issue 绑定来源 revision。Working Document 更新后，旧 Issue 保留历史，但只对来源 revision 有效。前端不能可靠映射时隐藏旧标记并重新检查。创建快照时只归档 revision 精确匹配的 Issue。

### 6.4 自主纠错原子操作

`POST /essays/{essay_id}/issues/validate`

```json
{
  "issue_id":"issue_uuid",
  "base_revision":19,
  "client_revision":27,
  "content_json":{"type":"doc","content":[]},
  "plain_text":"He went to school yesterday.",
  "word_count":6,
  "modified_range":{"start":3,"end":7,"offset_unit":"unicode_codepoint"}
}
```

流程：

1. 初步验证资源归属、Issue 和 base_revision。
2. 确定性规则先验证；必要的 LLM 判断在数据库事务外执行。
3. 开启短事务，再次验证 base_revision 未变化。
4. 更新 Working Document 并递增 revision。
5. 更新 Issue 状态及 resolved revision。
6. 创建含 from/to revision 的 Edit Event。
7. 提交事务。

状态：`correct`、`incorrect`、`needs_review`。若 LLM 判断期间 revision 变化，返回 409，不提交过期结果。不能只比较唯一标准答案，必须考虑语境中的合法替代表达。

### 6.5 Reveal 与 Ignore

Reveal：`POST /essays/{essay_id}/issues/{issue_id}/reveal`。仅用户主动请求后返回完整建议；查看答案不等于接受。

Ignore：`PATCH /essays/{essay_id}/issues/{issue_id}`，Request `{"status":"ignored"}`。忽略不删除历史记录。

## 7. 详细教学 API

不建立通用详细教学内容库。

`POST /essays/{essay_id}/issues/{issue_id}/teaching`

```json
{
  "server_revision":20,
  "client_revision":27,
  "current_sentence":"He goed to school yesterday.",
  "paragraph_context":"He goed to school yesterday. He wants to study engineering.",
  "user_current_text":"He goed to school yesterday."
}
```

后端验证 Issue 来源 revision。若上下文与来源 revision 不一致且无法可靠确认，返回 `409 STALE_AI_RESULT`。LLM 结合当前句子、段落、错误、用户修改及可验证历史画像生成讲解。教学记录保存来源 revision、context hash 和上下文快照；如已归档，同时记录 version ID。无历史依据时 personalized note 为 null。

## 8. 表达润色与中文翻译 API

| Method | Endpoint | 功能 |
|---|---|---|
| POST | `/essays/{essay_id}/expression-suggestions` | 表达润色 |
| POST | `/essays/{essay_id}/translations` | 中文转英文 |
| POST | `/essays/{essay_id}/expression-suggestions/{suggestion_id}/accept` | 接受建议 |

润色请求：

```json
{"server_revision":20,"client_revision":28,"selected_text":"get more experience","sentence":"I want to get more experience in this field.","paragraph_context":"I want to get more experience in this field because...","max_suggestions":3}
```

建议返回 text、meaning、usage、source、previously_learned、expression_id。历史表达须经过语境适用性判断。

翻译请求：

```json
{"server_revision":20,"client_revision":29,"chinese_text":"提高公众环保意识","sentence_context":"This policy can...","paragraph_context":"This policy can help people understand environmental issues."}
```

默认返回 2–4 个候选。

接受建议：

`POST /essays/{essay_id}/expression-suggestions/{suggestion_id}/accept`

```json
{
  "base_revision":20,
  "client_revision":30,
  "content_json":{"type":"doc","content":[]},
  "plain_text":"Updated essay text...",
  "word_count":160,
  "modified_range":{"start":10,"end":31,"offset_unit":"unicode_codepoint"}
}
```

服务端验证建议、归属、revision 和范围；在一个短事务中更新 Working Document、递增 revision、更新建议状态并创建 Edit Event。正式 accept 必须提交替换后的完整文档内容。

## 9. 个人表达知识库 API

| Method | Endpoint | 功能 |
|---|---|---|
| POST/GET | `/expressions` | 创建/列表 |
| GET/PATCH/DELETE | `/expressions/{expression_id}` | 详情/修改/删除 |
| POST | `/expressions/{expression_id}/archive` | 归档 |
| POST | `/essays/{essay_id}/expressions/extract` | 作文提取 |
| POST | `/expressions/search` | 关键词/语义搜索 |

创建表达：

```json
{"english_text":"gain hands-on experience","chinese_meaning":"获得实践经验","usage_context":"Career and education","topic":"Career","register":"formal","grammar_pattern":"Verb + adjective + noun"}
```

提取请求必须指定不可变 `version_id` 和 `extraction_scope`。候选先给用户确认，再保存。语义检索必须在查询阶段限制为当前用户数据。

## 10. 学习与复习 API

| Method | Endpoint | 功能 |
|---|---|---|
| GET | `/learning/reviews/due` | 待复习 |
| POST | `/learning/reviews` | 提交翻译练习 |
| GET | `/expressions/{expression_id}/progress` | 掌握进度 |
| GET | `/learning/summary` | 学习统计 |
| POST/GET | `/learning/plans` | 创建/列表 |
| GET | `/learning/tasks` | 任务列表 |
| PATCH | `/learning/tasks/{task_id}` | 更新任务 |

提交：

```json
{"expression_id":"expression_uuid","user_answer":"gain practical experience","exercise_mode":"translation"}
```

答案可由规则或 LLM 评价；复习间隔和掌握状态由后端确定性算法计算。

## 11. 错误画像 API

| Method | Endpoint | 功能 |
|---|---|---|
| GET | `/users/me/weaknesses` | 错误画像 |
| GET | `/users/me/weaknesses/{category}` | 类别详情 |
| GET | `/users/me/weaknesses/trends` | 趋势 |
| POST | `/users/me/weaknesses/practice` | 专项练习 |

趋势结合写作量和错误密度，不仅比较错误总数。

## 12. IELTS 题库 API

| Method | Endpoint | 功能 |
|---|---|---|
| GET | `/ielts/questions` | 题库 |
| GET | `/ielts/questions/{question_id}` | 题目 |
| GET | `/ielts/tags` | 标签 |
| GET | `/ielts/questions/random` | 随机题 |
| POST/DELETE | `/ielts/questions/{question_id}/favorite` | 收藏/取消 |

只返回已授权或允许公开的题目。收藏关系使用 `(user_id, question_id)` 联合主键。

## 13. 作文评分与改写 API

评分：

| Method | Endpoint | 功能 |
|---|---|---|
| POST | `/essays/{essay_id}/evaluations` | 创建评分 |
| GET | `/essays/{essay_id}/evaluations` | 评分历史 |
| GET/DELETE | `/evaluations/{evaluation_id}` | 查询/删除 |

创建评分：

```json
{"version_id":"version_uuid","evaluation_type":"ielts","task_type":"task2"}
```

必须绑定不可变 Version，返回 202 和 evaluation_id。状态 queued / processing / completed / failed / cancelled。Task 1 与 Task 2 使用不同 Schema；AI 分数明确标记为估分。

改写：

| Method | Endpoint | 功能 |
|---|---|---|
| POST | `/evaluations/{evaluation_id}/rewrite` | 创建改写 |
| GET | `/rewrites/{rewrite_id}` | 查询改写 |
| POST | `/rewrites/{rewrite_id}/accept` | 接受改写 |

创建改写 Request：`{"modification_level":"level_3"}`，level_1 至 level_4。

接受改写：

`POST /rewrites/{rewrite_id}/accept`

```json
{"base_revision":20,"client_revision":31}
```

服务端使用已完成 Rewrite 的结果，不接受客户端任意替换内容。在同一事务中验证归属、状态和 revision，更新 Working Document，创建 `ai_rewrite` EssayVersion，填写 `result_version_id`，创建 Edit Event。Original Snapshot 不变。

## 14. 写作大纲 API

| Method | Endpoint | 功能 |
|---|---|---|
| POST | `/essays/{essay_id}/outlines/generate` | 生成大纲 |
| GET | `/essays/{essay_id}/outlines` | 列表 |
| GET/PATCH | `/outlines/{outline_id}` | 详情/修改 |
| POST | `/outlines/{outline_id}/confirm` | 确认 |
| POST | `/outlines/{outline_id}/nodes` | 新增节点 |
| PATCH/DELETE | `/outlines/{outline_id}/nodes/{node_id}` | 修改/删除节点 |

Ghost Text 不写入正文，除非用户主动接受。

## 15. LangGraph 工作流 API

| Method | Endpoint | 功能 |
|---|---|---|
| POST | `/workflows` | 创建 |
| GET | `/workflows/{workflow_id}` | 状态 |
| POST | `/workflows/{workflow_id}/resume` | 恢复 |
| POST | `/workflows/{workflow_id}/cancel` | 取消 |
| GET | `/workflows/{workflow_id}/events` | 事件 |

类型：`writing_planner`、`learning_extractor`、`personalized_study_planner`。前端只提交 confirm / reject / revise / continue 等业务动作，不接触 LangGraph 内部状态。MVP 先轮询，后期按需 SSE。

## 16. AI 使用量 API

| Method | Endpoint | 功能 |
|---|---|---|
| GET | `/analytics/ai-usage` | 使用量 |
| GET | `/analytics/ai-usage/by-feature` | 功能统计 |
| GET | `/analytics/ai-usage/trends` | 成本趋势 |

用户只能查看自己的使用量；管理员统计需要独立权限。

## 17. 并发、文本位置与事务

- `server_revision` 是服务端工作文档修订号。
- `client_revision` 是客户端编辑序号。
- `version_no` 是不可变快照序号。
- Issue offset 只对其来源 revision 或归档快照有效。
- 前端通过 ProseMirror mapping 映射；不能可靠映射时丢弃旧结果并重新检查。
- API 使用 `unicode_codepoint`，前端负责 UTF-16 / ProseMirror 转换。
- 自动保存使用乐观并发控制。
- 自主纠错与接受改写使用短事务和二次 revision 校验。
- 外部 LLM 请求不在持有数据库锁的长事务内执行。

## 18. 安全与权限

1. 私有 API 默认要求认证。
2. 用户 ID 从认证上下文获取。
3. 每次访问 Essay、Version、Issue、Expression、Evaluation、Rewrite、Workflow 都校验归属。
4. pgvector 查询阶段限定当前用户。
5. Provider Key 只保存在服务端。
6. Cookie 认证端点实施 CSRF 防护。
7. AI 输出通过 Pydantic 校验。
8. 模型输出位置和 revision 二次验证。
9. LLM 不决定权限或直接执行任意数据库写入。
10. 未揭示答案不出现在初始响应。
11. 日志不记录不必要的作文全文。

## 19. 统一错误代码

| Code | 含义 |
|---|---|
| `AUTHENTICATION_REQUIRED` | 需要登录 |
| `INVALID_CREDENTIALS` | 登录信息错误 |
| `TOKEN_EXPIRED` | Access Token 过期 |
| `REFRESH_TOKEN_REVOKED` | Refresh Token 已撤销 |
| `REFRESH_TOKEN_REUSE_DETECTED` | 已轮换 Token 被重用 |
| `RESOURCE_NOT_FOUND` | 资源不存在 |
| `RESOURCE_ACCESS_DENIED` | 无权访问 |
| `VALIDATION_ERROR` | 参数错误 |
| `WORKING_DOCUMENT_CONFLICT` | 工作文档 revision 冲突 |
| `DOCUMENT_VERSION_CONFLICT` | 快照冲突 |
| `STALE_AI_RESULT` | AI 结果过期 |
| `GRAMMAR_SERVICE_UNAVAILABLE` | 语法服务不可用 |
| `LLM_PROVIDER_ERROR` | 模型服务异常 |
| `LLM_TIMEOUT` | 模型超时 |
| `RATE_LIMIT_EXCEEDED` | 请求超限 |
| `WORKFLOW_INVALID_STATE` | 工作流状态不允许 |
| `RESOURCE_ALREADY_EXISTS` | 资源重复 |
| `DATABASE_UNAVAILABLE` | 数据库不可用（健康检查返回 503） |

## 20. 前后端职责映射

| 前端 | API/后端 |
|---|---|
| TipTap Editor | Working Document |
| Grammar Decorations | Grammar Check |
| Inline Feedback | Grammar Check Response |
| 自主纠错 | Issues Validate |
| 答案揭示 | Reveal |
| 教学浮层 | Contextual Teaching |
| 表达推荐 | Expression Suggestions |
| 中文转英文 | Translations |
| 大纲 | Outlines |
| 知识库 | Expressions |
| 复习 | Learning Reviews |
| 作文报告 | Evaluations |
| 历史记录 | Essay Versions |

## 21. MVP 实施优先级

- **Phase 1：** Auth、User、Essay CRUD、Working Document、Snapshot、Writing Session、Grammar、Issue Validation、Reveal、Teaching。
- **Phase 2：** Expression Suggestions、Translation、Evaluation、Rewrite、Expression Extraction。
- **Phase 3：** Knowledge Base、Semantic Search、Review、Weakness、Learning Summary。
- **Phase 4：** IELTS、Outline、LangGraph、Learning Plans、AI Usage Analytics。

## 22. 验收标准

- Refresh Token 轮换不创建新设备 Session。
- 自动保存不创建快照。
- 实时 Issue 绑定 revision，不依赖快照。
- 快照只归档来源 revision 精确匹配的 Issue。
- Issue 位置不错误套用到新 revision。
- 自主纠错原子化保存正文、Issue 状态和 Edit Event。
- 外部 LLM 不在长事务中执行。
- 初始检查响应不泄露答案。
- 详细教学结合当前句子和上下文。
- Evaluation 绑定不可变 Version。
- Rewrite 接受创建新快照且不覆盖 Original。
- 私人 RAG 数据严格隔离。
- OpenAPI 与 Pydantic Schema 一致。
- 核心接口有单元、集成和 E2E 测试。

## 23. 基础设施健康检查 API

本节为 V1.1.1 附加内容，属于运维接口，不属于产品功能，不影响任何已批准业务接口语义。

| Method | Endpoint | 功能 |
|---|---|---|
| GET | `/health` | 服务与 PostgreSQL 连通性检查 |

完整路径：`GET /api/v1/health`。

### 23.1 语义

- 无需认证。契约中该操作使用 `security: []` 覆盖全局 `bearerAuth`。
- 服务端对 PostgreSQL 执行真实连通性探测（例如 `SELECT 1`），不返回假状态。
- **200**：服务正常且数据库可达。
- **503**：服务进程存活但数据库不可达；不得返回 `"connected"`。
- 探测失败不抛出未处理异常，统一返回错误封装。

### 23.2 数据库可用（200）

```json
{
  "data": {
    "status": "ok",
    "database": "connected"
  },
  "meta": {
    "request_id": "req_uuid"
  }
}
```

对应契约 Schema：`HealthResponse`。`status` 固定为 `ok`，`database` 固定为 `connected`。

### 23.3 数据库不可用（503）

```json
{
  "error": {
    "code": "DATABASE_UNAVAILABLE",
    "message": "Database is not reachable."
  },
  "meta": {
    "request_id": "req_uuid"
  }
}
```

对应契约 Schema：`ErrorResponse`。

### 23.4 范围限制

健康检查只报告服务与数据库状态，不检查 LanguageTool、LLM Provider、Redis 或队列，也不返回版本号之外的部署细节、连接串或凭据。

**文档结束 — API Specification V1.1（修订 V1.1.1：新增 §23 Health API 与 `DATABASE_UNAVAILABLE`）**
