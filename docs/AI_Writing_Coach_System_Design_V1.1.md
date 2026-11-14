# AI Writing Coach --- System Design

**文档版本：** V1.1\
**依据：** PRD V1.1 与已确认的 Writing Editor 交互决策\
**状态：** System Design 基线，供后续 ERD、API Specification
与开发计划使用\
**技术路线：** Next.js + TypeScript / Python + FastAPI / PostgreSQL +
pgvector

------------------------------------------------------------------------

## 1. 文档目的与范围

本文定义 AI Writing Coach 的系统架构、模块边界、核心数据流、AI
服务调用策略、运行部署方式、安全与测试原则。

本文件是系统设计文档，不是数据库字段清单或 API
逐项定义。数据库实体、字段、主外键和索引将在 ERD
阶段确定；请求与响应结构、路径、状态码将在 API Specification 阶段确定。

### 1.1 产品核心原则

1.  **Inline-first：** 纠错与表达建议直接出现在原文附近，不设置常驻右侧
    AI 反馈栏。
2.  **Rule-first：** 先执行程序化语言检查。
3.  **LLM-on-demand：** 只有需要上下文判断、复杂分析或个性化教学时才调用
    LLM。
4.  **Progressive Teaching：**
    默认展示简短错误提示；用户主动点击后，结合其具体句子进行详细讲解。
5.  **User-in-control：** AI 建议不自动覆盖正文，用户决定是否接受。
6.  **Data Integrity：**
    原始写作快照、建议、修改事件和最终版本分别管理。
7.  **Modular Monolith：** 初期采用模块化单体，避免过早引入微服务。
8.  **Contract-first：** 前后端通过稳定的 API 契约协作。
9.  **Deterministic Business Logic：**
    权限、版本、复习调度、考试规则等由普通业务代码控制，不交给 Agent
    自主决定。

### 1.2 明确不采用的设计

-   不建立可复用的通用详细教学内容库。
-   不在用户点击错误时优先查找预先生成的教学答案。
-   不让 LLM 直接修改或覆盖用户作文。
-   不让所有简单功能都经过 LangGraph。
-   不在 MVP 阶段拆分微服务。
-   不在前端直接调用 LLM Provider。

------------------------------------------------------------------------

## 2. 总体架构

### 2.1 High-level Architecture

``` mermaid
flowchart TB
    U[用户浏览器]
    FE[Next.js + TypeScript<br/>TipTap Editor]
    API[FastAPI Application<br/>业务 API 与权限控制]

    subgraph APP[模块化单体应用]
      AUTH[Auth / User]
      ESSAY[Essay / Version]
      GRAMMAR[Grammar / Feedback]
      EXPR[Expression / Knowledge]
      LEARN[Learning]
      IELTS[IELTS / Assessment]
      WORKFLOW[LangGraph Workflows]
      LLM[LLM Service Layer]
      RULE[Rule-based Checking Adapter]
    end

    subgraph DATA[数据与基础设施]
      PG[(PostgreSQL)]
      VEC[(pgvector)]
      REDIS[(Redis - 按需)]
      LT[LanguageTool Server]
    end

    PROVIDER[External LLM / Embedding APIs]

    U --> FE
    FE <-->|HTTPS REST / SSE| API
    API --> AUTH
    API --> ESSAY
    API --> GRAMMAR
    API --> EXPR
    API --> LEARN
    API --> IELTS
    API --> WORKFLOW

    GRAMMAR --> RULE
    RULE --> LT
    GRAMMAR --> LLM
    EXPR --> LLM
    IELTS --> LLM
    WORKFLOW --> LLM
    LLM --> PROVIDER

    AUTH --> PG
    ESSAY --> PG
    GRAMMAR --> PG
    EXPR --> PG
    LEARN --> PG
    IELTS --> PG
    EXPR --> VEC
    WORKFLOW --> PG
    API -.缓存/队列.-> REDIS
```

