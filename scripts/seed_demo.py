"""
Seed complete demo data for Render deployment.
Creates: admin user, demo company (Loob Berhad), intake stages, assessment with scores.
Then calls seed_demo_reports to create reports.

Run: python -m scripts.seed_demo
"""
import asyncio
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User, UserRole, RoleType
from app.models.company import Company
from app.models.intake import IntakeStage, IntakeStageNumber, IntakeStatus
from app.models.assessment import Assessment, AssessmentStatus, CapitalReadiness, ModuleScore, DimensionScore

# Fixed IDs so seed is idempotent
ADMIN_USER_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
DEMO_USER_ID = uuid.UUID("a0000000-0000-0000-0000-000000000002")
COMPANY_ID = uuid.UUID("d5f6ec35-6fdb-4da6-bf85-84bd572c25e7")
ASSESSMENT_ID = uuid.UUID("b0000000-0000-0000-0000-000000000001")


# ==========================================================================
# Stage 1 intake data — Loob Berhad (Tealive)
# ==========================================================================
STAGE_1_DATA = {
    "registration": {
        "legal_name": "Loob Holding Sdn Bhd",
        "registration_number": "201401001234",
        "date_of_incorporation": "2014-01-15",
        "company_type": "sdn_bhd",
        "registered_address": "Level 10, Menara Hap Seng 2, Plaza Hap Seng, Jalan P. Ramlee, 50250 Kuala Lumpur",
        "operating_address": "Level 10, Menara Hap Seng 2, Plaza Hap Seng, Jalan P. Ramlee, 50250 Kuala Lumpur",
        "website": "https://www.loob.com.my",
        "country_of_incorporation": "malaysia",
        "other_jurisdictions": ["singapore", "vietnam", "philippines", "brunei", "cambodia", "myanmar"]
    },
    "industry": {
        "primary_industry": "fnb",
        "sub_industry": "Lifestyle Beverages / QSR",
        "msic_code": "56101",
        "brief_description": "Southeast Asia's largest lifestyle beverage company operating Tealive, Bask Bear Coffee, SodaXpress, and WonderBrew across 11 countries with 1,087+ outlets."
    },
    "scale": {
        "total_employees": 2000,
        "num_branches": 1087,
        "operating_since": "2010",
        "geographic_coverage": "regional",
        "countries_of_operation": ["Malaysia", "Singapore", "Vietnam", "Philippines", "Brunei", "Cambodia", "Myanmar", "Australia", "UK", "India", "Sri Lanka"]
    },
    "founder": {
        "name": "Bryan Loo Woi Lip",
        "age": 40,
        "nationality": "Malaysian",
        "highest_education": "bachelors",
        "education_institution": "Monash University",
        "years_in_industry": 16,
        "years_business_experience": 16,
        "previous_companies_founded": 2,
        "previous_exit_experience": False,
        "emba_status": "not_enrolled",
        "emba_program": None
    },
    "co_founders": [
        {
            "name": "Loo Chee Leng",
            "role": "COO",
            "ownership_pct": 10,
            "years_with_company": 14,
            "expertise": "Operations & Supply Chain"
        }
    ],
    "management_team": [
        {"position": "CEO & Founder", "name": "Bryan Loo Woi Lip", "years_in_role": 14, "years_with_company": 14, "background": "Serial F&B entrepreneur, EY Emerging Entrepreneur 2013/2014"},
        {"position": "COO", "name": "Loo Chee Leng", "years_in_role": 10, "years_with_company": 14, "background": "Operations management, supply chain optimization"},
        {"position": "CFO", "name": "Ahmad Rizal", "years_in_role": 2, "years_with_company": 2, "background": "Ex-Big4 audit, IPO experience with 3 Bursa listings"},
        {"position": "CMO", "name": "Sarah Tan", "years_in_role": 3, "years_with_company": 5, "background": "Digital marketing, brand strategy, ex-Unilever"},
        {"position": "CTO / Digital Director", "name": "James Wong", "years_in_role": 1, "years_with_company": 1, "background": "Digital transformation, loyalty platforms, ex-Grab"}
    ],
    "succession": {
        "has_succession_plan": True,
        "management_stable_3yr": True,
        "key_person": "Bryan Loo Woi Lip",
        "key_person_contingency": "COO Loo Chee Leng designated as interim CEO; board includes 2 Creador-appointed independent directors"
    },
    "products": [
        {"name": "Tealive", "type": "beverage", "revenue_share_pct": 55, "gross_margin_pct": 65, "growth_trend": "stable"},
        {"name": "Bask Bear Coffee", "type": "beverage", "revenue_share_pct": 25, "gross_margin_pct": 60, "growth_trend": "growing"},
        {"name": "SodaXpress", "type": "beverage", "revenue_share_pct": 8, "gross_margin_pct": 55, "growth_trend": "growing"},
        {"name": "WonderBrew Kombucha", "type": "beverage", "revenue_share_pct": 4, "gross_margin_pct": 50, "growth_trend": "growing"},
        {"name": "Franchise Fees & Royalties", "type": "service", "revenue_share_pct": 8, "gross_margin_pct": 90, "growth_trend": "stable"}
    ],
    "product_competitiveness": {
        "differentiation": "strong",
        "ip_type": "trademark",
        "num_patents": 0,
        "rd_spending": 2.5,
        "certifications": ["Halal (JAKIM)", "ISO 22000", "HACCP", "MeSTI"]
    },
    "customers": {
        "customer_type": "b2c",
        "active_customers": 5000000,
        "top1_revenue_pct": 0,
        "top5_revenue_pct": 0,
        "top10_revenue_pct": 0,
        "avg_relationship_length": 3,
        "retention_rate": 65,
        "long_term_contracts": False
    },
    "supply_chain": {
        "num_key_suppliers": 15,
        "single_supplier_dependency": False,
        "supplier_agreements_documented": True
    },
    "revenue_model": {
        "description": "Hybrid corporate-franchise retail model with company-operated and franchise outlets generating revenue through direct beverage sales, franchise fees, royalties, and supply chain margin.",
        "model_types": ["retail_sales", "franchise_fees", "royalties"],
        "recurring_revenue_pct": 35,
        "is_seasonal": False,
        "peak_months": []
    },
    "scalability": {
        "replicable": True,
        "documented_sops": True,
        "central_facility": True,
        "training_weeks": 4,
        "expansion_plan_3yr": "Target 1,500+ outlets by 2027. Expand Bask Bear to 400 outlets. Enter Indonesia and Thailand markets."
    },
    "competitive_landscape": {
        "top3_competitors": ["Mixue", "ZUS Coffee", "Gong Cha"],
        "estimated_market_share": 18,
        "segment_leader": True,
        "segment_leader_detail": "Largest lifestyle beverage company in Malaysia by outlet count (1,087 vs #2 at ~500)",
        "competitive_advantages": ["Scale & distribution network", "Multi-brand portfolio", "Proven franchise model", "2.8M digital loyalty members", "Halal certification across all brands"],
        "barriers_to_entry": "moderate"
    },
    "financials": {
        "fy_end_month": 12,
        "year_t2": {"year": 2022, "revenue": 420000000, "cogs": 168000000, "operating_expenses": 189000000, "pbt": 63000000, "pat": 48000000},
        "year_t1": {"year": 2023, "revenue": 510000000, "cogs": 199000000, "operating_expenses": 224000000, "pbt": 87000000, "pat": 66000000},
        "year_t0": {"year": 2024, "revenue": 592000000, "cogs": 225000000, "operating_expenses": 260000000, "pbt": 107000000, "pat": 82000000}
    },
    "balance_sheet": {
        "cash": 85000000,
        "receivables": 35000000,
        "inventory": 28000000,
        "current_assets": 165000000,
        "fixed_assets": 180000000,
        "total_assets": 420000000,
        "current_liabilities": 95000000,
        "bank_borrowings": 45000000,
        "total_liabilities": 160000000,
        "paid_up_capital": 50000000
    },
    "cash_flow": {
        "cash_flow_positive": True,
        "monthly_opex": 22000000,
        "current_cash": 85000000,
        "customer_pay_days": 0,
        "supplier_pay_days": 45
    },
    "audit_status": {
        "has_audited": True,
        "years_audited": 10,
        "auditor_name": "Deloitte Malaysia",
        "aob_registered": True,
        "accounting_standard": "MFRS"
    },
    "growth_plans": {
        "revenue_target_yr1": 680000000,
        "revenue_target_yr3": 900000000,
        "revenue_target_yr5": 1200000000,
        "growth_strategy": "Multi-brand outlet expansion across SEA, with Bask Bear as primary growth engine. Digital transformation via loyalty platform monetization.",
        "biggest_obstacle": "Intense competition from low-cost entrants like Mixue and market saturation in tier-1 Malaysian cities"
    },
    "capital_intentions": {
        "looking_to_raise": True,
        "raise_amount": 300000000,
        "raise_purpose": "IPO on Bursa Malaysia Main Market to fund regional expansion, brand development, and digital infrastructure",
        "prior_funding": True,
        "prior_amount": 230000000
    },
    "ipo_aspiration": {
        "interest": "actively_planning",
        "preferred_markets": ["Bursa Main Market"],
        "engaged_advisors": True,
        "biggest_barrier": "Market timing and achieving target valuation multiple"
    },
    "exit_preference": {
        "long_term_goal": "ipo",
        "liquidity_timeline": "12_to_24_months"
    },
    "org_maturity": {
        "formal_org_chart": True,
        "num_departments": 10,
        "performance_reviews": "semi_annual",
        "training_program": True,
        "turnover_rate": 35,
        "hr_policies": True
    },
    "culture": {
        "documented_vmv": True,
        "vision": "To be the world's leading lifestyle beverage company",
        "mission": "Delivering happiness through innovative beverages and exceptional experiences",
        "core_values": "People is Everything, Innovation, Integrity, Excellence, Customer First"
    }
}

