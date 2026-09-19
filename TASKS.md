# AgentHub 开发任务（优化版）

本文件是执行路线，`PROJECT_SPEC.md` 是产品需求，`ARCHITECTURE.md` 是技术架构，`AI_RULES.md` 是协作规则。四者冲突时，先停止实现并明确冲突，不自行猜测。

状态定义：

- `[ ]` 未开始
- `[~]` 进行中
- `[x]` 已完成
- `[!]` 被外部环境阻断

## 执行总原则

1. 一次只执行一个 Task；完成、测试、验收后停止，不自动进入下一个 Task。
2. 每个 Milestone 必须形成一个可演示的垂直切片，而不是只堆基础设施。
3. 先建立稳定契约，再接入具体供应商；业务代码依赖接口/Adapter，不依赖厂商 SDK。
4. 不新增基础设施服务。当前固定使用 PostgreSQL、Redis、Qdrant、MinIO；确有必要时先修改架构文档。
5. 所有数据库结构变化必须有 Alembic Migration；所有外部服务必须有配置、连接管理、超时、错误处理和健康检查。
6. 生产代码不得用假数据、随机数据、空实现或 TODO 冒充功能。测试可以使用 Mock/Fake Adapter。
7. 每个 Task 的完成标准必须包括：代码、测试、运行命令、失败场景、文档更新和 Remaining Issues。

## 当前仓库状态

当前项目已完成 v0.3 Naive RAG，并进入 v0.4 Advanced Retrieval，已有：

- FastAPI 应用入口、配置、日志、统一异常处理
- `/health` 与 Swagger/OpenAPI
- PostgreSQL、Redis、Qdrant、MinIO Compose 配置
- `.env.example` 与基础 API 测试
- 四份项目规范文档

当前未完成：

- F4-T5 v0.5 Release Gate 及后续里程碑

下一项为 **F4-T5 v0.5 Release Gate**；未经明确指令不得自动开始。

---

# Milestone 0 — Foundation / v0.1

目标：建立可运行、可观察、可测试的模块化单体基础，不实现任何业务领域和 AI 能力。

## F0-T1 — API Foundation 补全

状态：`[x]`

范围：

- 建立 `app/api/v1/` 路由结构
- 实现 `GET /api/v1/system/info`
- 补全 `APP_NAME`、`APP_VERSION`、`ENVIRONMENT`、`DEBUG`、`API_V1_PREFIX`
- 配置开发环境 CORS
- 保留并稳定 `/health` 响应契约
- 补充 `/health` 与 `/api/v1/system/info` 测试
- 增加 backend 启动 README

禁止：数据库连接、Redis/Qdrant/MinIO 业务 Client、Auth、RAG、Agent、LLM。

验收：`pytest` 通过（4 passed，1 个 Starlette/httpx 弃用警告）；`/docs`、`/health`、`/api/v1/system/info` 可访问；`app/main.py` 不包含业务 Route 实现。

## F0-T2 — 基础设施 Compose 验收

状态：`[x]`

范围：

- PostgreSQL、Redis、Qdrant、MinIO Compose 服务
- 固定端口、持久化卷、健康检查、环境变量
- `.env.example` 与本地启动说明
- 验证 `docker compose config`
- 在 Docker daemon 可用时验证 `docker compose up -d` 和 `docker compose ps`

验收：四个服务均为 healthy；FastAPI `/health` 已真实检查并确认 PostgreSQL、Redis、Qdrant、MinIO 全部 healthy。PostgreSQL 使用宿主机 `55432` 端口避免与本机已有服务冲突；MinIO 使用官方 Quay 镜像源。

## F0-T3 — PostgreSQL Persistence Foundation

状态：`[x]`

范围：

- SQLAlchemy 2.x AsyncEngine、AsyncSession、Session Dependency
- Base Model、UTC 时间字段、UUID 主键约定
- Alembic 配置与第一份空基线 Migration
- 数据库连接错误处理与健康检查
- 数据库层单元/集成测试

禁止：User、KnowledgeBase、Document 等业务 Model；这些进入 v0.2。