### 2.2 分层职责

  --------------------------------------------------------------------------------------------
  层                      技术                          职责
  ----------------------- ----------------------------- --------------------------------------
  Presentation            Next.js、TypeScript、TipTap   页面、编辑器、交互状态、呈现 AI 反馈

  Application API         FastAPI、Pydantic             身份验证、权限、请求校验、业务编排

  Domain Services         Python modules                作文、语法、表达、学习、雅思业务规则

  AI Services             Provider                      模型调用、结构化输出、Embedding、RAG
                          SDK、LangChain（按需）

  Workflow                LangGraph（按需）             多步骤、有状态、需人工确认的 AI 流程

  Persistence             PostgreSQL、pgvector          业务数据、版本、学习数据、向量

  Infrastructure          Docker、Redis（按需）         开发部署、缓存、异步任务
  --------------------------------------------------------------------------------------------

### 2.3 技术选型

  领域             推荐技术                         使用边界
  ---------------- -------------------------------- ------------------------------
  前端框架         Next.js + TypeScript             Web UI
  UI 样式          Tailwind CSS                     设计系统与响应式布局
  富文本编辑器     TipTap / ProseMirror             文档编辑、选区、文档位置映射
  服务端数据状态   TanStack Query                   API 请求、缓存、失效
  UI 状态          Zustand（按需）                  面板、弹层、模式等跨组件状态
  后端             Python + FastAPI                 主业务 API
  数据校验         Pydantic                         API 与 AI 输出结构校验
  ORM              SQLAlchemy 2.x                   数据访问
  数据迁移         Alembic                          Schema 版本管理
  数据库           PostgreSQL                       关系数据
  向量检索         pgvector                         个人表达语义检索
  规则检查         LanguageTool + 自定义规则        基础语言问题筛查
  LLM 集成         Provider SDK；必要时 LangChain   模型调用和组件集成
  Agent 工作流     LangGraph（按需）                复杂、有状态工作流
  缓存/队列        Redis（按需）                    缓存、限流辅助、后台任务
  测试             Pytest、Playwright               后端测试与端到端测试
  监控             结构化日志、Langfuse（按需）     错误、延迟、Token、成本
  部署             Docker Compose 起步              本地与初期部署

**重要：** 架构允许 Redis、LangGraph、Langfuse 后续加入，不代表 MVP
第一阶段必须部署它们。

------------------------------------------------------------------------

## 3. 前端架构

### 3.1 页面与功能模块

-   Dashboard
-   Writing Editor
-   IELTS Practice
-   Knowledge Base
-   Learning Center
-   Writing History
-   Settings

### 3.2 Writing Editor 组件职责

  组件                     职责
  ------------------------ ----------------------------------
  Editor Canvas            文本输入、选区、光标、撤销重做
  Outline                  左侧可折叠写作大纲
  Grammar Decorations      错误范围标记
  Inline Feedback          原文下方简短错误提示
  Teaching Popover         点击后显示结合当前句子的详细教学
  Expression Suggestions   原文附近显示多个可选表达
  Ghost Text               根据确认的大纲显示思路或表达提示
  Mode Controller          辅助学习/独立写作模式
  Save Status              自动保存状态和冲突提示

不设置常驻右侧 AI
纠错栏。用户点击错误、表达或学习入口时，才在对应文本附近显示上下文浮层；窄屏设备可使用底部弹层。

### 3.3 前端状态职责边界

-   TipTap/ProseMirror：正文文档、光标、选区、文档事务和位置映射。
-   Decorations：标记错误与建议范围；不把提示文本写入作文正文。
-   Inline Widgets：渲染原文附近的轻量反馈。
-   TanStack Query：服务端数据获取、缓存、重新验证。
-   Zustand：跨组件 UI 状态，例如当前打开的教学卡片、模式、侧栏状态。
-   API Client：统一处理认证、请求、错误和响应类型。

