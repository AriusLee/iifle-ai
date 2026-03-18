import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
from app.services.company_service import (
    create_company,
    get_company,
    list_companies,
    update_company,
)

router = APIRouter()


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company_endpoint(
    data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = await create_company(db, data, current_user.id)
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
