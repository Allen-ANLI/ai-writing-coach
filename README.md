# AI Writing Coach

> 面向中文用户的英语写作训练 Web 应用 —— 边写边学，反馈就在原文旁边。

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17%20+%20pgvector-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

AI Writing Coach 是一个 inline-first 的英语写作教练：语法与表达反馈直接出现在原文附近，
而不是塞进一个独立的 AI 面板。用户在同一篇文档里写作、纠错、学习表达，并逐步建立
**属于自己的私人表达知识库**。界面为简体中文，作文与题目内容为英文。

## 功能特性

- **Inline-first 写作编辑器**（TipTap / ProseMirror）：自动保存、撤销/重做、字数统计、
  不可变历史快照与一键恢复；辅助学习 / 独立写作（考试条件）两种模式
- **对话式写作规划**：左侧聊天面板与 AI 协商大纲，确认后逐句给出灰色中文 ghost 提示，
  每条提示附来自范文的表达与句式卡片
- **自动语法反馈**：规则优先（LanguageTool + 自定义规则），LLM 按需补充；
  实时下划线、悬停即看纠正、Tab 一键接受；详细教学针对当前句子上下文生成，而非通用模板库
- **表达润色与中译英**：片段级自动检测不自然表达，提供 3 个可直接替换的候选；
  选中中文短语获得语境化英文候选
- **私人表达知识库**：收集、关键词 + 语义检索（pgvector）、从作文中提取候选（先确认再保存）
- **学习与复习**：SM-2 间隔重复、错误画像与趋势分析、个性化学习计划
- **IELTS 训练**：原创题库（覆盖 Task 1/2 全题型）、四项评分（明确标注估分）、1–4 级改写
- **账户与隐私**：设备会话管理、密码重置、数据导出、账号删除；
  订阅配额（沙箱支付）与 AI 用量分析

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 16（App Router）· React 19 · TypeScript（strict）· Tailwind CSS 4 · TipTap 3 · TanStack Query |
| 后端 | Python 3.13 · FastAPI · Pydantic 2 · SQLAlchemy 2 · Alembic（模块化单体） |
| 数据 | PostgreSQL 17 + pgvector |
| AI | LanguageTool（规则语法）· OpenAI 兼容 LLM / Embedding 适配器 · LangGraph（多步骤工作流） |
| 测试 | Pytest · Vitest · Playwright · OpenAPI 契约校验 |
| 基础设施 | Docker Compose · GitHub Actions CI · Nginx（生产配置） |

API 以 [`contracts/openapi.yaml`](contracts/openapi.yaml)（OpenAPI 3.1）为唯一机器可读契约，
前端类型生成与后端契约测试均从该文件出发。

## 快速开始

**前置要求**：Node.js 22+、Python 3.13+、Docker（含 Compose）。

```bash
# 1) 环境变量（首次）
cp .env.example .env
cp frontend/.env.example frontend/.env.local

# 2) 启动 PostgreSQL + pgvector 与 LanguageTool
docker compose up -d

# 3) 后端：依赖安装 → 数据库迁移 → 启动（端口 8000）
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 4) 前端：新终端（端口 3500）
cd frontend
npm install
npm run dev
```

打开 **http://localhost:3500** 即可使用；后端健康检查见
`http://localhost:8000/api/v1/health`。

> **说明**
> - AI 功能默认使用 `mock` provider（零成本，供开发与测试）。要获得真实的教学、润色、
>   评分效果，请在 `.env` 中配置 `LLM_*` / `EMBEDDING_*`（密钥只留在本地，已被 gitignore）。
> - Windows 用户可用一键脚本 `start-dev.ps1` / `stop-dev.ps1` / `status-dev.ps1`，
>   本机环境细节与常见坑见 [本地开发指南](docs/LOCAL_DEVELOPMENT.md)。

## 项目结构

```text
ai-writing-coach/
├── frontend/               # Next.js App Router（React 19 + TS strict + Tailwind 4 + TipTap）
├── backend/                # FastAPI 模块化单体（Python 3.13）
│   ├── app/                # api / core / infrastructure / modules / ai
│   ├── alembic/            # 数据库迁移
│   └── tests/              # 单元 / 契约 / PostgreSQL 集成测试
├── contracts/              # openapi.yaml —— 唯一 OpenAPI 契约源
├── docs/                   # PRD / 系统设计 / ERD / API 规范 / ADR / 开发计划
├── infrastructure/         # PostgreSQL 初始化、生产 Nginx 配置
├── scripts/                # 数据库备份 / 恢复 / 校验、性能探针、E2E 准备
├── docker-compose.yml      # 本地基础设施（PostgreSQL 17 + pgvector、LanguageTool）
├── docker-compose.prod.yml # 生产编排
└── AGENTS.md               # 工程约束（贡献者必读）
```

## 开发与测试

| 检查 | 命令（目录） |
|---|---|
| 后端测试 | `pytest`（backend/） |
| 后端 lint / 格式 | `ruff check .` / `ruff format --check .`（backend/） |
| 前端单元测试 | `npm run test:unit`（frontend/） |
| 前端 lint | `npm run lint`（frontend/） |
| 前端类型检查 | `npx tsc --noEmit`（frontend/） |
| 前端生产构建 | `npm run build`（frontend/） |
| E2E | `npx playwright test`（frontend/，隔离测试栈 :8001/:3600） |
| API 类型生成 | `npm run generate:api`（frontend/） |

GitHub Actions CI（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)）在每次 push / PR
运行后端测试（真实 PostgreSQL + LanguageTool 服务）、前端检查与依赖安全审计。

## 文档

| 文档 | 说明 |
|---|---|
| [AGENTS.md](AGENTS.md) | 工程约束与领域不变量（贡献者必读） |
| [docs/README.md](docs/README.md) | 文档权威索引与优先级规则 |
| [PRD V1.1](docs/PRD_V1.1.docx) | 产品需求（DOCX） |
| [系统设计 V1.1](docs/AI_Writing_Coach_System_Design_V1.1.md) | 架构基线 |
| [数据库 ERD V1.2](docs/DATABASE_ERD.md) | 模式与数据不变量 |
| [API 规范 V1.1.1](docs/API_SPECIFICATION.md) | 人类可读 API 语义 |
| [开发计划](docs/DEVELOPMENT_PLAN.md) · [追溯矩阵](docs/TRACEABILITY_MATRIX.md) | 阶段记录与逐条需求验证状态 |
| [ADR 决策记录](docs/ADR/) | 架构与产品决策（ADR-016 起；001–015 见系统设计附录） |
| [本地开发指南（Windows）](docs/LOCAL_DEVELOPMENT.md) | 一键脚本、本机环境、Docker 命令 |
| [发布清单](docs/LAUNCH_CHECKLIST.md) | 公开发布前置事项 |

## 项目状态

核心功能已实现并建立自动化测试覆盖（Pytest 集成测试、Vitest 单元测试、Playwright E2E、
OpenAPI 契约校验），逐项实现与验证状态见[追溯矩阵](docs/TRACEABILITY_MATRIX.md)。
公开部署及真实 LLM / 邮件 / 支付服务的启用尚未进行，按[发布清单](docs/LAUNCH_CHECKLIST.md)管理。
项目处于活跃开发中。