不要把所有编辑器、AI 请求和反馈状态写进一个巨大的 Editor 组件。

### 3.4 文本位置与版本

每次检查请求必须携带文档版本标识及被检查文本的上下文。后端返回的文本范围必须能映射回请求时的文本版本。

前端收到响应后：

1.  检查响应版本是否仍然有效。
2.  若用户已经继续编辑，使用 ProseMirror transaction mapping
    尝试映射范围。
3.  无法可靠映射时丢弃旧结果并重新检查。
4.  不允许旧响应覆盖新文本。
5.  统一定义文本偏移编码，避免 Python 与 JavaScript 对 Unicode、emoji 和
    UTF-16 索引处理不同导致错位。

------------------------------------------------------------------------

## 4. 后端架构

### 4.1 架构模式

采用 **Modular Monolith（模块化单体）**：

-   一个 FastAPI 应用。
-   一个主 PostgreSQL 数据库。
-   业务模块按领域划分。
-   AI 服务作为内部模块。
-   需要后台执行时再增加 Worker。
-   初期不拆成多个独立微服务。

### 4.2 业务模块

  模块               职责
  ------------------ ---------------------------------
  Auth               注册、登录、会话和权限
  Users              用户资料、偏好和目标
  Essays             作文 CRUD、快照、版本和修改事件
  Writing Sessions   写作模式、考试条件和会话状态
  Grammar            程序化检查、错误分类、验证
  Feedback           错误提示、建议、接受/忽略状态
  Expressions        表达内容、用户收藏和来源
  Knowledge          Embedding、检索和 RAG
  Learning           复习记录、掌握状态、调度
  IELTS              题库、考试配置、评分结果
  Workflows          LangGraph 工作流入口与状态协调
  Analytics          学习统计、AI 使用量和成本

### 4.3 推荐目录结构

``` text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── api/
│   │   ├── router.py
│   │   └── dependencies.py
│   ├── modules/
│   │   ├── auth/
│   │   ├── users/
│   │   ├── essays/
│   │   ├── writing_sessions/
│   │   ├── grammar/
│   │   ├── feedback/
│   │   ├── expressions/
│   │   ├── knowledge/
│   │   ├── learning/
│   │   ├── ielts/
│   │   └── analytics/
│   ├── ai/
│   │   ├── providers/
│   │   ├── prompts/
│   │   ├── schemas/
│   │   ├── llm/
│   │   ├── embeddings/
│   │   ├── rag/
│   │   ├── tools/
│   │   └── workflows/
│   ├── infrastructure/
│   │   ├── database/
│   │   ├── language_tool/
│   │   ├── cache/
│   │   └── queue/
│   └── workers/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evaluation/
├── alembic/
├── pyproject.toml
└── Dockerfile
```

------------------------------------------------------------------------

## 5. 核心子系统一：Rule-first 语法检查

### 5.1 设计目标

程序化检查优先识别基础、明确的语言错误。只有当问题需要上下文判断、规则引擎无法可靠处理，或用户请求进一步解释时，才调用
LLM。

这里必须区分两件事：

-   **发现错误：** 由规则引擎先执行。
-   **深入教学：** 用户点击后，结合当前句子和必要上下文生成解释。

### 5.2 语法检查流程

``` mermaid
flowchart TD
    A["用户编辑文本"] --> B["Debounce / 文本边界检测"]
    B --> C["FastAPI Grammar API"]
    C --> D["LanguageTool + 自定义规则"]
    D --> E{"是否发现问题？"}
    E -->|"否"| F["返回无规则命中结果"]
    E -->|"是"| G["规则分类与可靠性判断"]
    G --> H{"是否能确定并生成简短反馈？"}
    H -->|"是"| I["规则模板生成短提示"]
    H -->|"否"| J["按需调用 LLM 判断"]
    J --> K{"LLM 是否确认问题？"}
    K -->|"否"| L["过滤或作为可选建议"]
    K -->|"是"| M["生成简短反馈"]
    I --> N["统一 Feedback Schema"]
    L --> N
    M --> N
    F --> O["返回前端"]
    N --> O
    O --> P["原文标记 + 简短提示"]
```