验收：Alembic `0001_baseline` 已应用；SQLAlchemy AsyncEngine/AsyncSession 可用；PostgreSQL 集成测试通过；Ruff 检查通过。

## F0-T4 — Infrastructure Client Adapters

状态：`[x]`

范围：

- Redis Client 生命周期、超时与 ping
- Qdrant Client 生命周期与 readiness 检查
- MinIO Client 配置与 bucket 健康检查
- 统一 Integration/Adapter 错误类型
- 连接层测试使用 Test Adapter，不依赖真实服务才能运行单元测试

禁止：Cache 业务、Vector Search 业务、文件上传业务。

验收：Redis、Qdrant、MinIO Adapter 单元测试与真实服务集成测试通过；聚合 `/health` 已通过 Adapter 检查全部服务；Qdrant 客户端约束为 `1.12.x`，与 Compose 服务版本保持兼容。

## F0-T5 — Frontend Shell

状态：`[x]`

范围：

- Vue 3 + TypeScript + Vite
- Vue Router、Pinia、Element Plus
- API Client 基础封装
- 基础 Layout、Dashboard 占位页、错误/加载状态
- `/health` 或 `/api/v1/system/info` 的最小连通性展示

禁止：登录、知识库、聊天、Agent 页面。

验收：Vite 开发服务器可启动并返回首页；TypeScript 类型检查通过；生产构建通过；Dashboard 能调用后端系统信息和健康接口。

## F0-T6 — v0.1 Release Gate

状态：`[x]`

验收清单：

- `docker compose up -d` 成功
- PostgreSQL、Redis、Qdrant、MinIO 均健康
- FastAPI 能启动，`/docs` 可打开
- `/health` 与 `/api/v1/system/info` 正常
- 前端能启动并访问基础 Layout
- 后端测试、前端测试/构建通过
- `.env` 未进入 Git，README 可让新环境复现启动

只有 F0-T6 通过，才能进入 v0.2。

---

# Milestone 1 — Identity & Knowledge Slice / v0.2

目标：完成“用户登录 → 创建知识库 → 上传原始文档”的第一个业务闭环。

## F1-T1 — Authentication

状态：`[x]`

- User Model、Migration、Repository、Service
- 注册、登录、当前用户
- Argon2 或项目选定的密码哈希方案
- JWT Access Token、过期时间、认证依赖
- 密码、Token、Secret 不进入日志
- 注册、登录、错误凭证、重复用户测试

## F1-T2 — Knowledge Base CRUD

状态：`[x]`

- KnowledgeBase Model、Migration、Repository、Service、Schema
- 创建、列表、详情、更新、删除
- 所有权校验：用户只能访问自己的知识库
- 分页、排序、统一错误码
- API、Service、Repository 测试

## F1-T3 — Document Metadata & Object Storage

状态：`[x]`

- Document Model、Migration、Repository、Service
- PDF/TXT/Markdown 文件类型与大小校验
- MinIO 原文件上传、storage_key、元数据保存
- 状态：uploaded、processing、completed、failed
- 上传失败事务补偿与孤儿对象处理策略
- 文档列表、详情、删除

## F1-T4 — Knowledge UI

状态：`[x]`

- 登录/注册
- Dashboard
- 知识库列表/详情
- 文档上传、列表、状态、删除
- 统一 API 错误和加载状态

## F1-T5 — v0.2 Release Gate

状态：`[x]`

用户可以注册、登录、创建知识库、上传文档、查看文档并删除文档；API、数据库 Migration、MinIO 和前端流程均有可重复测试。

---

# Milestone 2 — Document Ingestion & Naive RAG / v0.3

目标：完成“上传文档 → 处理 → 检索 → 回答 → 引用”的最小真实闭环。

## F2-T1 — Parsing and Chunking Contracts

状态：`[x]`

- `Parser`、`Cleaner`、`Chunker` 接口
- TXT、Markdown、PDF Parser
- 统一 ParsedDocument、Chunk、ChunkMetadata 类型
- 页码、位置、document_id、chunk_id 元数据
- Parser/Chunker 单元测试和异常文件测试

