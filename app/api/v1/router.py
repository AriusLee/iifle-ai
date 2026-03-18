from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.companies import router as companies_router
from app.api.v1.documents import router as documents_router
from app.api.v1.intake import router as intake_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(companies_router, prefix="/companies", tags=["Companies"])
api_router.include_router(intake_router, prefix="/companies/{company_id}/intake", tags=["Intake"])
api_router.include_router(documents_router, prefix="/companies/{company_id}/documents", tags=["Documents"])