### 5.3 程序化检查范围

初期评估 LanguageTool，并可结合自定义规则，优先处理：

-   拼写错误。
-   常见主谓一致问题。
-   常见名词单复数问题。
-   部分冠词错误。
-   部分基础时态问题。
-   标点与格式问题。
-   其他有可靠规则支持的语言问题。

规则引擎未发现问题，不代表句子完全正确。

### 5.4 是否调用 LLM 的判断

对于每个规则命中，按规则类型、可靠性和上下文需求进行分类：

**确定性较高：**

-   规则能明确定位错误。
-   推荐答案和解释可由规则元数据生成。
-   直接返回简短提示。
-   不调用 LLM。

**复杂或不确定：**

-   规则只发现可疑问题，无法确认。
-   需要理解上下文、语义或复杂语法。
-   按需调用 LLM 确认并生成简短反馈。

不能把所有规则命中无条件发送给 LLM，否则会失去 Rule-first 的成本优势。

### 5.5 详细教学：必须结合用户当前句子生成

**本系统不设置可复用的详细教学内容库，也不采用"点击后先查询通用教学模板"的流程。**

用户点击某条错误提示时：

1.  前端提交错误
    ID、当前句子、必要的前后文、错误类型、原始片段、用户当前修改和文档版本。
2.  FastAPI 验证用户权限、作文归属和版本有效性。
3.  Teaching Service 调用 LLM。
4.  LLM 根据用户的具体句子解释错误原因、正确规则及修改方式。
5.  结合用户历史错误画像，判断是否需要指出重复出现的问题。
6.  返回结构化教学内容。
7.  前端在原文附近展开浮动教学卡片。

详细教学可包含：

-   当前句子中具体哪里有问题。
-   为什么在这个语境下不合适。
-   推荐修改及其理由。
-   对应语法或表达规则。
-   两到三个贴合当前知识点的例句。
-   用户过去是否反复出现同类错误。
-   可选的针对性练习。

**禁止将通用教学模板作为详细解释的替代。**
可以缓存同一用户、同一错误和同一文档版本下已经生成的教学结果，以避免重复请求；文本或上下文变化后必须重新判断缓存是否有效。

### 5.6 自主纠错验证

用户直接在原文中修改，不使用独立输入框。

流程：

``` mermaid
sequenceDiagram
    actor User as 用户
    participant Editor as TipTap Editor
    participant API as FastAPI
    participant Rule as Rule Engine
    participant DB as PostgreSQL

    User->>Editor: 修改原文中的错误
    Editor->>Editor: 创建新文档事务
    Editor->>API: 提交待验证文本与版本
    API->>Rule: 验证修改后的句子
    Rule-->>API: 返回验证结果
    alt 可以可靠判断
        API->>DB: 更新错误状态和修改事件
        API-->>Editor: 返回正确/仍有错误
        Editor->>Editor: 正确则恢复黑色
    else 无法可靠判断
        API-->>Editor: 返回需要进一步判断
        Note over Editor,API: 按需调用 LLM 验证
    end
```

验证原则：

-   不允许只通过字符串是否等于一个标准答案来判断。
-   需要考虑同一语境下多个合法表达。
-   明确错误优先用规则验证。
-   复杂句子按需调用 LLM。
-   正确后隐藏当前错误标记，但保留历史错误记录。
-   错误仍存在时继续标红并给出简短提示。

------------------------------------------------------------------------

## 6. 核心子系统二：作文与版本管理

### 6.1 设计模式

采用：

**Document + Snapshot + Edit Events**

不引入完整 Event Sourcing 框架。

