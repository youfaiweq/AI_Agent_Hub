"""Document metadata and object-storage service."""

import logging
from io import BytesIO
from pathlib import PurePath
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.integrations.minio import MinioAdapter
from app.models.document import Document, DocumentStatus
from app.rag.vectorstores.qdrant import QdrantVectorStore
from app.repositories.documents import DocumentRepository
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.document import DocumentListResponse, DocumentResponse

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


class DocumentService:
    """Coordinate document validation, metadata, and object storage."""

    def __init__(
        self,
        session: AsyncSession,
        storage: MinioAdapter,
        vector_store: QdrantVectorStore,
    ) -> None:
        self.session = session
        self.storage = storage
        self.vector_store = vector_store
        self.documents = DocumentRepository(session)
        self.knowledge_bases = KnowledgeBaseRepository(session)

    def _validate_file(self, filename: str, content: bytes) -> tuple[str, str]:
        settings = get_settings()
        safe_filename = PurePath(filename).name
        extension = PurePath(safe_filename).suffix.lower()
        content_type = ALLOWED_EXTENSIONS.get(extension)
        if content_type is None:
            raise AppError(
                "UNSUPPORTED_DOCUMENT_TYPE",
                "Only PDF, TXT, and Markdown files are supported",
                415,
            )
        if len(content) == 0:
            raise AppError("EMPTY_DOCUMENT", "The uploaded document is empty", 400)
        if len(content) > settings.max_document_size_bytes:
            raise AppError("DOCUMENT_TOO_LARGE", "The uploaded document is too large", 413)
        return safe_filename, content_type

    async def upload(
        self,
        user_id: UUID,
        knowledge_base_id: UUID,
        filename: str | None,
        content: bytes,
    ) -> Document:
        if not filename:
            raise AppError("INVALID_FILENAME", "A document filename is required", 400)
        knowledge_base = await self.knowledge_bases.get_owned(knowledge_base_id, user_id)
        if knowledge_base is None:
            raise AppError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base was not found", 404)
        safe_filename, content_type = self._validate_file(filename, content)
        document_id = UUID(int=0)
        storage_key = ""
        object_uploaded = False
        document: Document | None = None
        try:
            document = await self.documents.create(
                user_id,
                knowledge_base_id,
                safe_filename,
                content_type,
                len(content),
                "pending",
            )
            document_id = document.id
            storage_key = f"documents/{user_id}/{knowledge_base_id}/{document_id}{PurePath(safe_filename).suffix.lower()}"
            document.storage_key = storage_key
            await self.session.commit()

            await self.storage.ensure_bucket()
            await self.storage.put_object(
                storage_key,
                BytesIO(content),
                len(content),
                content_type,
            )
            object_uploaded = True

            document.status = DocumentStatus.UPLOADED
            document.failure_reason = None
            await self.session.commit()
            await self.session.refresh(document)
            return document
        except AppError:
            raise
        except Exception as exc:
            await self.session.rollback()
            if object_uploaded and storage_key:
                try:
                    await self.storage.remove_object(storage_key)
                except Exception:
                    logger.exception("Failed to remove orphaned document object")
            if document_id.int != 0:
                failed = await self.documents.get_owned(document_id, user_id, knowledge_base_id)
                if failed is not None:
                    failed.status = DocumentStatus.FAILED
                    failed.failure_reason = "object storage upload failed"
                    await self.session.commit()
            raise AppError("DOCUMENT_UPLOAD_FAILED", "Document upload failed", 502) from exc

    async def list(
        self,
        user_id: UUID,
        knowledge_base_id: UUID,
        page: int,
        page_size: int,
    ) -> DocumentListResponse:
        knowledge_base = await self.knowledge_bases.get_owned(knowledge_base_id, user_id)
        if knowledge_base is None:
            raise AppError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base was not found", 404)
        total = await self.documents.count_owned(user_id, knowledge_base_id)
        items = await self.documents.list_owned(
            user_id,
            knowledge_base_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return DocumentListResponse(
            items=[DocumentResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get(self, user_id: UUID, knowledge_base_id: UUID, document_id: UUID) -> Document:
        knowledge_base = await self.knowledge_bases.get_owned(knowledge_base_id, user_id)
        if knowledge_base is None:
            raise AppError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base was not found", 404)
        document = await self.documents.get_owned(document_id, user_id, knowledge_base_id)
        if document is None:
            raise AppError("DOCUMENT_NOT_FOUND", "Document was not found", 404)
        return document

    async def delete(self, user_id: UUID, knowledge_base_id: UUID, document_id: UUID) -> None:
        document = await self.get(user_id, knowledge_base_id, document_id)
        try:
            await self.vector_store.delete_document(knowledge_base_id, document.id)
            await self.storage.remove_object(document.storage_key)
        except Exception as exc:
            raise AppError("DOCUMENT_STORAGE_DELETE_FAILED", "Document deletion failed", 502) from exc
        await self.documents.delete(document)
        await self.session.commit()