# ==========================================================================
# Stage 2 intake data — Financial deep dive
# ==========================================================================
STAGE_2_DATA = {
    "section_a_audit": {
        "auditor_name": "Deloitte Malaysia",
        "audit_firm_tier": "big4",
        "aob_registered": True,
        "accounting_standard": "MFRS",
        "audit_opinion_t0": "unqualified",
        "audit_opinion_t1": "unqualified",
        "audit_opinion_t2": "unqualified",
        "management_letter_issues": False
    },
    "section_b_income": {
        "revenue_streams": [
            {"name": "Tealive Corporate Stores", "t0": 325600000, "t1": 280500000, "t2": 231000000},
            {"name": "Bask Bear Coffee", "t0": 148000000, "t1": 102000000, "t2": 63000000},
            {"name": "SodaXpress", "t0": 47360000, "t1": 40800000, "t2": 33600000},
            {"name": "WonderBrew Kombucha", "t0": 23680000, "t1": 20400000, "t2": 16800000},
            {"name": "Franchise Fees & Royalties", "t0": 47360000, "t1": 66300000, "t2": 75600000}
        ],
        "total_revenue": {"t0": 592000000, "t1": 510000000, "t2": 420000000},
        "cogs": {"t0": 225000000, "t1": 199000000, "t2": 168000000},
        "gross_profit": {"t0": 367000000, "t1": 311000000, "t2": 252000000},
        "gross_margin_pct": {"t0": 62.0, "t1": 61.0, "t2": 60.0},
        "operating_expenses": {"t0": 260000000, "t1": 224000000, "t2": 189000000},
        "ebitda": {"t0": 132000000, "t1": 110000000, "t2": 84000000},
        "ebitda_margin_pct": {"t0": 22.3, "t1": 21.6, "t2": 20.0},
        "pbt": {"t0": 107000000, "t1": 87000000, "t2": 63000000},
        "tax": {"t0": 25000000, "t1": 21000000, "t2": 15000000},
        "pat": {"t0": 82000000, "t1": 66000000, "t2": 48000000},
        "pat_margin_pct": {"t0": 13.9, "t1": 12.9, "t2": 11.4}
    },
    "section_c_balance_sheet": {
        "cash_and_equivalents": {"t0": 85000000, "t1": 65000000, "t2": 48000000},
        "trade_receivables": {"t0": 35000000, "t1": 28000000, "t2": 22000000},
        "inventory": {"t0": 28000000, "t1": 24000000, "t2": 20000000},
        "other_current_assets": {"t0": 17000000, "t1": 14000000, "t2": 12000000},
        "total_current_assets": {"t0": 165000000, "t1": 131000000, "t2": 102000000},
        "ppe": {"t0": 145000000, "t1": 130000000, "t2": 115000000},
        "intangible_assets": {"t0": 25000000, "t1": 22000000, "t2": 20000000},
        "rou_assets": {"t0": 65000000, "t1": 55000000, "t2": 48000000},
        "other_non_current": {"t0": 20000000, "t1": 18000000, "t2": 15000000},
        "total_assets": {"t0": 420000000, "t1": 356000000, "t2": 300000000},
        "trade_payables": {"t0": 42000000, "t1": 35000000, "t2": 28000000},
        "other_current_liabilities": {"t0": 53000000, "t1": 45000000, "t2": 38000000},
        "total_current_liabilities": {"t0": 95000000, "t1": 80000000, "t2": 66000000},
        "bank_borrowings": {"t0": 45000000, "t1": 55000000, "t2": 60000000},
        "lease_liabilities": {"t0": 55000000, "t1": 48000000, "t2": 42000000},
        "total_non_current_liabilities": {"t0": 65000000, "t1": 68000000, "t2": 70000000},
        "total_liabilities": {"t0": 160000000, "t1": 148000000, "t2": 136000000},
        "share_capital": {"t0": 50000000, "t1": 50000000, "t2": 50000000},
        "retained_earnings": {"t0": 210000000, "t1": 158000000, "t2": 114000000},
        "total_equity": {"t0": 260000000, "t1": 208000000, "t2": 164000000}
    },
    "section_d_cash_flow": {
        "operating_cf": {"t0": 115000000, "t1": 95000000, "t2": 72000000},
        "investing_cf": {"t0": -55000000, "t1": -48000000, "t2": -40000000},
        "financing_cf": {"t0": -30000000, "t1": -25000000, "t2": -20000000},
        "net_cf": {"t0": 30000000, "t1": 22000000, "t2": 12000000},
        "capex": {"t0": 50000000, "t1": 45000000, "t2": 38000000},
        "free_cash_flow": {"t0": 65000000, "t1": 50000000, "t2": 34000000}
    },
    "section_e_working_capital": {
        "receivable_days": {"t0": 21, "t1": 20, "t2": 19},
        "inventory_days": {"t0": 45, "t1": 44, "t2": 43},
        "payable_days": {"t0": 68, "t1": 64, "t2": 61},
        "cash_conversion_cycle": {"t0": -2, "t1": 0, "t2": 1},
        "current_ratio": {"t0": 1.74, "t1": 1.64, "t2": 1.55},
        "quick_ratio": {"t0": 1.26, "t1": 1.16, "t2": 1.06}
    },
    "section_f_peers": {
        "comparables": [
            {"name": "Yifang Taiwan Fruit Tea", "market": "Private", "revenue_myr": 180000000, "pe_ratio": None, "ev_ebitda": 12.0},
            {"name": "ZUS Coffee", "market": "Private", "revenue_myr": 350000000, "pe_ratio": None, "ev_ebitda": 15.0},
            {"name": "OldTown White Coffee", "market": "Bursa", "revenue_myr": 480000000, "pe_ratio": 22.0, "ev_ebitda": 14.0},
            {"name": "Mr DIY", "market": "Bursa", "revenue_myr": 4200000000, "pe_ratio": 35.0, "ev_ebitda": 22.0}
        ],
        "target_ev_ebitda_range": {"low": 15, "mid": 18, "high": 22},
        "target_pe_range": {"low": 20, "mid": 25, "high": 30}
    },
    "section_g_projections": {
        "budget_revenue": [680000000, 780000000, 900000000, 1050000000, 1200000000],
        "budget_ebitda": [155000000, 185000000, 220000000, 265000000, 310000000],
        "budget_pat": [98000000, 120000000, 145000000, 175000000, 205000000],
        "capex_plan": [60000000, 70000000, 75000000, 65000000, 55000000],
        "projection_assumptions": "15-20% YoY revenue growth driven by 100+ new outlets/year (primarily Bask Bear), improving unit economics, and digital revenue streams."
    },
    "section_h_funding": {
        "funding_rounds": [
            {"round": "Series A", "year": 2019, "amount": 230000000, "investor": "Creador", "equity_pct": 30, "instrument": "Ordinary shares"}
        ],
        "current_shareholding": [
            {"shareholder": "Bryan Loo Woi Lip", "pct": 55, "type": "founder"},
            {"shareholder": "Creador PE Fund IV", "pct": 30, "type": "institutional"},
            {"shareholder": "Loo Chee Leng", "pct": 10, "type": "co-founder"},
            {"shareholder": "ESOP Pool", "pct": 5, "type": "esop"}
        ],
        "shareholders_agreement": True,
        "tag_drag_rights": True,
        "anti_dilution": True,
        "ipo_commitment": "Creador has pre-agreed exit via IPO within 5 years of investment (by 2024-2025)"
    },
    "section_i_rpt": {
        "related_party_transactions": [
            {"party": "Loo Family Properties Sdn Bhd", "nature": "Office rental", "annual_amount": 1200000, "arm_length": True}
        ],
        "rpt_policy_documented": True
    }
}

