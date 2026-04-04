"""
Seed minimal demo data — creates admin user only.
The old Loob Berhad intake/assessment/report seeds are removed.
Companies and diagnostics are now created via the app.

Run: python -m scripts.seed_demo
"""
import asyncio
import uuid

from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User, UserRole, RoleType

ADMIN_USER_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")


async def seed():
    async with async_session_factory() as db:
        # Check if admin already exists
        result = await db.execute(select(User).where(User.id == ADMIN_USER_ID))
        if result.scalar_one_or_none():
            print("Admin user already exists, skipping seed.")
            return

        # Create admin user (password: Admin123!)
        import bcrypt
        pw_hash = bcrypt.hashpw(b"Admin123!", bcrypt.gensalt()).decode()

        admin = User(
            id=ADMIN_USER_ID,
            email="admin@iifle.com",
            password_hash=pw_hash,
            full_name="IIFLE Admin",
            is_active=True,
        )
        db.add(admin)

        # Global admin role
        db.add(UserRole(
            id=uuid.uuid4(),
            user_id=ADMIN_USER_ID,
            company_id=None,
            role=RoleType.admin,
        ))

        await db.commit()
        print("Seeded admin user: admin@iifle.com / Admin123!")


if __name__ == "__main__":
    asyncio.run(seed())
