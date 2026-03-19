import pathlib
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
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

UPLOAD_DIR = pathlib.Path(__file__).resolve().parents[3] / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def _serialize_doc(d):
    return {
        "id": str(d.id),
        "company_id": str(d.company_id),
        "category": d.category.value,
        "filename": d.filename,
        "original_filename": d.original_filename,
        "file_size": d.file_size,
        "mime_type": d.mime_type,
        "s3_key": d.s3_key,
        "stage": d.stage.value if d.stage else None,
        "extraction_status": d.extraction_status.value if d.extraction_status else "pending",
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


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
    try:
        result = generate_upload_url(company_id, data.filename, data.category)
        return result
    except Exception:
        # S3 not available — return a local upload hint
        s3_key = f"companies/{company_id}/{data.category}/{uuid.uuid4().hex}_{data.filename}"
        return {"upload_url": f"/api/v1/companies/{company_id}/documents/upload", "s3_key": s3_key}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    company_id: uuid.UUID,
    file: UploadFile = File(...),
    category: str = Form("other"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Direct file upload — stores locally when S3 is not available."""
    company_dir = UPLOAD_DIR / str(company_id) / category
    company_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex
    safe_name = file.filename.replace("/", "_").replace("\\", "_") if file.filename else "unnamed"
    stored_name = f"{file_id}_{safe_name}"
    file_path = company_dir / stored_name

    content = await file.read()
    file_path.write_bytes(content)

    s3_key = f"companies/{company_id}/{category}/{stored_name}"

    doc = await create_document_record(
        db,
        company_id,
        {
            "category": category,
            "filename": stored_name,
            "original_filename": file.filename or "unnamed",
            "file_size": len(content),
            "mime_type": file.content_type or "application/octet-stream",
            "s3_key": s3_key,
        },
        current_user.id,
    )
    await db.commit()

    return _serialize_doc(doc)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_document(
    company_id: uuid.UUID,
    data: DocumentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await create_document_record(db, company_id, data.model_dump(), current_user.id)
    await db.commit()
    return _serialize_doc(doc)


@router.get("")
async def list_documents_endpoint(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = await list_documents(db, company_id)
    return [_serialize_doc(d) for d in docs]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select, delete as sql_delete
    from app.models.document import Document

    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.company_id == company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Delete local file if exists
    local_path = UPLOAD_DIR / str(company_id) / doc.category.value / doc.filename
    if local_path.exists():
        local_path.unlink()

    await db.delete(doc)
    await db.commit()


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
        select(Document).where(Document.id == document_id, Document.company_id == company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Try S3 first, fall back to local
    try:
        url = generate_download_url(doc.s3_key)
        return {"download_url": url}
    except Exception:
        return {"download_url": f"/api/v1/companies/{company_id}/documents/{document_id}/file"}


@router.get("/{document_id}/file")
async def download_file(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve locally stored file directly."""
    from fastapi.responses import FileResponse
    from sqlalchemy import select
    from app.models.document import Document

    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.company_id == company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    local_path = UPLOAD_DIR / str(company_id) / doc.category.value / doc.filename
    if not local_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    return FileResponse(
        path=str(local_path),
        filename=doc.original_filename,
        media_type=doc.mime_type,
    )


@router.post("/{document_id}/extract", status_code=status.HTTP_202_ACCEPTED)
async def extract_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger PDF extraction for a document (audited financial report).

    Extracts financial data and maps it to Stage 2 schema fields.
    Results are stored in document.extracted_data.
    """
    from sqlalchemy import select as sa_select
    from app.models.document import Document

    result = await db.execute(
        sa_select(Document).where(Document.id == document_id, Document.company_id == company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.mime_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents can be extracted",
        )

    # Read file bytes
    local_path = UPLOAD_DIR / str(company_id) / doc.category.value / doc.filename
    if not local_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    file_bytes = local_path.read_bytes()

    # Update status
    doc.extraction_status = "processing"
    await db.commit()

    async def _run_extraction():
        from app.database import async_session_factory
        from app.services.ai.document_parser import PDFExtractionService, map_extraction_to_stage2
        from app.services.ai.provider import get_ai_client
        from sqlalchemy import update as sql_update

        try:
            async with async_session_factory() as session:
                client = get_ai_client()
                extractor = PDFExtractionService(ai_client=client)
                extracted = await extractor.extract(file_bytes, filename=doc.original_filename)

                # Map to Stage 2 schema
                stage2_data = map_extraction_to_stage2(extracted)
                extracted["stage2_mapped"] = stage2_data

                await session.execute(
                    sql_update(Document)
                    .where(Document.id == document_id)
                    .values(
                        extraction_status="completed",
                        extracted_data=extracted,
                    )
                )
                await session.commit()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("PDF extraction failed: %s", exc)
            try:
                async with async_session_factory() as err_session:
                    await err_session.execute(
                        sql_update(Document)
                        .where(Document.id == document_id)
                        .values(extraction_status="failed")
                    )
                    await err_session.commit()
            except Exception:
                pass

    background_tasks.add_task(_run_extraction)

    return {
        "status": "processing",
        "document_id": str(document_id),
        "message": "PDF extraction started. Check document status for results.",
    }


@router.get("/{document_id}/extracted")
async def get_extracted_data(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the extracted data from a processed document."""
    from sqlalchemy import select as sa_select
    from app.models.document import Document

    result = await db.execute(
        sa_select(Document).where(Document.id == document_id, Document.company_id == company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return {
        "document_id": str(document_id),
        "extraction_status": doc.extraction_status.value if doc.extraction_status else "pending",
        "extracted_data": doc.extracted_data,
    }