### 6.2 版本概念

  数据                含义                         处理原则
  ------------------- ---------------------------- ----------------
  Original Snapshot   未经 AI 辅助的基准文本快照   不被 AI 覆盖
  AI Suggestions      AI 提出的独立修改建议        保留建议及状态
  Assisted Version    用户接受部分建议后的文本     可产生新版本
  Final Version       用户最终保存或提交的版本     以新快照保存

辅助学习模式应在合适的基准时点保存未经 AI
修改的文本，并独立维护后续辅助版本。

独立写作模式应在提交时保存独立写作快照，作为能力评估依据。

### 6.3 修改事件

每次接受 AI 建议或进行重要修改时记录：

-   修改前文本或片段。
-   修改后文本或片段。
-   修改来源（用户手动、接受 AI 建议）。
-   修改类型。
-   对应建议 ID（如有）。
-   文档版本。
-   修改时间。

初期可采用定期快照 + 修改事件记录。无需把每一个击键都写入数据库。

### 6.4 版本流程

``` mermaid
flowchart TD
    A["创建作文 / 写作会话"] --> B["建立基准快照"]
    B --> C["用户编辑"]
    C --> D["规则检查 / AI 分析"]
    D --> E["产生 AI Suggestion"]
    E --> F{"用户操作"}
    F -->|"接受"| G["记录 AI Edit Event"]
    F -->|"拒绝 / 忽略"| H["记录建议状态"]
    F -->|"自行修改"| I["记录 User Edit"]
    G --> J["更新当前文档版本"]
    I --> J
    H --> C
    J --> K["保存新快照或版本"]
    K --> C
    C --> L["提交作文"]
    L --> M["保存 Final Snapshot"]
```

------------------------------------------------------------------------

## 7. 核心子系统三：LLM 服务层

### 7.1 统一模型调用接口

业务模块不直接绑定某个模型供应商 SDK。

``` mermaid
flowchart TB
    B["Grammar / Translation / IELTS / Teaching"]
    S["LLM Service Interface"]
    R["Model Routing / Config"]
    A["Provider A"]
    C["Provider B"]
    D["Provider C"]

    B --> S --> R
    R --> A
    R --> C
    R --> D
```

统一管理：

-   模型名称。
-   Prompt 版本。
-   输出 Schema。
-   Token 使用量。
-   请求耗时。
-   超时和重试。
-   调用成本。
-   成功与失败状态。

### 7.2 模型选择策略

  任务           策略
  -------------- ------------------------------
  基础语法       不使用 LLM
  复杂语法判断   按需使用模型
  详细教学       用户点击后调用，结合具体句子
  中文转英文     选择语言质量和延迟合适的模型
  表达润色       选择具备上下文理解能力的模型
  IELTS 评分     优先稳定性和一致性
  写作结构规划   需要较强分析能力的模型
  表达提取       结构化输出模型

具体模型应通过评测集比较后确定，不在系统设计阶段绑定某一家供应商。

### 7.3 Prompt 管理

Prompt 独立版本化管理，不散落在业务代码中。

``` text
backend/app/ai/prompts/
├── grammar/
│   └── deep_check_v1.txt
├── teaching/
│   └── contextual_explanation_v1.txt
├── expression/
│   ├── polish_v1.txt
│   └── translate_v1.txt
├── ielts/
│   └── evaluate_v1.txt
└── workflows/
    ├── writing_planner_v1.txt
    └── learning_extractor_v1.txt
```

教学 Prompt
必须要求模型基于用户提供的具体句子和上下文进行解释，不允许只返回脱离语境的通用语法定义。

------------------------------------------------------------------------

## 8. 核心子系统四：个人知识库与 RAG

### 8.1 数据存储分工

  数据           存储
  -------------- ------------
  英文表达       PostgreSQL
  中文含义       PostgreSQL
  话题和标签     PostgreSQL
  用户收藏状态   PostgreSQL
  掌握程度       PostgreSQL
  复习记录       PostgreSQL
  Embedding      pgvector

