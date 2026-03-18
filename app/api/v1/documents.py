import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.document_service import (
    create_document_record,
    generate_download_url,
    generate_upload_url,
    list_documents,
)

router = APIRouter()


class UploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=500)
    category: str


class DocumentCreateRequest(BaseModel):
    category: str
    filename: str
    original_filename: str
    file_size: int = Field(gt=0)
    mime_type: str
    s3_key: str
    stage: str | None = None


@router.post("/upload-url")
async def get_upload_url(
    company_id: uuid.UUID,
    data: UploadUrlRequest,
    current_user: User = Depends(get_current_user),
):
    result = generate_upload_url(company_id, data.filename, data.category)
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_document(
    company_id: uuid.UUID,
    data: DocumentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await create_document_record(db, company_id, data.model_dump(), current_user.id)
    return {
        "id": str(doc.id),
        "company_id": str(doc.company_id),
        "category": doc.category.value,
        "filename": doc.filename,
        "original_filename": doc.original_filename,
        "file_size": doc.file_size,
        "mime_type": doc.mime_type,
        "s3_key": doc.s3_key,
        "extraction_status": doc.extraction_status.value,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.get("")
async def list_documents_endpoint(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = await list_documents(db, company_id)
    return [
        {
            "id": str(d.id),
            "company_id": str(d.company_id),
            "category": d.category.value,
            "filename": d.filename,
            "original_filename": d.original_filename,
            "file_size": d.file_size,
            "mime_type": d.mime_type,
            "s3_key": d.s3_key,
            "stage": d.stage.value if d.stage else None,
            "extraction_status": d.extraction_status.value,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.get("/{document_id}/download-url")
async def get_download_url(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    from app.models.document import Document

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    url = generate_download_url(doc.s3_key)
    return {"download_url": url}