## F2-T2 — Ingestion Pipeline

状态：`[x]`

- Document 状态流转：uploaded → processing → completed/failed
- 解析、清理、分块 Pipeline
- 失败原因持久化
- 幂等处理与重复触发保护
- 处理过程日志

初期允许同步执行；只有在性能或可靠性验证后再引入后台 Worker，不提前引入复杂任务框架。

## F2-T3 — Embedding and Vector Store

状态：`[x]`

- EmbeddingProvider Adapter
- Qdrant VectorStore Adapter
- Collection 命名、向量维度配置和 payload schema
- upsert、search、delete、health_check
- 文档重处理与向量删除策略
- 使用 Provider Contract Test 验证 Adapter

## F2-T4 — Dense Retrieval and Context

状态：`[x]`

- DenseRetriever
- Top-K、相似度阈值、去重
- ContextBuilder 与 Token Budget
- Citation 结构：document_id、filename、chunk_id、page_number、snippet

## F2-T5 — LLM Provider and Chat

状态：`[x]`

- LLMProvider Adapter
- Conversation、Message Model 与 Migration
- Chat Service、Chat API、引用返回
- 无相关上下文时明确回答无法从知识库确认，不编造来源
- LLM 错误、超时、空回答测试

## F2-T6 — v0.3 Release Gate

状态：`[x]`

上传至少一份真实 PDF/TXT/Markdown 后，可以通过 API/UI 提问并获得基于检索上下文的答案与 Citation。检索结果和引用可追溯到原文 Chunk。

---

# Milestone 3 — Advanced Retrieval / v0.4

目标：在 Naive RAG 稳定后提高召回、可解释性和调试能力。

## F3-T1 — Sparse Retrieval

状态：`[x]`

- 使用 PostgreSQL Full-Text Search（`simple` 配置）和 GIN 表达式索引
- `document_chunks` 持久化处理后的 chunk 文本与页码/字符位置元数据
- `SparseRetriever` 支持 `query`、`knowledge_base_id`、`top_k`、`score_threshold` 和 rank score
- 与 `DenseRetriever` 共享 `RetrievedChunk` 结果结构和 `Retriever` 契约
- ingestion 首次处理、重处理时同步替换 PostgreSQL chunk 快照
- Sparse Retrieval 单元测试和 PostgreSQL 集成测试已覆盖
- 不新增 Elasticsearch 等基础设施

## F3-T2 — Hybrid Retrieval and RRF

状态：`[x]`

- `HybridRetriever` 并行调用 DenseRetriever + SparseRetriever
- 独立 `RRFusion`，支持 RRF 参数和来源权重
- 分数归一化、候选集大小、重复 Chunk 处理
- Hybrid 结果保留 dense/sparse 原始分数、归一化分数、来源 rank 和 fusion score
- Hybrid Retrieval Contract Tests 已覆盖
- 不接入 Reranker，不修改 Chat API

## F3-T3 — Reranker Adapter

状态：`[x]`

- `BaseReranker`、`RerankedChunk` 和标准化 `RerankerError`
- Cohere-compatible HTTP Reranker Provider Adapter
- Settings/.env 支持 provider、model、API key、base URL、timeout、fallback、Top-K
- 超时、HTTP 错误、非法响应、空配置和 Top-K 校验
- fallback 必须显式开启，仅保留原检索顺序且不伪造 rerank score
- 不使用关键词排序等伪 Reranker 冒充真实实现
- Reranker Provider 单元测试已覆盖

## F3-T4 — Retrieval Debug and Evaluation

状态：`[x]`

- Retrieval Debug API：支持 dense、sparse、hybrid、rerank 模式
- Knowledge Base 详情页 Retrieval Test UI
- 返回 query、chunk、document、page、snippet、dense_score、sparse_score、fusion_score、rerank_score、final_rank
- Versioned request-scoped Evaluation Dataset API
- 初始 Retrieval Recall 和 Citation Correctness 指标
- API 所有权校验、失败错误转换和测试覆盖
- 不接入 Agent、Langfuse 或生产级评测流水线

