from fastapi import APIRouter

from app.api.v1.assessments import router as assessments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.auto_intake import router as auto_intake_router
from app.api.v1.chat import router as chat_router
from app.api.v1.companies import router as companies_router
from app.api.v1.documents import router as documents_router
from app.api.v1.intake import router as intake_router
from app.api.v1.reports import router as reports_router
from app.api.v1.research import router as research_router
from app.api.v1.settings import router as settings_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(settings_router, prefix="/settings", tags=["Settings"])
api_router.include_router(companies_router, prefix="/companies", tags=["Companies"])
api_router.include_router(intake_router, prefix="/companies/{company_id}/intake", tags=["Intake"])
api_router.include_router(documents_router, prefix="/companies/{company_id}/documents", tags=["Documents"])
api_router.include_router(assessments_router, prefix="/companies/{company_id}/assessments", tags=["Assessments"])
api_router.include_router(chat_router, prefix="/companies/{company_id}/chat", tags=["Chat"])
api_router.include_router(reports_router, prefix="/companies/{company_id}/reports", tags=["Reports"])
api_router.include_router(research_router, prefix="/companies/{company_id}/research", tags=["Research"])
api_router.include_router(auto_intake_router, prefix="/companies/{company_id}/auto-intake", tags=["Auto Intake"])