# ==========================================================================
# Stage 3 intake data — Strategic assessment (exit & listing)
# ==========================================================================
STAGE_3_DATA = {
    "exit_strategy": {
        "primary_exit": "ipo",
        "target_exchange": "Bursa Main Market",
        "target_timeline": "2026 H2",
        "target_valuation_myr": 2500000000,
        "secondary_exit": "trade_sale",
        "exit_readiness_self_assessment": "high",
        "advisors_engaged": ["Investment bank (shortlisted)", "Legal counsel (engaged)", "Reporting accountant (engaged)"]
    },
    "listing_readiness": {
        "profit_track_record_3yr": True,
        "min_pat_achieved": True,
        "min_market_cap_met": True,
        "corporate_governance_framework": True,
        "independent_directors_appointed": True,
        "num_independent_directors": 3,
        "audit_committee_formed": True,
        "risk_committee_formed": True,
        "nomination_committee_formed": True,
        "remuneration_committee_formed": True,
        "internal_audit_function": True,
        "compliance_officer_appointed": True
    },
    "regulatory_compliance": {
        "bursa_eligibility_met": True,
        "sc_guidelines_reviewed": True,
        "prospectus_preparation": "in_progress",
        "due_diligence_status": "ongoing",
        "legal_disputes_pending": False,
        "regulatory_approvals_needed": ["SC approval", "Bursa listing approval"],
        "tax_compliance_confirmed": True,
        "transfer_pricing_documented": True
    },
    "investor_readiness": {
        "investor_deck_prepared": True,
        "financial_model_ready": True,
        "management_presentation_rehearsed": True,
        "cornerstone_investors_identified": True,
        "cornerstone_investors_list": ["EPF", "PNB", "Kumpulan Wang Persaraan"],
        "institutional_roadshow_planned": True,
        "retail_tranche_planned": True,
        "greenshoe_option_considered": True
    }
}