## F3-T5 — v0.4 Release Gate

状态：`[x]`

- 同一问题已通过真实 PostgreSQL/Qdrant 数据比较 Dense、Sparse、Hybrid 结果
- Rerank Provider contract、排序、错误和显式 fallback 已通过测试
- Debug API/UI 可追踪 query、chunk、document、各阶段 score 和 final_rank
- 同一 Evaluation Dataset 重复运行结果一致
- 后端、前端、Migration、Docker 健康和敏感文件验收通过
- 真实 Cohere Rerank 请求仍需配置 `RERANKER_API_KEY`

---

# Milestone 4 — Conversations & LangGraph Agent / v0.5

目标：让 Agent 在受控范围内调用工具，并保存完整执行记录。

## F4-T1 — Agent Runtime Contracts

状态：`[x]`

- `AgentState`：messages、user_id、conversation_id、agent_id、knowledge_base_id、tool_calls、tool_results、metadata
- AgentRun、ToolCallRecord Model、Repository 与 0008 Migration
- Max Steps、Timeout、取消、失败状态
- LangGraph `START → agent → tool/END` Graph/Node/Conditional Edge
- AgentStepHandler、ToolExecutor 和 ToolExecutionResult Provider-neutral 契约
- Agent Runtime unit tests、PostgreSQL persistence integration test
- 不实现 Tool Registry 或具体 Tool

## F4-T2 — Tool Registry

状态：`[x]`

- `BaseTool` 统一 `name`、`description`、`input_schema`、`execute`
- `ToolRegistry` 注册、发现、重复名保护和 F4-T1 `ToolExecutor` 适配
- JSON object input schema 的 required/type 校验
- 未注册工具、非法输入、工具异常、超时统一转换为结构化错误
- Tool 执行日志只记录 tool_name、call_id、状态和耗时，不记录参数/结果
- ToolCallRecord 创建、running、completed/failed 持久化
- Tool Registry unit tests 已覆盖
- 不实现具体业务 Tool

## F4-T3 — Read-only Tools

状态：`[x]`

- `knowledge_search`：复用 Retriever，返回 traceable source chunks
- `calculator`：AST 白名单求值，不使用 `eval`
- `sql_query`：仅允许 SELECT，sqlglot AST 校验、表白名单、超时、行数限制、JSON 序列化
- `web_search`：Provider Adapter 契约和 Tavily-compatible HTTP Adapter
- 所有工具接入统一 Tool Registry、输入校验、结构化错误和执行审计
- 单元测试、Provider MockTransport 测试和 PostgreSQL SQL 集成测试已覆盖

## F4-T4 — Agent API and UI

状态：`[x]`

- Agent 配置、列表、详情、更新、删除 API
- Agent Run API、Run History、Tool Call 记录返回
- 完成非流式可靠运行版本，使用当前 LLM Provider 和 Tool Registry
- 前端 Agents 列表、创建、详情、运行和历史页面
- 所有权校验、max steps、timeout、失败状态和运行持久化已覆盖
- 不实现流式输出、Memory 或 HITL Approval

## F4-T5 — v0.5 Release Gate

Agent 能根据问题选择工具、在最大步数内结束、记录每次 Tool Call，并正确处理工具错误和超时。

---

# Milestone 5 — Memory & Human-in-the-loop / v0.6

## F5-T1 — Short-term Conversation Memory

- Conversation 历史加载与上下文窗口
- Token Budget、截断策略、消息持久化

## F5-T2 — Explicit Long-term Memory

- 结构化 Memory Model、来源、置信度、更新时间
- 只保存用户明确要求记住或经确认的信息
- 提取、检索、编辑、删除 API/UI
- 禁止把全部聊天记录复制为长期 Memory

## F5-T3 — Approval Runtime

- Dangerous Tool 定义
- interrupt、waiting_approval、approve、reject、resume
- Approval 状态持久化、幂等与过期
- 前端审批 UI