关系型数据负责业务管理，向量数据负责语义检索。

### 8.2 表达检索流程

``` mermaid
flowchart TD
    A["用户完成当前句子"] --> B["提取语义查询"]
    B --> C["生成 Query Embedding"]
    C --> D["pgvector 召回候选表达"]
    D --> E["按用户、状态、话题过滤"]
    E --> F["相关性排序"]
    F --> G["必要时判断上下文适用性"]
    G --> H["原文附近显示推荐"]
    H --> I["用户插入 / 忽略 / 收藏"]
```

### 8.3 推荐原则

优先级：

1.  当前语境高度匹配且用户已经学过的表达。
2.  当前语境匹配但尚未掌握的表达。
3.  AI 新生成的表达。
4.  更正式或更高级的可选表达。

初期使用向量召回、元数据过滤和相似度排序。后期根据评估结果再加入 Hybrid
Search 和 Reranking。

### 8.4 学习进度

掌握状态、复习时间、正确次数和复习间隔由普通 Python 业务逻辑维护。

Embedding 不代表掌握程度；被收藏也不代表学会。

------------------------------------------------------------------------

## 9. LangGraph 工作流

LangGraph 只用于确实需要多步骤状态管理、条件分支、暂停和恢复的流程。

### 9.1 Writing Planner

``` mermaid
flowchart TD
    A["用户输入题目与观点"] --> B["Topic Analyzer"]
    B --> C["Argument Generator"]
    C --> D["Personal Expression Retrieval"]
    D --> E["Outline Generator"]
    E --> F["Quality Checker"]
    F --> G{"是否需要调整？"}
    G -->|"是"| C
    G -->|"否"| H["等待用户确认"]
    H --> I["保存大纲"]
```

### 9.2 Learning Extractor

作文提交后，识别值得学习的表达，规范化、去重并生成学习元数据。提取结果先供用户确认，之后由业务服务执行保存。

### 9.3 Personalized Study Planner

结合用户错误画像、表达掌握状态和练习历史生成学习建议。复习调度、任务数量和掌握状态由确定性算法控制。

### 9.4 不使用 LangGraph 的功能

-   基础语法检查。
-   简单 LLM 调用。
-   中文翻译。
-   表达润色。
-   普通 RAG 检索。
-   作文 CRUD。
-   复习时间计算。
-   权限、订阅和支付逻辑。

------------------------------------------------------------------------

## 10. 写作模式

系统只有两种写作模式。

  能力               辅助学习模式   独立写作模式
  ------------------ -------------- --------------
  程序化实时检查     开启           关闭
  LLM 实时语言辅助   开启           关闭
  中文转英文         开启           关闭
  历史表达推荐       开启           关闭
  Ghost Text         开启           关闭
  实时段落分析       开启           关闭
  完成后 AI 批改     可选           可选/提交后
  计时               可选           可选
  自动保存           开启           开启

独立写作模式可配置自由写作或模拟考试条件，例如考试类型、Task、时间和字数要求。考试条件不是第三种写作模式。

模式限制必须由后端校验，不能只依赖前端隐藏控件。

------------------------------------------------------------------------

## 11. 数据与基础设施架构

### 11.1 初期开发环境

``` mermaid
flowchart TB
    subgraph LOCAL["Docker Compose / Local Development"]
      FE["Next.js<br/>localhost:3000"]
      API["FastAPI<br/>localhost:8000"]
      DB[("PostgreSQL + pgvector")]
      LT["LanguageTool Server"]
    end
    EXT["External LLM APIs"]

    FE <-->|HTTP| API
    API <--> DB
    API <-->|HTTP| LT
    API <-->|HTTPS| EXT
```

初期服务：

-   Next.js。
-   FastAPI。
-   PostgreSQL + pgvector。
-   LanguageTool Server。

