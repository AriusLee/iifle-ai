"""
Seed complete demo data for Render deployment.
Creates: admin user, demo company (Loob Berhad), assessment with scores.
Then calls seed_demo_reports to create reports.

Run: python -m scripts.seed_demo
"""
import asyncio
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text

from app.database import async_session_factory, engine, Base
from app.models.user import User, UserRole, RoleType
from app.models.company import Company
from app.models.assessment import Assessment, AssessmentStatus, CapitalReadiness, ModuleScore, DimensionScore

# Fixed IDs so seed is idempotent
ADMIN_USER_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
DEMO_USER_ID = uuid.UUID("a0000000-0000-0000-0000-000000000002")
COMPANY_ID = uuid.UUID("d5f6ec35-6fdb-4da6-bf85-84bd572c25e7")
ASSESSMENT_ID = uuid.UUID("b0000000-0000-0000-0000-000000000001")


async def seed():
    from app.services.auth_service import hash_password

    async with async_session_factory() as session:
        # Check if already seeded
        existing = await session.execute(select(User).where(User.id == ADMIN_USER_ID))
        if existing.scalar_one_or_none():
            print("Demo data already seeded. Skipping.")
            return

        # --- Admin user ---
        admin = User(
            id=ADMIN_USER_ID,
            email="admin@iifle.com",
            password_hash=hash_password("admin123"),
            full_name="IIFLE Admin",
        )
        session.add(admin)
        await session.flush()

        admin_role = UserRole(
            user_id=ADMIN_USER_ID,
            company_id=None,
            role=RoleType.admin,
        )
        session.add(admin_role)

        # --- Demo client user ---
        demo_user = User(
            id=DEMO_USER_ID,
            email="demo@iifle.com",
            password_hash=hash_password("demo123"),
            full_name="Demo Client",
        )
        session.add(demo_user)
        await session.flush()

        # --- Loob Berhad company ---
        company = Company(
            id=COMPANY_ID,
            legal_name="Loob Holding Sdn Bhd",
            brand_name="Loob Berhad (Tealive)",
            registration_number="201401001234",
            date_of_incorporation=date(2014, 1, 15),
            company_type="sdn_bhd",
            primary_industry="Food & Beverage",
            sub_industry="Lifestyle Beverages / QSR",
            country="Malaysia",
            website="https://www.loob.com.my",
            brief_description="Southeast Asia's largest lifestyle beverage company. Operates Tealive (831 outlets), Bask Bear Coffee (135 outlets), SodaXpress, and WonderBrew across 11 countries with 1,087+ total outlets.",
            enterprise_stage="expansion",
            status="active",
        )
        session.add(company)
        await session.flush()

        # Assign roles
        advisor_role = UserRole(
            user_id=ADMIN_USER_ID,
            company_id=COMPANY_ID,
            role=RoleType.advisor,
        )
        client_role = UserRole(
            user_id=DEMO_USER_ID,
            company_id=COMPANY_ID,
            role=RoleType.client,
        )
        session.add_all([advisor_role, client_role])

        # --- Assessment with module scores ---
        assessment = Assessment(
            id=ASSESSMENT_ID,
            company_id=COMPANY_ID,
            trigger_stage="stage_2",
            status=AssessmentStatus.approved,
            overall_score=Decimal("78.50"),
            overall_rating="Strong",
            enterprise_stage_classification="Expansion — Pre-IPO",
            capital_readiness=CapitalReadiness.green,
        )
        session.add(assessment)
        await session.flush()

        # Module scores
        modules = [
            {
                "module_number": 1,
                "module_name": "Gene Structure",
                "total_score": Decimal("82.00"),
                "rating": "Strong",
                "weight": Decimal("0.200"),
                "dimensions": [
                    ("Founder & Key Person", Decimal("85.00"), Decimal("0.300")),
                    ("Industry & Market", Decimal("78.00"), Decimal("0.200")),
                    ("Business Model Clarity", Decimal("80.00"), Decimal("0.200")),
                    ("Replicability & Scalability", Decimal("88.00"), Decimal("0.150")),
                    ("Organisation & Culture", Decimal("75.00"), Decimal("0.150")),
                ],
            },
            {
                "module_number": 2,
                "module_name": "Business Model Structure",
                "total_score": Decimal("79.00"),
                "rating": "Developing → Mature",
                "weight": Decimal("0.200"),
                "dimensions": [
                    ("Revenue Model", Decimal("82.00"), Decimal("0.250")),
                    ("Customer Analysis", Decimal("80.00"), Decimal("0.200")),
                    ("Cost Structure", Decimal("75.00"), Decimal("0.200")),
                    ("Competitive Advantage", Decimal("78.00"), Decimal("0.200")),
                    ("Scalability", Decimal("80.00"), Decimal("0.150")),
                ],
            },
            {
                "module_number": 3,
                "module_name": "Valuation Structure",
                "total_score": Decimal("76.00"),
                "rating": "Developing",
                "weight": Decimal("0.200"),
                "dimensions": [
                    ("Financial Performance", Decimal("78.00"), Decimal("0.300")),
                    ("Valuation Metrics", Decimal("74.00"), Decimal("0.300")),
                    ("Growth Trajectory", Decimal("80.00"), Decimal("0.200")),
                    ("Risk Assessment", Decimal("72.00"), Decimal("0.200")),
                ],
            },
            {
                "module_number": 4,
                "module_name": "Financing Structure",
                "total_score": Decimal("75.00"),
                "rating": "Developing",
                "weight": Decimal("0.200"),
                "dimensions": [
                    ("Capital Structure", Decimal("76.00"), Decimal("0.300")),
                    ("Funding History", Decimal("80.00"), Decimal("0.250")),
                    ("Use of Proceeds", Decimal("74.00"), Decimal("0.250")),
                    ("Investor Readiness", Decimal("70.00"), Decimal("0.200")),
                ],
            },
            {
                "module_number": 5,
                "module_name": "Exit Mechanism",
                "total_score": Decimal("80.00"),
                "rating": "Strong",
                "weight": Decimal("0.100"),
                "dimensions": [
                    ("Exit Strategy Clarity", Decimal("85.00"), Decimal("0.350")),
                    ("Market Conditions", Decimal("78.00"), Decimal("0.300")),
                    ("Timeline Feasibility", Decimal("76.00"), Decimal("0.350")),
                ],
            },
            {
                "module_number": 6,
                "module_name": "Listing Standards",
                "total_score": Decimal("77.00"),
                "rating": "Developing → Strong",
                "weight": Decimal("0.100"),
                "dimensions": [
                    ("Regulatory Compliance", Decimal("80.00"), Decimal("0.350")),
                    ("Governance Standards", Decimal("75.00"), Decimal("0.350")),
                    ("Disclosure Readiness", Decimal("76.00"), Decimal("0.300")),
                ],
            },
        ]

        for mod in modules:
            ms = ModuleScore(
                assessment_id=ASSESSMENT_ID,
                module_number=mod["module_number"],
                module_name=mod["module_name"],
                total_score=mod["total_score"],
                rating=mod["rating"],
                weight=mod["weight"],
                scored_at=datetime.now(timezone.utc),
            )
            session.add(ms)
            await session.flush()

            for idx, (dim_name, score, weight) in enumerate(mod["dimensions"], 1):
                ds = DimensionScore(
                    module_score_id=ms.id,
                    dimension_number=idx,
                    dimension_name=dim_name,
                    score=score,
                    weight=weight,
                )
                session.add(ds)

        await session.commit()
        print("Demo data seeded successfully!")
        print(f"  Admin: admin@iifle.com / admin123")
        print(f"  Client: demo@iifle.com / demo123")
        print(f"  Company: Loob Berhad ({COMPANY_ID})")

    # Now seed the reports
    from scripts.seed_demo_reports import seed as seed_reports
    await seed_reports()


if __name__ == "__main__":
    asyncio.run(seed())
