# AgentHub Interview Questions

1. Why keep this system as a modular monolith instead of splitting services?
2. How does the ingestion pipeline make document processing idempotent?
3. Why combine dense, sparse, RRF, and reranking retrieval?
4. How are citation metadata and source traceability preserved?
5. How does the Agent Runtime prevent infinite loops and runaway Tool calls?
6. How does the Tool Registry validate schemas and normalize failures?
7. Why must a dangerous Tool pause before execution, and how is approval idempotent?
8. What is the difference between short-term Conversation memory and explicit long-term Memory?
9. How does the Langfuse Adapter avoid blocking the main request when telemetry fails?
10. Why are Answer Relevance and Faithfulness implemented as deterministic proxies in F6-T2?
11. How would you scale Qdrant, PostgreSQL, MinIO, and the backend independently?
12. What are the backup and recovery boundaries, and why is Redis disposable?
