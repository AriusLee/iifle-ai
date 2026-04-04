import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.user import RoleType, UserRole
from app.schemas.company import CompanyCreate, CompanyUpdate


async def _user_is_admin(db: AsyncSession, user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role == RoleType.admin,
            UserRole.company_id.is_(None),
        )
    )
    return result.scalar_one_or_none() is not None


async def _user_has_company_access(db: AsyncSession, user_id: uuid.UUID, company_id: uuid.UUID) -> bool:
    return True


async def create_company(db: AsyncSession, data: CompanyCreate, user_id: uuid.UUID) -> Company:
    company = Company(**data.model_dump())
    db.add(company)
    await db.flush()

    advisor_role = UserRole(
        user_id=user_id,
        company_id=company.id,
        role=RoleType.advisor,
    )
    db.add(advisor_role)
    await db.flush()

    return company


async def get_company(db: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID) -> Company:
    if not await _user_has_company_access(db, user_id, company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this company",
        )

    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    return company


async def list_companies(db: AsyncSession, user_id: uuid.UUID) -> list[Company]:
    if await _user_is_admin(db, user_id):
        result = await db.execute(select(Company).order_by(Company.created_at.desc()))
        return list(result.scalars().all())

    result = await db.execute(
        select(Company)
        .join(UserRole, UserRole.company_id == Company.id)
        .where(UserRole.user_id == user_id)
        .order_by(Company.created_at.desc())
    )
    return list(result.scalars().all())


async def update_company(
    db: AsyncSession, company_id: uuid.UUID, data: CompanyUpdate, user_id: uuid.UUID
) -> Company:
    company = await get_company(db, company_id, user_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    await db.flush()
    return company
