import asyncio
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.database import async_session_factory
from app.models.user import User
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
from app.services.company_service import (
    create_company,
    get_company,
    list_companies,
    update_company,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _run_dd_research(company_id: uuid.UUID) -> None:
    """Background task: run due diligence research for a newly created company."""
    from app.services.ai.research import ResearchService
    from app.config import settings

    from app.config import settings as current_settings
    # Check any AI provider is configured
    if not (current_settings.ANTHROPIC_API_KEY or current_settings.GROQ_API_KEY or current_settings.GEMINI_API_KEY):
        logger.info("Skipping DD research — no AI API key configured")
        return

    try:
        async with async_session_factory() as db:
            service = ResearchService(db)
            research = await service.run_full_research(company_id)
            await db.commit()
            logger.info("DD research completed for company %s — status: %s", company_id, research.status)
    except Exception as exc:
        logger.exception("DD research background task failed for %s: %s", company_id, exc)
        # Research service already saves failed status internally


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company_endpoint(
    data: CompanyCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = await create_company(db, data, current_user.id)

    # Commit NOW so background tasks can find the company in DB
    await db.commit()

    # Auto-trigger DD research in background (uses its own DB session)
    background_tasks.add_task(_run_dd_research, company.id)

    return company


@router.get("", response_model=list[CompanyResponse])
async def list_companies_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    companies = await list_companies(db, current_user.id)
    return companies


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company_endpoint(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = await get_company(db, company_id, current_user.id)
    return company


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company_endpoint(
    company_id: uuid.UUID,
    data: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = await update_company(db, company_id, data, current_user.id)
    return company
