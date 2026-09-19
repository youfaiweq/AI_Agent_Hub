# AgentHub — 项目需求规格说明

## 1. 项目定位

AgentHub 是一个面向企业知识管理与智能任务执行场景的 AI 应用平台。系统允许用户创建知识库、上传企业文档，并通过 RAG 对文档进行检索问答；同时通过 LangGraph 构建能够自动选择并调用知识库检索、SQL 查询、计算分析、Web Search 等工具的智能 Agent。

项目目标是构建具备 RAG、Agent、Tool Calling、Memory、Human-in-the-loop、Observability、Evaluation 与 Docker Deployment 能力的完整 AI 应用工程项目，而不是简单的 ChatGPT UI。

## 2. 核心场景

### 企业知识问答

支持产品说明书、公司制度、售后政策、技术文档、FAQ、Markdown 等企业资料。用户提问后，系统检索、排序、构建上下文、生成答案并返回引用来源。

### 企业数据分析

Agent 可判断问题需要业务数据，调用受限的 `sql_query` 查询 Demo Business Database 后生成答案。

### 多工具协同

复杂问题可同时调用 SQL Tool 与 Knowledge Tool，并基于两个工具结果进行综合分析。

### 长期记忆

只保存用户明确要求记住的信息、偏好和常用业务指标；不把全部聊天内容无限保存为长期 Memory。

### 高风险操作审批

涉及发送通知、邮件、写数据库或其他外部副作用的 Tool，必须在执行前暂停并请求用户 approve/reject。

## 3. 用户角色

第一版仅有普通用户：注册、登录、管理个人知识库、上传/删除文档、AI 对话、创建 Agent、查看会话和 Agent 执行记录。暂不实现 Admin、Workspace、Organization、RBAC。

## 4. 功能范围

### Authentication

用户注册、登录、JWT Authentication、获取当前用户、密码哈希与 Token 校验。

### Knowledge Base

支持知识库创建、修改、删除、查询与文档查看。字段：`id`、`user_id`、`name`、`description`、`created_at`、`updated_at`。

### Document

第一阶段支持 PDF、TXT、Markdown；未来支持 DOCX、XLSX、HTML、Web Page。状态为 `uploaded`、`processing`、`completed`、`failed`。原文件进入 MinIO，数据库只保存元数据与 `storage_key`。

## 5. RAG Pipeline

```text
Document → Parser → Cleaner → Chunker → Embedding → Vector Store
→ Retriever → Fusion → Reranker → Context Builder → LLM
→ Answer + Citation
```

v0.3 先实现 Naive RAG：问题 Embedding、Dense Retrieval、Top-K Chunks、Context、LLM、Answer 与 Citation。Citation 至少包含 `document_id`、`filename`、`chunk_id`、可选 `page_number` 与 content snippet。

v0.4 实现 Dense + Sparse Retrieval、RRF Fusion、Reranker 与 Retrieval Debug。Debug 至少记录 query、chunk、document、dense_score、sparse_score、fusion_score、rerank_score、final_rank。

## 6. Agent

使用 LangGraph 实现：

```text
START → Agent → 是否需要 Tool？
                 ├─ Yes → Tool → Agent
                 └─ No  → END
```

第一阶段工具：`knowledge_search`、受限只读的 `sql_query`、`calculator`、通过 Provider Adapter 封装的 `web_search`。Agent State 至少包含 `messages`、`user_id`、`conversation_id`、`agent_id`、`knowledge_base_id`、`tool_calls`、`tool_results`、`metadata`。

SQL Tool 默认只允许 `SELECT`，禁止 INSERT、DELETE、UPDATE、DROP、ALTER、TRUNCATE；必须有 SQL Validation、Timeout、Row Limit 与 Table Whitelist。

## 7. Conversation、Memory 与 HITL

Conversation 支持创建、查询、历史 Message 查询和删除；Message Role 为 `user`、`assistant`、`system`、`tool`。短期 Memory 保存当前 Conversation，长期 Memory 结构化保存用户明确要求记住的信息与可复用偏好。

高风险 Agent Run 状态为 `pending`、`running`、`waiting_approval`、`completed`、`failed`、`cancelled`；用户可以 approve 或 reject。

## 8. Observability 与 Evaluation

接入 Langfuse，记录 Trace、LLM Call、Retrieval、Tool Call、Latency、Token Usage、Model、Error 与 Agent Run。后期建立包含 Question、Expected Answer、Expected Source 的 Evaluation Dataset，并评估 Retrieval Recall、Answer Relevance、Faithfulness、Citation Correctness。

## 9. 前端页面

最终包含 Login、Dashboard、AI Chat、Knowledge Base（列表、详情、Documents、Chunk Preview、Retrieval Test）、Agents（列表、详情、Tools、Run History）、Conversations、Memory、Trace、Settings。

## 10. 非功能需求

系统必须模块化、类型安全、可验证、具备异常处理、统一日志、API Validation、Authentication、Database Transaction、Unit Test、Integration Test 与 Docker Deployment。核心业务逻辑不得直接写在 Router 中。

## 11. 阶段目标

```text
v0.1 基础工程
v0.2 Auth + Knowledge Base
v0.3 Naive RAG
v0.4 Advanced RAG
v0.5 Agent
v0.6 Memory + Human-in-the-loop
v0.7 Observability + Evaluation
v1.0 求职展示版本
```

最终目标是证明 Python AI Backend、FastAPI、PostgreSQL、Redis、RAG、Vector Database、Hybrid Search、Reranking、LangGraph、Agent Architecture、Tool Calling、Memory、Human-in-the-loop、Observability 与 Docker Deployment 能力。