async def wipe_and_reseed():
    """Drop all demo data so seed() can run fresh."""
    from sqlalchemy import text
    async with async_session_factory() as session:
        # Delete in order respecting FK constraints
        for table in [
            "report_sections", "reports",
            "dimension_scores", "module_scores", "auto_flags", "assessments",
            "chat_messages", "chat_conversations",
            "documents", "intake_stages",
            "user_roles", "users",
            "company_research", "companies",
        ]:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.commit()
        print("Wiped all demo data.")


async def seed(force: bool = False):
    from app.services.auth_service import hash_password

    if force:
        await wipe_and_reseed()

    async with async_session_factory() as session:
        # Check if already seeded
        existing = await session.execute(select(User).where(User.id == ADMIN_USER_ID))
        if existing.scalar_one_or_none():
            print("Demo data already seeded. Skipping. (use --force to reseed)")
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
        advisor_role = UserRole(user_id=ADMIN_USER_ID, company_id=COMPANY_ID, role=RoleType.advisor)
        client_role = UserRole(user_id=DEMO_USER_ID, company_id=COMPANY_ID, role=RoleType.client)
        session.add_all([advisor_role, client_role])

        # --- Intake stages (all submitted) ---
        now = datetime.now(timezone.utc)

        stage1 = IntakeStage(
            company_id=COMPANY_ID,
            stage=IntakeStageNumber.stage_1,
            status=IntakeStatus.submitted,
            data=STAGE_1_DATA,
            completed_sections=["registration", "industry", "scale", "founder", "co_founders",
                                "management_team", "succession", "products", "product_competitiveness",
                                "customers", "supply_chain", "revenue_model", "scalability",
                                "competitive_landscape", "financials", "balance_sheet", "cash_flow",
                                "audit_status", "growth_plans", "capital_intentions", "ipo_aspiration",
                                "exit_preference", "org_maturity", "culture"],
            submitted_by=DEMO_USER_ID,
            submitted_at=now,
        )
        stage2 = IntakeStage(
            company_id=COMPANY_ID,
            stage=IntakeStageNumber.stage_2,
            status=IntakeStatus.submitted,
            data=STAGE_2_DATA,
            completed_sections=["section_a_audit", "section_b_income", "section_c_balance_sheet",
                                "section_d_cash_flow", "section_e_working_capital", "section_f_peers",
                                "section_g_projections", "section_h_funding", "section_i_rpt"],
            submitted_by=DEMO_USER_ID,
            submitted_at=now,
        )
        stage3 = IntakeStage(
            company_id=COMPANY_ID,
            stage=IntakeStageNumber.stage_3,
            status=IntakeStatus.submitted,
            data=STAGE_3_DATA,
            completed_sections=["exit_strategy", "listing_readiness", "regulatory_compliance", "investor_readiness"],
            submitted_by=DEMO_USER_ID,
            submitted_at=now,
        )
        session.add_all([stage1, stage2, stage3])

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
                scored_at=now,
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
        print(f"  Intake: Stage 1, 2, 3 all submitted")
        print(f"  Assessment: 6 modules scored (overall 78.5/100)")

    # Now seed the reports
    from scripts.seed_demo_reports import seed as seed_reports
    await seed_reports()


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    asyncio.run(seed(force=force))
