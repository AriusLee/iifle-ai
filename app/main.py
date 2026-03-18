import logging
from contextlib import asynccontextmanager

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1.router import api_router

logger = logging.getLogger(__name__)


def _ensure_s3_bucket():
    """Create the S3 bucket on startup if it doesn't exist (for MinIO local dev)."""
    try:
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        try:
            client.head_bucket(Bucket=settings.S3_BUCKET)
            logger.info("S3 bucket '%s' already exists", settings.S3_BUCKET)
        except ClientError:
            client.create_bucket(Bucket=settings.S3_BUCKET)
            logger.info("Created S3 bucket '%s'", settings.S3_BUCKET)
    except Exception as e:
        logger.warning("Could not ensure S3 bucket exists: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_s3_bucket()
    yield


app = FastAPI(
    title="IIFLE API",
    description="IIFLE AI Capital Structure Platform API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "iifle-api"}