Redis、Worker、Langfuse 按实际功能需要再加入。

### 11.2 后期生产部署

``` mermaid
flowchart TB
    U["Users"] --> EDGE["Domain / HTTPS"]
    EDGE --> FE["Frontend Hosting"]
    FE --> API["FastAPI Application"]
    API --> DB[("Managed PostgreSQL + pgvector")]
    API --> LT["LanguageTool Service"]
    API --> LLM["LLM Providers"]
    API -.-> REDIS["Redis"]
    REDIS -.-> WORKER["Background Worker"]
    API --> OBS["Logs / Monitoring"]
    WORKER --> OBS
```

初期选择一个主要部署区域，不提前构建多云或多区域微服务架构。面向中国大陆和新加坡用户时，后续根据访问延迟、模型服务可用性和数据合规要求决定部署区域。

------------------------------------------------------------------------

## 12. 安全与可靠性

### 12.1 用户数据隔离

-   所有私有数据查询都必须使用认证后的用户身份。
-   不信任前端传来的 user_id。
-   用户不能读取其他用户的作文、表达、复习记录和工作流状态。
-   对关键写入操作执行权限检查。

### 12.2 AI 安全

-   防范 Prompt Injection。
-   不将模型输出直接作为数据库写入指令。
-   所有结构化输出经过 Pydantic 校验。
-   校验文本位置和文档版本。
-   工具调用实施权限控制。
-   不允许 LLM 自行决定跨用户数据访问。

### 12.3 数据可靠性

-   自动保存。
-   失败重试。
-   版本快照。
-   修改事件记录。
-   幂等写入。
-   数据库备份。
-   用户数据删除流程。

### 12.4 LLM 成本记录

每次 LLM 调用记录：

-   用户 ID。
-   功能模块。
-   模型名称。
-   Prompt 版本。
-   Input Tokens。
-   Output Tokens。
-   请求耗时。
-   调用成本。
-   成功或失败状态。

------------------------------------------------------------------------

## 13. 测试与质量保证

  测试层级           工具                 目标
  ------------------ -------------------- --------------------
  Unit Test          Pytest               单个业务函数
  Integration Test   Pytest               数据库和服务交互
  API Test           FastAPI TestClient   接口行为
  E2E Test           Playwright           浏览器真实用户流程
  AI Evaluation      评测 Dataset         模型输出质量

### 13.1 Grammar Evaluation

评估：

-   Precision。
-   Recall。
-   F1。
-   误报率。
-   漏报率。
-   错误位置准确率。
-   自主修改验证准确率。

### 13.2 RAG Evaluation

评估：

-   Recall@K。
-   Precision@K。
-   MRR。
-   推荐相关性。

### 13.3 IELTS Evaluation

评估：

-   与人工评分的一致性。
-   不同模型评分稳定性。
-   反馈准确性。
-   对原文论证的忠实程度。

### 13.4 Editor E2E

重点覆盖：

-   多个错误同时出现。
-   用户修改文本后旧标记失效。
-   正确修改后标记消失。
-   错误修改后继续标红。
-   查看模糊答案。
-   点击详细教学。
-   快捷键冲突。
-   中文输入法组合输入。
-   多处修改后的文本位置映射。
-   保存失败和网络中断恢复。

------------------------------------------------------------------------

## 14. 架构决策记录（ADR）

  ------------------------------------------------------------------------------------------------------------
  编号                    决策                    结论
  ----------------------- ----------------------- ------------------------------------------------------------
  ADR-001                 系统架构                模块化单体

  ADR-002                 前端                    Next.js + TypeScript

  ADR-003                 后端                    Python + FastAPI

  ADR-004                 数据库                  PostgreSQL

  ADR-005                 向量检索                pgvector

  ADR-006                 编辑器                  TipTap / ProseMirror

  ADR-007                 基础语法检查            LanguageTool + 自定义规则

  ADR-008                 LLM 接入                统一 Provider Abstraction

  ADR-009                 AI 组件框架             LangChain 按需使用

  ADR-010                 Agent 工作流            LangGraph 按需使用

  ADR-011                 版本管理                Snapshot + Edit Events

  ADR-012                 缓存与队列              Redis 按需引入

  ADR-013                 部署                    Docker Compose 起步

  ADR-014                 测试                    Pytest + Playwright + AI Evaluation

  ADR-015                 详细教学                点击后基于当前句子与上下文实时生成，不设置可复用教学内容库
  ------------------------------------------------------------------------------------------------------------

