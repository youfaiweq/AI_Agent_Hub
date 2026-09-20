# AgentHub Architecture

```mermaid
flowchart LR
    Browser[Vue 3 + Nginx] --> API[FastAPI API]
    API --> Auth[Auth and Ownership]
    API --> Chat[Chat Service]
    API --> Agent[LangGraph Agent Runtime]
    Chat --> Retrieval[Dense / Sparse / Hybrid Retrieval]
    Agent --> Tools[Tool Registry]
    Retrieval --> Qdrant[(Qdrant)]
    Retrieval --> Postgres[(PostgreSQL)]
    Agent --> Postgres
    Chat --> Postgres
    API --> MinIO[(MinIO Documents)]
    API --> Redis[(Redis Runtime State)]
    Chat --> LLM[OpenAI-compatible LLM]
    Agent --> LLM
    API -. fail-open telemetry .-> Langfuse[Langfuse OTLP]
```

The production Compose file places PostgreSQL, Redis, Qdrant, MinIO, and the
backend on a private bridge network. Nginx is the only published application
entry point. Business logic remains behind API → Service → Repository layers;
providers are injected through adapter contracts.
