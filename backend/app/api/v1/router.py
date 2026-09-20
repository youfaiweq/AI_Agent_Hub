"""Version 1 API router registration."""

from fastapi import APIRouter

from app.api.v1.routes.agents import router as agent_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.chat import router as chat_router
from app.api.v1.routes.documents import router as document_router
from app.api.v1.routes.knowledge_bases import router as knowledge_base_router
from app.api.v1.routes.memories import router as memory_router
from app.api.v1.routes.retrieval import router as retrieval_router
from app.api.v1.routes.system import router as system_router

router = APIRouter()
router.include_router(system_router)
router.include_router(auth_router)
router.include_router(agent_router)
router.include_router(knowledge_base_router)
router.include_router(document_router)
router.include_router(chat_router)
router.include_router(retrieval_router)
router.include_router(memory_router)
