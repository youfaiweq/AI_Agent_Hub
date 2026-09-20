# AgentHub — 系统架构设计

## 1. 架构原则

AgentHub 使用 Modular Monolith（模块化单体架构）。第一阶段禁止拆分微服务，以降低复杂度、聚焦 AI 核心能力并保留未来拆分空间。

```text
Vue 3 Frontend → FastAPI Backend
                       ├─ PostgreSQL
                       ├─ Redis
                       ├─ MinIO
                       ├─ Qdrant / RAG
                       ├─ LangGraph / Agent
                       ├─ LLM、Embedding、Reranker Providers
                       └─ Langfuse
```

## 2. 前端

技术栈：Vue 3、TypeScript、Vite、Element Plus、Pinia、Vue Router。目录建议：

```text
frontend/src/
├── api/ assets/ components/ layouts/
├── router/ stores/ types/ utils/ views/
```

API 请求统一封装，禁止在组件内大量直接调用 HTTP。

## 3. 后端

```text
backend/
├── app/
│   ├── api/ core/ models/ schemas/ repositories/ services/
│   ├── rag/ agents/ tools/ memory/ integrations/ main.py
├── tests/ alembic/ pyproject.toml
```

统一分层：`API → Service → Repository → Database`。

- API 负责 HTTP、参数、Authentication、Response。
- Service 负责 Business Logic、事务协调和领域校验。
- Repository 负责数据库查询、CRUD 与持久化。

Router 不写复杂 SQL 或业务逻辑。

## 4. Core、Database 与基础设施

```text
core/
├── config.py database.py security.py
├── exceptions.py logging.py dependencies.py
```

使用 PostgreSQL、SQLAlchemy 2.x、优先 AsyncSession、Alembic。所有结构变化必须通过 Migration。Redis 只用于 Cache、Rate Limit、Temporary State 与未来异步任务，不作为永久数据库。MinIO 保存文档原文件，数据库保存 metadata、storage_key 与 status。

## 5. RAG

```text
rag/
├── parsers/ cleaners/ chunkers/ embeddings/
├── vectorstores/ retrievers/ fusion/ rerankers/
├── context/ pipeline/
```

Parser 统一为 `parse(file) -> ParsedDocument`，Chunker 统一为 `split(document) -> list[Chunk]`。Embedding、LLM、Vector Store、Reranker 均使用 Provider/Adapter 接口，业务代码不得绑定单一厂商。Vector Store 第一版使用 Qdrant，Retriever 包含 Dense、Sparse、Hybrid，Fusion 使用独立 RRF 实现，Context Builder 负责 Token Budget、去重和 Citation Metadata。

## 6. Agent、Tool、Memory

```text
agents/
├── graphs/ nodes/ states/ prompts/ runtime/ services/
tools/
├── base.py knowledge.py sql.py calculator.py web_search.py
memory/
├── short_term/ long_term/ extractor/ repository/
```

Tool 至少提供 `name`、`description`、`input_schema`、`execute`，不直接依赖 HTTP Request。Agent 必须设置 Max Step、Timeout、Error Handling，并保存 AgentRun 与 Tool Call Record。SQL Tool 只读、限时、限行并使用表白名单。

## 7. Human-in-the-loop 与 Observability

危险 Tool 采用 `Agent → interrupt → waiting_approval → approve/reject → resume` 流程。Langfuse 通过独立 Observability Adapter 接入，业务代码不与 Langfuse 深度耦合。

## 8. API、配置、日志和测试

API 前缀统一为 `/api/v1`，返回尽量统一为 `{ "data": {}, "message": "success" }`，错误为 `{ "detail": { "code": "...", "message": "..." } }`。敏感信息全部通过环境变量，维护 `.env.example`，禁止提交 `.env`。统一 Logger 记录请求、数据库、RAG、LLM、Tool、Agent 错误，禁止大量 `print`。测试分为 `tests/unit`、`tests/integration`、`tests/api`。

## 9. Docker

开发环境使用 `docker-compose.yml` 管理 PostgreSQL、Redis、Qdrant、MinIO；后期再加入 backend、frontend、nginx 与 production compose。

## 10. 当前限制

当前已完成 v0.3 Naive RAG、Sparse Retrieval、RRF-based Hybrid Retrieval 和
Reranker Adapter、Retrieval Debug、初始 Evaluation 和 v0.4 Release Gate；
Agent Runtime Contracts、Tool Registry、初始只读 Tool、非流式 Agent API/UI、
短期 Memory、显式长期 Memory 和 Approval Runtime 已完成；Langfuse 仍按后续
任务实现。优先级为：正确性 >
可维护性 > 可测试性 > 可观测性 > 性能优化 > 技术炫技。
