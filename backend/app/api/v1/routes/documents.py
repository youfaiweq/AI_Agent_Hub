"""Document metadata and upload endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.core.dependencies import SessionDependency, StorageDependency, UserDependency
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.documents import DocumentService

router = APIRouter(prefix="/knowledge-bases/{knowledge_base_id}/documents", tags=["documents"])
PageDependency = Annotated[int, Query(ge=1, description="One-based page number")]
PageSizeDependency = Annotated[int, Query(ge=1, le=100, description="Items per page")]
UploadFileDependency = Annotated[UploadFile, File(...)]


def get_document_service(
    session: SessionDependency,
    storage: StorageDependency,
) -> DocumentService:
    return DocumentService(session, storage)


ServiceDependency = Annotated[DocumentService, Depends(get_document_service)]


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    knowledge_base_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
    file: UploadFileDependency,
) -> DocumentResponse:
    try:
        content = await file.read()
        document = await service.upload(user.id, knowledge_base_id, file.filename, content)
        return DocumentResponse.model_validate(document)
    finally:
        await file.close()


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    knowledge_base_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
    page: PageDependency = 1,
    page_size: PageSizeDependency = 20,
) -> DocumentListResponse:
    return await service.list(user.id, knowledge_base_id, page, page_size)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
) -> DocumentResponse:
    document = await service.get(user.id, knowledge_base_id, document_id)
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    user: UserDependency,
    service: ServiceDependency,
) -> Response:
    await service.delete(user.id, knowledge_base_id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
