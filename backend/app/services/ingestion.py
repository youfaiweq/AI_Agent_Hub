"""Synchronous document-ingestion orchestration service."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.integrations.minio import MinioAdapter
from app.models.document import Document, DocumentStatus
from app.rag.embeddings import EmbeddingProvider
from app.rag.errors import DocumentProcessingError
from app.rag.pipeline import DocumentIngestionPipeline
from app.rag.vectorstores.qdrant import QdrantVectorStore
from app.repositories.documents import DocumentRepository
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.document import DocumentProcessingResponse, DocumentResponse

logger = logging.getLogger(__name__)


class IngestionService:
    """Coordinate idempotent document processing and status transitions."""

    def __init__(
        self,
        session: AsyncSession,
        storage: MinioAdapter,
        embedder: EmbeddingProvider,
        vector_store: QdrantVectorStore,
        pipeline: DocumentIngestionPipeline | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.embedder = embedder
        self.vector_store = vector_store
        self.pipeline = pipeline or DocumentIngestionPipeline()
        self.documents = DocumentRepository(session)
        self.knowledge_bases = KnowledgeBaseRepository(session)

    async def process(
        self,
        user_id: UUID,
        knowledge_base_id: UUID,
        document_id: UUID,
    ) -> DocumentProcessingResponse:
        knowledge_base = await self.knowledge_bases.get_owned(knowledge_base_id, user_id)
        if knowledge_base is None:
            raise AppError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base was not found", 404)

        document = await self.documents.get_owned_for_update(
            document_id,
            user_id,
            knowledge_base_id,
        )
        if document is None:
            raise AppError("DOCUMENT_NOT_FOUND", "Document was not found", 404)
        if document.status == DocumentStatus.COMPLETED:
            return self._response(document)
        if document.status == DocumentStatus.PROCESSING:
            raise AppError("DOCUMENT_ALREADY_PROCESSING", "Document is already processing", 409)

        document.status = DocumentStatus.PROCESSING
        document.failure_reason = None
        await self.session.commit()

        try:
            content = await self.storage.get_object_bytes(document.storage_key)
            result = self.pipeline.run(
                content,
                document_id=document.id,
                filename=document.filename,
            )
            await self.vector_store.delete_document(knowledge_base_id, document.id)
            if result.chunks:
                vectors = await self.embedder.embed([chunk.text for chunk in result.chunks])
                await self.vector_store.upsert_chunks(knowledge_base_id, list(result.chunks), vectors)
            processed = await self.documents.get_owned(document.id, user_id, knowledge_base_id)
            if processed is None:
                raise AppError("DOCUMENT_NOT_FOUND", "Document was not found", 404)
            processed.status = DocumentStatus.COMPLETED
            processed.chunk_count = len(result.chunks)
            processed.failure_reason = None
            await self.session.commit()
            await self.session.refresh(processed)
            logger.info(
                "Document ingestion completed",
                extra={"document_id": str(document.id), "chunk_count": len(result.chunks)},
            )
            return self._response(processed)
        except AppError:
            raise
        except Exception as exc:
            await self.session.rollback()
            failed = await self.documents.get_owned(document.id, user_id, knowledge_base_id)
            if failed is not None:
                failure_reason = self._failure_reason(exc)
                failed.status = DocumentStatus.FAILED
                failed.chunk_count = 0
                failed.failure_reason = failure_reason
                await self.session.commit()
                logger.warning(
                    "Document ingestion failed",
                    extra={
                        "document_id": str(document.id),
                        "failure_code": failure_reason.split(":", maxsplit=1)[0],
                    },
                )
            raise AppError("DOCUMENT_PROCESSING_FAILED", "Document processing failed", 422) from exc

    @staticmethod
    def _failure_reason(error: Exception) -> str:
        if isinstance(error, DocumentProcessingError):
            return f"{error.code}: {error.message}"
        return "INGESTION_FAILED: document processing failed"

    @staticmethod
    def _response(document: Document) -> DocumentProcessingResponse:
        return DocumentProcessingResponse(
            document=DocumentResponse.model_validate(document),
            chunk_count=document.chunk_count,
        )
