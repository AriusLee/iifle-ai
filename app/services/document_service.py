import uuid
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, DocumentCategory, DocumentStage


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4"),
    )


def generate_upload_url(company_id: uuid.UUID, filename: str, category: str) -> dict:
    s3_key = f"companies/{company_id}/{category}/{uuid.uuid4().hex}_{filename}"
    client = _get_s3_client()
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": s3_key,
        },
        ExpiresIn=3600,
    )
    return {"upload_url": upload_url, "s3_key": s3_key}


async def create_document_record(
    db: AsyncSession,
    company_id: uuid.UUID,
    data: dict,
    user_id: uuid.UUID,
) -> Document:
    doc = Document(
        company_id=company_id,
        category=DocumentCategory(data["category"]),
        filename=data["filename"],
        original_filename=data["original_filename"],
        file_size=data["file_size"],
        mime_type=data["mime_type"],
        s3_key=data["s3_key"],
        stage=DocumentStage(data["stage"]) if data.get("stage") else None,
        uploaded_by=user_id,
    )
    db.add(doc)
    await db.flush()
    return doc


async def list_documents(db: AsyncSession, company_id: uuid.UUID) -> list[Document]:
    result = await db.execute(
        select(Document)
        .where(Document.company_id == company_id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


def generate_download_url(s3_key: str) -> str:
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": s3_key,
        },
        ExpiresIn=3600,
    )
