"""
Seed the three sample companies from the client's Phase 1.5 sample docx:
  1. 云桥企服 (Yunqiao) — Replication Battle Map target
  2. 味坊连锁 (Weifang) — Financing Battle Map target
  3. 领航云科 (Linghang) — Capitalization Battle Map target

Each is inserted with:
  - A user account (email/password printed at the end)
  - A Company record
  - A fully-scored Phase 1 Diagnostic (answers crafted to produce scores that
    match the target variant)
  - A classified Phase 1.5 BattleMap (answers taken verbatim from the client's
    sample xlsx so the classifier picks the correct variant)

Per-section AI analyses and the 10-chapter report are NOT generated here — the
advisor should click "Generate Report" on the reports page so the customer
sees real, typo-free AI narrative.

Run from the backend directory:
  .venv/bin/python scripts/seed_sample_companies.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a script: add backend/ to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.database import async_session_factory
from app.models.battlemap import BattleMap, BattleMapStatus
from app.models.company import Company
from app.models.diagnostic import Diagnostic, DiagnosticStatus
from app.models.user import User
from app.services.auth_service import hash_password
from app.services.battlemap.classifier import classify
from app.services.battlemap.variants import variant_meta
from app.services.diagnostic.scoring import score_diagnostic


# ── Sample data ──────────────────────────────────────────────────────────────
#
# Each sample dict carries:
#   user:            login credentials + full name
#   company:         basics
#   phase1_answers:  35 Phase 1 answers (Q01-Q35) — the scoring engine derives
#                    six-structure scores + enterprise_stage from these
#   phase1_5_answers: 35 Phase 1.5 answers — taken verbatim from the client
#                    sample so the classifier produces the right variant

SAMPLES = [
    # ────────────────── 云桥企服 (Replication) ──────────────────
    {
        "user": {
            "email": "yunqiao@iifle-demo.com",
            "password": "Demo2026!",
            "full_name": "陈智远 (云桥企服)",
            "phone": None,
        },
        "company": {
            "legal_name": "云桥企服（模拟）",
            "primary_industry": "企业服务 / 财税合规 / 商家代办",
            "country": "Malaysia",
            "brief_description": "模拟样本 — 早期服务公司，正从生存经营期迈向稳定盈利期",
        },
        "phase1_answers": {
            "Q01": "1–3年",
            "Q02": "5–10年",
            "Q03": "服务业",
            "Q04": "100万–500万",
            "Q05": "偶尔盈利",
            "Q06": "11–30人",
            "Q07": "已经能稳定成交",
            "Q08": "先稳定盈利",
            "Q09": "少数销售高手",
            "Q10": "创始人+少数核心骨干",
            "Q11": "较清楚",
            "Q12": "一部分可以",
            "Q13": "有少数核心骨干",
            "Q14": "多种收入组合",
            "Q15": "中等部分可复制",
            "Q16": "有基础流程",
            "Q17": "一部分可以",
            "Q18": "一般",
            "Q19": "主要靠创始人/熟人资源",
            "Q20": "有少量验证",
            "Q21": "增加销售团队",
            "Q22": "全国性品牌机会",
            "Q23": "系统 / 技术",
            "Q24": "稳定营收",
            "Q25": "靠产品赚钱的业务型公司",
            "Q26": "基本清楚",
            "Q27": "全部创始人持有",
            "Q28": "有基础财务报表",
            "Q29": "暂时不融资，先经营",
            "Q30": "1年后再看",
            "Q31": "有基础资料但不完整",
            "Q32": "不会讲资本故事",
            "Q33": "长期经营，不谈退出",
            "Q34": "先把经营和模式跑顺",
            "Q35": ["看清企业卡在哪", "看清能不能复制扩张"],
        },
        "phase1_5_answers": {
            "Q01": "稳定盈利",
            "Q02": "太依赖老板",
            "Q03": "先建立一套不依赖老板的成交与交付 SOP，让业务能稳定复制。",
            "Q04": "先做内部结构升级",
            "Q05": "少数核心客户",
            "Q06": "较高",
            "Q07": "组合式收入",
            "Q08": "有机会",
            "Q09": "有尝试但不稳定",
            "Q10": "有基础流程",
            "Q11": "一部分可以",
            "Q12": "销售成交",
            "Q13": "偶尔盈利",
            "Q14": "一半一半",
            "Q15": "有基础财务报表",
            "Q16": "大致知道",
            "Q17": "1位",
            "Q18": "几乎所有重要事项",
            "Q19": "有少数骨干",
            "Q20": "运营型人才",
            "Q21": "基本清楚",
            "Q22": "以上皆无",
            "Q23": "偶尔存在",
            "Q24": "有部分机制",
            "Q25": "投资人可能会关注的是：中小企业合规服务需求稳定、续费属性逐步增强、可通过产品化和渠道化实现区域复制。",
            "Q26": "产品升级",
            "Q27": "全国性机会",
            "Q28": "能讲部分增长逻辑",
            "Q29": "愿意重点推进",
            "Q30": "愿意一起参与",
            "Q31": "基本愿意",
            "Q32": "一对一顾问深拆",
            "Q33": "最大的结构性障碍是：老板依赖过重，导致成交、交付与团队承接无法真正脱钩。",
            "Q34": "未来一年最值得放大的增长点是：把秘书与合规续费做成标准化套餐，并通过渠道合作复制到新城市。",
            "Q35": "最希望本次报告帮我看清：先补哪些底层结构，才能从\"业务型工作室\"升级为可复制的企业服务公司。",
        },
    },

    # ────────────────── 味坊连锁 (Financing) ──────────────────
    {
        "user": {
            "email": "weifang@iifle-demo.com",
            "password": "Demo2026!",
            "full_name": "林婉婷 (味坊连锁)",
            "phone": None,
        },
        "company": {
            "legal_name": "味坊连锁（模拟）",
            "primary_industry": "餐饮连锁 / 地方特色快餐",
            "country": "Malaysia",
            "brief_description": "模拟样本 — 已跑通单店模型，准备从稳定盈利期进入复制扩张期",
        },
        "phase1_answers": {
            "Q01": "5年以上",
            "Q02": "10年以上",
            "Q03": "餐饮连锁",
            "Q04": "3000万–1亿",
            "Q05": "持续稳定盈利",
            "Q06": "31–100人",
            "Q07": "正在扩张",
            "Q08": "先复制扩张",
            "Q09": "团队与系统共同驱动",
            "Q10": "团队+组织机制",
            "Q11": "清楚且差异化明显",
            "Q12": "大部分可以",
            "Q13": "有较成熟管理层",
            "Q14": "多种收入组合",
            "Q15": "较高已有初步方法",
            "Q16": "已有可训练SOP",
            "Q17": "大部分可以",
            "Q18": "较高",
            "Q19": "主要靠渠道/平台/品牌流量",
            "Q20": "有明显验证",
            "Q21": "多开店 / 多开点",
            "Q22": "全国性品牌机会",
            "Q23": "供应链 / 交付能力",
            "Q24": "多城市复制",
            "Q25": "可复制的成长型公司",
            "Q26": "较清晰",
            "Q27": "有少量外部股东",
            "Q28": "有1年年度审计",
            "Q29": "想做融资准备",
            "Q30": "6–12个月",
            "Q31": "已开始系统整理融资资料",
            "Q32": "财务不规范",
            "Q33": "未来融资后再退出",
            "Q34": "可以开始做上市前体检",
            "Q35": ["看清有没有融资可能", "看清企业卡在哪"],
        },
        "phase1_5_answers": {
            "Q01": "扩张到新区域 / 新门店 / 新团队",
            "Q02": "团队承接不住",
            "Q03": "先把门店复制模型、店长体系与供应链协同稳定下来，再考虑更快扩张。",
            "Q04": "融资准备",
            "Q05": "多门店 / 多区域",
            "Q06": "一般",
            "Q07": "重复采购",
            "Q08": "已有一定验证",
            "Q09": "已初步验证",
            "Q10": "有较完整 SOP",
            "Q11": "大部分可以",
            "Q12": "团队管理",
            "Q13": "持续稳定盈利",
            "Q14": "主要来自主营业务",
            "Q15": "有较规范报表",
            "Q16": "已有明确预算和用途规划",
            "Q17": "4–5位",
            "Q18": "资源整合",
            "Q19": "有基础管理层",
            "Q20": "财务型人才",
            "Q21": "较清晰",
            "Q22": "以上皆无",
            "Q23": "基本清楚",
            "Q24": "基本建立",
            "Q25": "投资人可能会感兴趣的是：公司已跑通高复购门店模型、具备区域化复制能力，并可通过供应链与品牌化进一步拉开利润空间。",
            "Q26": "新门店 / 新网点",
            "Q27": "全国性机会",
            "Q28": "能讲成长与市场空间",
            "Q29": "愿意重点推进",
            "Q30": "必须一起参与",
            "Q31": "愿意积极调整",
            "Q32": "融资准备",
            "Q33": "最大的结构性障碍是：门店复制已验证，但组织、财务与资本表达还没有完全跟上复制速度。",
            "Q34": "未来一年最值得放大的增长点是：复制成熟门店模型，同时借助中央厨房和培训体系提升新店开业成功率。",
            "Q35": "最希望本次报告帮我看清：若准备融资，哪些指标、材料与结构要先补到位。",
        },
    },

    # ────────────────── 领航云科 (Capitalization) ──────────────────
    {
        "user": {
            "email": "linghang@iifle-demo.com",
            "password": "Demo2026!",
            "full_name": "周启航 (领航云科)",
            "phone": None,
        },
        "company": {
            "legal_name": "领航云科（模拟）",
            "primary_industry": "企业软件 / AI 数据应用 / SaaS",
            "country": "Malaysia",
            "brief_description": "模拟样本 — ARR 稳定且 AI 模块增长，资本准备期向上市预备期过渡",
        },
        "phase1_answers": {
            "Q01": "5年以上",
            "Q02": "10年以上",
            "Q03": "SaaS/科技",
            "Q04": "1亿以上",
            "Q05": "盈利能力较强",
            "Q06": "101–300人",
            "Q07": "正在准备融资/资本动作",
            "Q08": "先进入融资/资本路径",
            "Q09": "团队与系统共同驱动",
            "Q10": "已开始系统化运转",
            "Q11": "已形成行业标签/品牌认知",
            "Q12": "基本可以",
            "Q13": "已有系统化管理团队+决策机制",
            "Q14": "订阅/月费",
            "Q15": "很高已有成熟SOP",
            "Q16": "已能复制给不同团队",
            "Q17": "基本完全可以",
            "Q18": "很高",
            "Q19": "多渠道较均衡",
            "Q20": "已形成区域复制基础",
            "Q21": "区域扩张 / 跨国复制",
            "Q22": "东南亚机会",
            "Q23": "系统 / 技术",
            "Q24": "强品牌/流量/平台效应",
            "Q25": "具备平台化潜力的高估值公司",
            "Q26": "非常清晰",
            "Q27": "有多轮投资人+员工持股计划",
            "Q28": "有2–3年审计 / 较规范财务体系",
            "Q29": "想走向上市路径",
            "Q30": "3–6个月内",
            "Q31": "已能进入 BP / 路演准备",
            "Q32": "缺乏投资人资源",
            "Q33": "未来上市退出",
            "Q34": "已开始认真思考上市路径",
            "Q35": ["看清未来上市路径", "看清有没有高估值潜力"],
        },
        "phase1_5_answers": {
            "Q01": "启动资本化 / 上市规划",
            "Q02": "不知道如何讲估值故事",
            "Q03": "先把治理、股权、财务披露口径和资本叙事统一起来，形成资本化推进底盘。",
            "Q04": "上市规划",
            "Q05": "多产品组合",
            "Q06": "较分散",
            "Q07": "长期客户续费",
            "Q08": "已较成熟",
            "Q09": "已较成熟复制",
            "Q10": "可复制给他人执行",
            "Q11": "基本可以",
            "Q12": "基本可正常运行",
            "Q13": "盈利能力较强",
            "Q14": "非常稳定且持续",
            "Q15": "有年度审计 / 较规范财务体系",
            "Q16": "已有明确预算和用途规划",
            "Q17": "5位以上",
            "Q18": "资源整合",
            "Q19": "较成熟",
            "Q20": "资本 / 战略型人才",
            "Q21": "非常清晰",
            "Q22": "外部股东诉求不一致",
            "Q23": "已较清晰分开",
            "Q24": "较规范",
            "Q25": "投资人会关注的是：高续费 SaaS 收入、行业数据壁垒、AI 模块带来的 ARPU 提升，以及东南亚区域扩张与潜在资本化路径。",
            "Q26": "技术化升级",
            "Q27": "东南亚区域机会",
            "Q28": "能较完整讲清估值逻辑",
            "Q29": "愿意全面推进",
            "Q30": "必须一起参与",
            "Q31": "愿意积极调整",
            "Q32": "资本化 / 上市前规划",
            "Q33": "最大的结构性障碍是：业务已经成熟，但资本动作前的治理深度、投资人协调和上市节奏管理仍需更细化。",
            "Q34": "未来一年最值得放大的增长点是：AI 模块升级与东南亚区域扩张叠加，提升 ARR 与估值想象力。",
            "Q35": "最希望本次报告帮我看清：距离资本化推进和上市预备还差哪些硬条件，以及先后顺序。",
        },
    },
]


# Section order must match service.submit_section ordering.
PHASE1_SECTION_ORDER = ["a", "b", "c", "d", "e", "f"]
BM_SECTION_ORDER = ["a", "b", "c", "d", "e", "f", "g", "h"]


async def upsert_user(db, data: dict) -> User:
    """Create or fetch a user by email. Password is re-hashed on every run."""
    result = await db.execute(select(User).where(User.email == data["email"]))
    user = result.scalar_one_or_none()
    if user:
        user.password_hash = hash_password(data["password"])
        user.full_name = data["full_name"]
        await db.flush()
        return user
    user = User(
        email=data["email"],
        password_hash=hash_password(data["password"]),
        full_name=data["full_name"],
        phone=data.get("phone"),
    )
    db.add(user)
    await db.flush()
    return user


async def upsert_company(db, user_id: uuid.UUID, data: dict) -> Company:
    """Find a company owned by this user with the same legal name, or create."""
    result = await db.execute(
        select(Company).where(Company.legal_name == data["legal_name"])
    )
    company = result.scalar_one_or_none()
    if company:
        return company
    company = Company(
        legal_name=data["legal_name"],
        primary_industry=data.get("primary_industry"),
        country=data.get("country", "Malaysia"),
        brief_description=data.get("brief_description"),
    )
    db.add(company)
    await db.flush()
    return company


async def upsert_diagnostic(db, user_id: uuid.UUID, company_id: uuid.UUID, answers: dict) -> Diagnostic:
    """Create (or replace) a fully-scored Phase 1 diagnostic."""
    result = await db.execute(
        select(Diagnostic).where(
            Diagnostic.user_id == user_id, Diagnostic.company_id == company_id
        )
    )
    d = result.scalar_one_or_none()
    if not d:
        d = Diagnostic(user_id=user_id, company_id=company_id)
        db.add(d)
        await db.flush()

    d.answers = answers
    d.other_answers = {}

    score = score_diagnostic(answers)
    module_scores: dict = dict(score.get("module_scores") or {})

    # Mark every section as submitted so the sidebar + battle map gate treat
    # this as a complete Phase 1.
    meta = module_scores.get("_meta", {})
    meta["sections_submitted"] = list(PHASE1_SECTION_ORDER)
    meta["stage_score"] = score.get("stage_score")
    meta["section_submitted_at"] = {
        k: datetime.now(timezone.utc).isoformat() for k in PHASE1_SECTION_ORDER
    }
    module_scores["_meta"] = meta

    d.module_scores = module_scores
    d.overall_score = score.get("overall_score")
    d.overall_rating = score.get("overall_rating")
    d.enterprise_stage = score.get("enterprise_stage")
    d.capital_readiness = score.get("capital_readiness")
    d.key_findings = score.get("key_findings") or []
    d.status = DiagnosticStatus.completed
    now = datetime.now(timezone.utc)
    d.submitted_at = d.submitted_at or now
    d.scored_at = now

    flag_modified(d, "module_scores")
    flag_modified(d, "answers")
    flag_modified(d, "key_findings")
    await db.flush()
    return d


async def upsert_battlemap(db, user_id: uuid.UUID, company_id: uuid.UUID, diagnostic: Diagnostic, answers: dict) -> BattleMap:
    """Create (or replace) a Phase 1.5 battle map — classified, no AI analyses."""
    result = await db.execute(
        select(BattleMap).where(BattleMap.diagnostic_id == diagnostic.id)
    )
    bm = result.scalar_one_or_none()
    if not bm:
        bm = BattleMap(
            user_id=diagnostic.user_id,
            company_id=company_id,
            diagnostic_id=diagnostic.id,
        )
        db.add(bm)
        await db.flush()
    # Always realign battle map ownership to the diagnostic's owner.
    bm.user_id = diagnostic.user_id
    bm.answers = answers
    bm.other_answers = {}
    bm.source_scores = diagnostic.module_scores

    # Classify.
    result_cls = classify(diagnostic, answers)
    bm.variant = result_cls.variant
    bm.current_stage = result_cls.current_stage
    bm.target_stage = result_cls.target_stage

    meta = variant_meta(result_cls.variant)
    bm.top_priorities = [
        {
            "rank": i + 1,
            "title_zh": m["title_zh"],
            "title_en": m["title_en"],
            "action_zh": m["action_zh"],
            "action_en": m["action_en"],
        }
        for i, m in enumerate(meta["modules"][:3])
    ]
    bm.do_not_do = meta["do_not_do"]
    bm.battle_modules = meta["modules"]
    bm.timeline = meta["timeline_template"]

    # Mark all sections as submitted (answers are complete) so the sidebar
    # shows every section with a check — but leave section_analyses empty.
    # The advisor can click "Submit & analyze" per section later OR just
    # generate the 10-chapter report directly from the Reports page.
    bm.section_analyses = {
        "_meta": {
            "sections_submitted": list(BM_SECTION_ORDER),
            "section_submitted_at": {
                k: datetime.now(timezone.utc).isoformat() for k in BM_SECTION_ORDER
            },
        }
    }
    bm.status = BattleMapStatus.submitted
    now = datetime.now(timezone.utc)
    bm.submitted_at = bm.submitted_at or now
    bm.completed_at = now

    flag_modified(bm, "section_analyses")
    flag_modified(bm, "answers")
    await db.flush()
    return bm


async def seed_one(sample: dict) -> dict:
    async with async_session_factory() as db:
        try:
            user = await upsert_user(db, sample["user"])
            company = await upsert_company(db, user.id, sample["company"])
            diagnostic = await upsert_diagnostic(
                db, user.id, company.id, sample["phase1_answers"]
            )
            battlemap = await upsert_battlemap(
                db, user.id, company.id, diagnostic, sample["phase1_5_answers"]
            )
            await db.commit()
            return {
                "user_email": user.email,
                "user_password": sample["user"]["password"],
                "company": company.legal_name,
                "diagnostic_id": str(diagnostic.id),
                "overall_score": float(diagnostic.overall_score) if diagnostic.overall_score else None,
                "enterprise_stage": diagnostic.enterprise_stage,
                "battle_map_id": str(battlemap.id),
                "variant": battlemap.variant.value if battlemap.variant else None,
                "current_stage": battlemap.current_stage,
                "target_stage": battlemap.target_stage,
            }
        except Exception:
            await db.rollback()
            raise


async def main():
    print("Seeding 3 sample companies...\n")
    results = []
    for sample in SAMPLES:
        try:
            r = await seed_one(sample)
            results.append(r)
        except Exception as exc:
            print(f"  ✗ {sample['company']['legal_name']}: {exc}")
            raise

    print("\nSeeded. Login credentials:\n")
    print(f"  {'Company':<22} {'Email':<32} {'Password':<12} {'Variant':<18} {'Score'}")
    print(f"  {'-'*22} {'-'*32} {'-'*12} {'-'*18} {'-'*6}")
    for r in results:
        print(
            f"  {r['company']:<22} {r['user_email']:<32} {r['user_password']:<12} "
            f"{(r['variant'] or '—'):<18} {r['overall_score']}"
        )
    print("\nNext steps for the advisor:")
    print("  1. Log in as any of the above emails")
    print("  2. Open that company → Reports page")
    print("  3. Click 'Generate Report' → pick Diagnostic or Battle Map")
    print("  4. Review the AI-generated narrative with the client\n")


if __name__ == "__main__":
    asyncio.run(main())