### ADR-015 说明

详细教学是针对用户当前错误的个性化解释，不是通用知识库查询。

系统可以保存同一请求的结果用于短期缓存和避免重复付费，但不得将其作为脱离当前句子、可跨场景复用的教学答案。用户文本或上下文变化时，应重新判断缓存有效性。

------------------------------------------------------------------------

## 15. MVP 实施范围

### 第一批：基础产品闭环

-   Next.js + TipTap。
-   FastAPI。
-   PostgreSQL。
-   用户认证。
-   作文 CRUD。
-   作文基准快照与版本管理。
-   LanguageTool 集成。
-   统一错误反馈 Schema。
-   自主纠错验证。
-   LLM Provider 基础封装。
-   按需详细教学。
-   表达润色与中文翻译。

### 第二批：个人知识库

-   表达收藏与提取。
-   pgvector。
-   Embedding。
-   RAG 检索。
-   历史表达推荐。
-   错误画像。
-   表达复习。

### 第三批：高级 AI 能力

-   LangGraph Writing Planner。
-   Learning Extractor。
-   Personalized Study Planner。
-   Redis 异步任务。
-   Langfuse。
-   AI Evaluation 完善。

------------------------------------------------------------------------

## 16. ERD 阶段待确定事项

本系统设计不提前假定所有数据库字段。以下内容将在 ERD 中进一步明确：

1.  User、UserProfile 和认证会话的关系。
2.  Essay、WritingSession、EssayVersion 的关系。
3.  Original Snapshot、Assisted Version、Final Version 的保存规则。
4.  EssayEditEvent 与 AISuggestion 的关系。
5.  WritingError 与文档版本、文本范围的关联。
6.  ErrorRule 与程序化检查结果的关系。
7.  UserExpression 与通用 Expression 内容的关系。
8.  ExpressionEmbedding 的存储和更新策略。
9.  ExpressionReview 与 UserExpressionProgress 的关系。
10. IELTS Book、Test、Task 的层级关系。
11. WritingOutline 与 Essay 的关系。
12. AIUsageLog 与用户、任务、模型调用的关联。
13. 删除作文时相关错误、建议、向量和学习记录的生命周期。

------------------------------------------------------------------------

## 17. 进入下一阶段的验收标准

System Design 完成的判断标准：

-   前端和后端职责明确。
-   业务模块边界明确。
-   Rule-first 检查流程明确。
-   详细教学明确为上下文相关的按需生成，不设置可复用教学内容库。
-   作文版本与修改事件原则明确。
-   RAG 与 LangGraph 的适用边界明确。
-   MVP 和后期能力区分明确。
-   ERD 和 API Specification 有清晰的设计输入。

**结论：本 System Design 可作为后续 Database ERD、API Specification
和开发任务拆解的基线。**

------------------------------------------------------------------------

# 18. 后续设计顺序

1.  **Database ERD：** 定义实体、字段、主外键、索引和数据生命周期。
2.  **API Specification：** 定义接口、请求响应
    Schema、错误码、认证和版本控制。
3.  **Development Plan：** 将功能拆解为可独立实现和验收的开发任务。
4.  **Implementation：**
    先完成前后端基础闭环，再逐步接入规则引擎、LLM、RAG 和 Agent。

**文档结束 --- AI Writing Coach System Design V1.1**
