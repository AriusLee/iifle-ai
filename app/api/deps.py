import uuid
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.user import RoleType, User, UserRole
from app.services.auth_service import decode_token

security = HTTPBearer()


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token_data = decode_token(credentials.credentials)
    user_id = uuid.UUID(token_data.sub)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return user


def require_role(roles: list[str]) -> Callable:
    async def role_checker(
        company_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # Check for global admin role
        admin_result = await db.execute(
            select(UserRole).where(
                UserRole.user_id == current_user.id,
                UserRole.role == RoleType.admin,
                UserRole.company_id.is_(None),
            )
        )
        if admin_result.scalar_one_or_none():
            return current_user

        # Check for company-specific role
        role_enums = [RoleType(r) for r in roles]
        result = await db.execute(
            select(UserRole).where(
                UserRole.user_id == current_user.id,
                UserRole.company_id == company_id,
                UserRole.role.in_(role_enums),
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this company",
            )
        return current_user

    return role_checker