## F5-T4 — v0.6 Release Gate

Agent 遇到副作用 Tool 时不会自动执行；用户批准后可恢复，拒绝后有明确终态和审计记录。

---

# Milestone 6 — Observability & Evaluation / v0.7

## F6-T1 — Observability Adapter

- Langfuse Adapter
- Trace、LLM、Retrieval、Rerank、Tool、Memory、Agent Run
- latency、token usage、model、error
- Langfuse 不可用时不阻塞主业务

## F6-T2 — Evaluation Pipeline

- Dataset 版本化
- Retrieval Recall
- Answer Relevance
- Faithfulness
- Citation Correctness
- 可重复运行并输出结果

## F6-T3 — v0.7 Release Gate

一次 Agent 请求可在 Trace 中看到完整执行链路，评测结果可重复、可比较。

---

# Milestone 7 — v1.0 Job-ready Release

- UI Polish、响应式和空状态
- Backend/Frontend/Nginx Docker 镜像
- Production Compose 与安全配置
- Demo Data、README、Architecture Diagram、ER Diagram、API 文档
- Screenshots、Demo Video Script、Interview Questions、Resume Description
- 安全检查、依赖审计、备份/恢复说明、错误演练

## 最终验收

从零开始按 README 操作，能够启动基础设施、后端和前端；完成注册、知识库、文档上传、RAG 问答、引用、Agent 工具调用、审批、Trace 和 Evaluation 演示。

## 当前执行指令

**F0-T1 — API Foundation 补全已完成。**
**F0-T2 — 基础设施 Compose 验收已完成。**
**F0-T3 — PostgreSQL Persistence Foundation 已完成。**
**F0-T4 — Infrastructure Client Adapters 已完成。**
**F0-T5 — Frontend Shell 已完成。**
**F0-T6 — v0.1 Release Gate 已完成。**
**F1-T1 — Authentication 已完成。**
**F1-T2 — Knowledge Base CRUD 已完成。**
**F1-T3 — Document Metadata & Object Storage 已完成。**
**F1-T4 — Knowledge UI 已完成。**
**F1-T5 — v0.2 Release Gate 已完成。**
**F2-T1 — Parsing and Chunking Contracts 已完成。**
**F2-T2 — Ingestion Pipeline 已完成。**
**F2-T3 — Embedding and Vector Store 已完成。**
**F2-T4 — Dense Retrieval and Context 已完成。**
**F2-T5 — LLM Provider and Chat 已完成。**
**F2-T6 — v0.3 Release Gate 已完成。**
**F3-T1 — Sparse Retrieval 已完成。** 下一项允许执行 **F3-T2 — Hybrid Retrieval and RRF**，但未收到明确开发指令前不要自动开始。
**F3-T2 — Hybrid Retrieval and RRF 已完成。**
**F3-T3 — Reranker Adapter 已完成。** 下一项允许执行 **F3-T4 — Retrieval Debug and Evaluation**，但未收到明确开发指令前不要自动开始。
**F3-T4 — Retrieval Debug and Evaluation 已完成。** 下一项允许执行 **F3-T5 — v0.4 Release Gate**，但未收到明确开发指令前不要自动开始。
**F3-T5 — v0.4 Release Gate 已完成。** 下一项允许执行 **F4-T1 — Agent Runtime Contracts**，但未收到明确开发指令前不要自动开始。
**F4-T1 — Agent Runtime Contracts 已完成。** 下一项允许执行 **F4-T2 — Tool Registry**，但未收到明确开发指令前不要自动开始。
**F4-T2 — Tool Registry 已完成。** 下一项允许执行 **F4-T3 — Read-only Tools**，但未收到明确开发指令前不要自动开始。
**F4-T3 — Read-only Tools 已完成。** 下一项允许执行 **F4-T4 — Agent API and UI**，但未收到明确开发指令前不要自动开始。
**F4-T4 — Agent API and UI 已完成。** 下一项允许执行 **F4-T5 — v0.5 Release Gate**，但未收到明确开发指令前不要自动开始。
