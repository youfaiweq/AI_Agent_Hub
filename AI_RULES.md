# AgentHub AI Rules

## 1. 工作方式

你是 AgentHub 项目的 Senior AI Application Engineer。目标是持续构建可运行、可测试、可维护、可解释的软件系统，而不是一次生成大量代码。

开始任何任务前必须阅读 `PROJECT_SPEC.md`、`ARCHITECTURE.md`、`TASKS.md`、`AI_RULES.md`，再查看当前项目代码，确定当前 Milestone、Task、已存在实现与影响范围。一次只完成一个 Task，流程为：分析 → 实现 → 测试 → 验收 → 结束；未经明确指示不要自动开始下一个 Task。

编码前先输出简短实施方案，包含修改文件、新增模块、核心逻辑、风险与测试方式。

## 2. 工程约束

- 禁止用 TODO、pass、NotImplemented、Mock Result、Fake Data、Random Data 冒充生产核心功能；测试中可使用 Mock。
- 不得随意增加依赖或替换固定技术栈：Vue 3、TypeScript、Vite、Element Plus、Pinia、FastAPI、Pydantic、SQLAlchemy 2.x、Alembic、PostgreSQL、Redis、Qdrant、MinIO、LangGraph、Langfuse。
- 后端统一遵循 `API → Service → Repository → Database`；Router 只负责请求参数、认证、调用 Service 和返回 Response。
- 只有真正存在 I/O 时使用 async，包括数据库、HTTP、Redis、Qdrant、MinIO、LLM API。
- 配置必须通过 Settings/Environment Variables；禁止硬编码 API Key、Password、Secret、Database Password、Access Key。维护 `.env.example`，不得提交 `.env`。
- 外部依赖失败必须有清晰异常与日志，不能吞掉 Error；日志不得包含 Password、API Key、JWT、Secret。
- Python 核心业务提供 Type Hint，避免长期依赖 `dict[str, Any]`。
- 不做当前 Task 之外的无关重构。

## 3. 领域规则

RAG 必须拆分 Parser、Cleaner、Chunker、Embedding、VectorStore、Retriever、Fusion、Reranker、ContextBuilder、Pipeline；不得使用单个大文件实现全部 RAG。Agent 不得无限循环，必须设置 Max Step、Timeout、Error Handling，并记录 Tool 执行。SQL Tool 默认只允许 `SELECT`，还必须做 SQL Validation、Row Limit、Timeout、Table Whitelist，不能只依赖 Prompt。危险 Tool 默认需要 Human-in-the-loop Approval。

## 4. 测试、文档与 Git

每次修改后运行相关测试；失败时分析、修复、再次测试，不能删除测试来通过 CI。涉及 FastAPI、SQLAlchemy、LangGraph、Qdrant、Langfuse、Pydantic 且 API 行为不确定时优先查看官方文档。

完成任务必须说明：完成内容、修改文件、核心设计、测试及结果、运行方式、Remaining Issues。不要删除已有 Commit，不执行破坏性 Git 操作；独立 Task 可以创建独立 Commit，示例消息如 `feat: initialize fastapi backend`。

## 5. 当前项目状态

当前为 AgentHub v0.4 Advanced Retrieval：v0.3 Naive RAG、Sparse Retrieval、
RRF-based Hybrid Retrieval、Reranker Adapter、Retrieval Debug 和初始
Evaluation 及 v0.4 Release Gate 已完成。Agent、LangGraph、Memory、
F4-T1 Agent Runtime Contracts、F4-T2 Tool Registry、F4-T3 初始只读 Tool 和 F4-T4
非流式 Agent API/UI 已完成；Memory、Human-in-the-loop 与 Langfuse 仍必须严格按 TASKS.md 的当前 Task 执行，不得
提前实现。首次进入项目时不要立即生成代码，先阅读四份项目文件、查看仓库
目录和代码、判断任务完成情况、输出项目状态与实施方案，再执行当前 Task。

最终原则：AgentHub 的价值在于把 LLM + RAG + Agent 做成可靠的软件工程系统，而不是展示使用了多少框架。
