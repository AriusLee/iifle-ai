"""
Seed demo reports for Loob Berhad (Tealive) — Gene Structure + Business Model.
Run: python3 scripts/seed_demo_reports.py
"""
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import text, select
from app.database import async_session_factory
from app.models.report import Report, ReportSection, ReportStatus, ReportType, ReportLanguage

COMPANY_ID = uuid.UUID("d5f6ec35-6fdb-4da6-bf85-84bd572c25e7")

# We'll use the latest assessment
async def get_latest_assessment_id():
    async with async_session_factory() as s:
        r = await s.execute(text(
            "SELECT id FROM assessments WHERE company_id = :cid ORDER BY created_at DESC LIMIT 1"
        ), {"cid": COMPANY_ID})
        row = r.fetchone()
        return row[0] if row else None


# ============================================================
# GENE STRUCTURE REPORT (Module 1) — Standard Tier
# ============================================================

GENE_SECTIONS = [
    {
        "key": "executive_summary",
        "title": "Executive Summary",
        "content_en": """Loob Berhad demonstrates a remarkably strong gene structure with an overall Module 1 score of 82/100, placing it firmly in the "Strong" category. The company's DNA is characterized by a visionary founder with proven resilience, dominant market positioning in Southeast Asia's lifestyle beverage segment, and a multi-brand portfolio that provides both diversification and growth optionality.

Key strengths include Bryan Loo's exceptional entrepreneurial track record — having survived the Chatime-to-Tealive overnight rebrand in 2017 and emerged stronger — a well-documented franchise model with comprehensive SOPs enabling rapid replication, and a professional management team that has been progressively assembled to reduce founder dependency ahead of the planned Bursa Main Market IPO.

The primary areas for improvement center on succession planning (currently in progress but not formalized), moderate barriers to entry in the bubble tea segment facing aggressive competition from Mixue, and a relatively high employee turnover rate of 35% that, while typical for F&B retail, presents scalability challenges.

Overall, Loob Berhad possesses the foundational "genes" of a company ready for public market scrutiny, with its multi-brand strategy, proven operational model, and strong founder narrative providing compelling capital market positioning.""",
        "content_cn": """Loob Berhad展现出极为强劲的基因结构，第一模块总分82/100，稳居"强劲"评级。公司的DNA特征体现在创始人的远见和韧性、在东南亚生活方式饮品领域的市场主导地位，以及多品牌组合带来的多元化和增长选择权。

主要优势包括创始人Bryan Loo卓越的创业记录——在2017年Chatime到Tealive的一夜品牌重塑中生存并更加强大——完善的特许经营模式和全面的标准操作流程实现快速复制，以及为减少创始人依赖、为计划中的Bursa主板上市而逐步组建的专业管理团队。

需要改进的主要领域集中在继任计划（目前正在进行但尚未正式化）、珍珠奶茶领域面临来自蜜雪冰城激烈竞争的适度进入壁垒，以及35%的较高员工流失率（虽然在马来西亚餐饮零售中属于典型水平）带来的可扩展性挑战。

总体而言，Loob Berhad具备接受公开市场审视的基础"基因"，其多品牌策略、成熟的运营模式和强大的创始人叙事提供了引人注目的资本市场定位。"""
    },
    {
        "key": "founder_analysis",
        "title": "Founder & Key Person Analysis",
        "content_en": """Score: 85/100

Bryan Loo Woi Lip is a standout founder in Malaysia's F&B landscape. At 40 years old with 16 years of industry experience, he has built Loob Berhad from a single Chatime franchise outlet into Southeast Asia's largest lifestyle beverage company with over 1,087 outlets across 11 countries.

Founder Strengths:
• Proven Crisis Leadership: The 2017 Chatime franchise dispute and overnight rebrand to Tealive is one of the most remarkable business pivots in Malaysian corporate history. Bryan retained 95%+ of stores and staff, demonstrating exceptional crisis management and brand-building capability.
• Recognition & Network: Named EY Emerging Entrepreneur of the Year 2013/2014, Endeavor Entrepreneur 2023, and featured across major Asian business publications. This network provides deal flow, mentorship, and investor confidence.
• Multi-brand Vision: Rather than being a single-product entrepreneur, Bryan has systematically expanded into coffee (Bask Bear), sparkling water (SodaXpress), and kombucha (WonderBrew), showing strategic portfolio thinking.
• PE Partnership: Successfully secured a 30% stake investment from Creador (one of Asia's top PE firms) at ~RM230M, validating the business model and governance standards.

Key Person Risk:
Bryan remains the face of the brand and primary strategic driver. However, the risk is being actively mitigated through:
• Sister Loo Chee Leng as COO with 14 years' tenure handling day-to-day operations
• Professional C-suite hires in 2023-2024 (CFO, Digital Director, HR Director)
• PE-appointed board directors from Creador providing governance oversight

Education (Monash University, BSc Biotechnology) is solid but not elite MBA-tier — however, this is more than compensated by practical entrepreneurial achievement.

Succession plan is "in progress" — this should be formalized with documented protocols before IPO. Currently rated as adequate but not exemplary.""",
        "content_cn": """评分：85/100

Bryan Loo Woi Lip是马来西亚餐饮行业中的杰出创始人。40岁，拥有16年行业经验，他将Loob Berhad从一家Chatime特许经营店发展成为东南亚最大的生活方式饮品公司，在11个国家拥有超过1,087家门店。

创始人优势：
• 危机领导力：2017年Chatime特许经营权争议和一夜品牌重塑为Tealive，是马来西亚企业史上最引人注目的商业转型之一。Bryan保留了95%以上的门店和员工，展示了卓越的危机管理和品牌建设能力。
• 认可与人脉：荣获安永2013/2014年新兴企业家奖、2023年Endeavor企业家，并被亚洲主要商业刊物广泛报道。
• 多品牌愿景：系统性地扩展到咖啡（Bask Bear）、苏打水（SodaXpress）和康普茶（WonderBrew），展现战略性组合思维。
• PE合作：成功获得Creador（亚洲顶级PE之一）约2.3亿令吉的30%股权投资，验证了商业模式和治理标准。

关键人物风险：
Bryan仍然是品牌的代言人和主要战略驱动者。然而，风险正在通过以下方式积极缓解：妹妹Loo Chee Leng担任COO拥有14年任期、2023-2024年聘请的专业高管团队，以及Creador委派的董事会成员。

继任计划"正在进行中"——应在上市前以书面形式正式化。"""
    },
    {
        "key": "industry_analysis",
        "title": "Industry & Market Analysis",
        "content_en": """Score: 78/100

Industry Overview:
The Southeast Asian bubble tea and specialty beverage market is valued at approximately US$4.3 billion (2024) and is projected to grow at a CAGR of 8-10% through 2028. Malaysia's segment is estimated at RM2.5-3.0 billion, driven by a young demographic (median age 30), high urbanization (78%), and strong café culture.

Market Position:
Loob Berhad holds an estimated 10-25% market share in Malaysia's lifestyle beverage segment by outlet count, making it the #1 player. Tealive alone has 831 outlets — more than double the next largest competitor. This scale advantage provides:
• Superior negotiating power with suppliers and landlords
• Brand recognition and consumer trust (Reader's Digest Trusted Brand Platinum 2023)
• Data advantages from 2.8M digital loyalty members

Industry Lifecycle:
The bubble tea segment is in a mature-growth phase in Malaysia, with consolidation expected as smaller players exit. The coffee segment (Bask Bear's space) remains in early growth, with significant whitespace.

Competitive Threats:
• Mixue: Chinese ultra-low-price competitor (RM3-5 per drink vs Tealive's RM8-12). Has opened 200+ outlets in Malaysia since 2023. Competes on price, not quality.
• ZUS Coffee: Fast-growing Malaysian coffee chain (~500 outlets). Direct competitor to Bask Bear.
• Gong Cha: Premium positioned Taiwan brand. Less aggressive in Malaysia expansion.

PESTEL Considerations:
• Sugar tax regulations could impact pricing and margins
• Halal certification requirements create a moat for established players
• Rising commodity costs (sugar, dairy, tea leaves) affect industry margins
• Environmental regulations on single-use plastics (cup/straw bans) require operational adaptation

The industry positioning is strong but not exceptional — the moderate barriers to entry and intense competition from well-funded international entrants (Mixue) prevent a higher score.""",
        "content_cn": """评分：78/100

行业概况：
东南亚珍珠奶茶和特色饮品市场2024年估值约43亿美元，预计到2028年将以8-10%的复合年增长率增长。马来西亚细分市场估计为25-30亿令吉。

市场地位：
Loob Berhad在马来西亚生活方式饮品领域按门店数量计算占据约10-25%的市场份额，位居第一。仅Tealive就拥有831家门店——是第二大竞争对手的两倍多。

竞争威胁：
• 蜜雪冰城：中国超低价竞争者，自2023年以来在马来西亚开设200多家门店
• ZUS Coffee：快速增长的马来西亚咖啡连锁，Bask Bear的直接竞争对手
• 贡茶：定位高端的台湾品牌

行业定位强劲但非卓越——适度的进入壁垒和来自资金充足的国际竞争者的激烈竞争限制了更高评分。"""
    },
    {
        "key": "product_analysis",
        "title": "Product & Service Analysis",
        "content_en": """Score: 82/100

Loob Berhad operates a compelling multi-brand portfolio spanning four distinct beverage categories:

1. Tealive (65% of revenue, 831 outlets): The flagship brand and Malaysia's #1 bubble tea chain. Offers 70+ drink options with proprietary recipes. Achieved Reader's Digest Trusted Brand Platinum status. Strong brand equity built through the resilient Chatime-to-Tealive transition.

2. Bask Bear Coffee (25% of revenue, 135 outlets): Launched in 2021, this is the high-growth engine. Positioned as an affordable specialty coffee alternative to ZUS and Starbucks. Growing at 80-100 new outlets per year, demonstrating the company's ability to replicate the Tealive playbook in a new category.

3. SodaXpress (5% of revenue): Sparkling water machines for home and commercial use. A different business model (product sales + refills) providing margin diversification.

4. WonderBrew Kombucha (3% of revenue, 35% equity stake): Health-conscious beverage play targeting the growing wellness segment. Strategic investment rather than core operation.

Product Competitiveness:
• Proprietary recipes and trade secrets provide differentiation from generic competitors
• 2.8M digital loyalty members with 57% monthly active rate — exceptional for F&B
• Menu innovation cycle every 6-8 weeks keeps consumer engagement high
• Halal certification across all brands provides a competitive moat in Muslim-majority markets
• RM8M annual R&D spend (~1.4% of revenue) is adequate for the F&B sector

Revenue Concentration Risk: Low. No single customer exceeds 0.1% of revenue — this is a mass-market B2C model with 5M+ monthly consumers. Excellent diversification.

The multi-brand strategy is the key differentiator — most competitors are single-brand operators. This provides natural hedging and multiple growth vectors.""",
        "content_cn": """评分：82/100

Loob Berhad运营着一个引人注目的多品牌组合，涵盖四个不同的饮品类别：

1. Tealive（收入的65%，831家门店）：旗舰品牌，马来西亚第一珍珠奶茶连锁。
2. Bask Bear Coffee（收入的25%，135家门店）：2021年推出的高增长引擎。
3. SodaXpress（收入的5%）：苏打水机，提供利润率多元化。
4. WonderBrew康普茶（收入的3%）：面向健康养生市场的战略投资。

多品牌策略是关键差异化因素——大多数竞争对手都是单一品牌运营商。这提供了自然对冲和多个增长向量。"""
    },
    {
        "key": "differentiation_analysis",
        "title": "Differentiation & Competitive Advantage",
        "content_en": """Score: 80/100

Loob Berhad's competitive moat is built on several reinforcing layers:

Scale Advantage (Strong): 1,087+ outlets provide unmatched scale in Southeast Asia's lifestyle beverage space. This translates to superior supplier pricing, prime retail locations secured through long-standing landlord relationships, and operational efficiencies that smaller competitors cannot match.

Brand Resilience (Exceptional): The Chatime-to-Tealive overnight rebrand is arguably the strongest proof of brand moat in Malaysian F&B history. The fact that 95%+ of outlets, staff, and customers stayed demonstrates that the moat sits with the operator, not the franchisor brand.

Digital Ecosystem (Strong): The 2.8M-member loyalty platform with 57% monthly active usage creates a data-driven engagement loop. This enables personalized marketing, predictive inventory management, and direct consumer communication — capabilities that most competitors lack.

Multi-Brand Portfolio (Differentiating): Operating across tea, coffee, sparkling water, and kombucha provides category diversification that single-brand operators cannot replicate quickly. Each brand can cross-promote and share supply chain infrastructure.

Areas of Vulnerability:
• The core bubble tea category has moderate barriers to entry — recipes can be approximated
• Mixue's ultra-low pricing strategy could erode the mass-market segment
• Franchise model means some quality consistency risk across 290+ franchise outlets
• Brand is Malaysia-centric; international brand recognition is still developing

The moat is real and multi-layered, but not impregnable — continuous innovation and scale expansion are required to maintain the advantage.""",
        "content_cn": """评分：80/100

Loob Berhad的竞争护城河建立在多个相互强化的层面上：规模优势（强）、品牌韧性（卓越）、数字生态系统（强）和多品牌组合（差异化）。

护城河是真实且多层次的，但并非坚不可摧——需要持续创新和规模扩张来维持优势。"""
    },
    {
        "key": "replicability_analysis",
        "title": "Replicability & Scalability Analysis",
        "content_en": """Score: 85/100

Replicability is one of Loob Berhad's strongest dimensions, reflecting the company's proven franchise and expansion model.

Franchise Model Maturity:
• Comprehensive SOPs documented for all operational processes
• Centralized supply chain with a dedicated procurement and distribution facility in Petaling Jaya
• New staff training program of just 3 weeks — highly efficient for F&B
• Proven store opening playbook: consistently opens 100+ new outlets per year
• Franchise fee of RM75K per outlet with 3% ongoing royalty — well-structured economics

Scalability Evidence:
• Grew from ~150 outlets (2017 rebrand) to 1,087+ outlets (2024) — 7x growth in 7 years
• Successfully replicated the model across 11 countries, though international markets are still early-stage
• Bask Bear Coffee's rapid growth (0 to 135 outlets in 3 years) proves the playbook is transferable to new brands/categories
• Central facility provides the backbone for scaling without proportional overhead increases

Checklist Assessment:
✅ Replicable to new locations — Easily
✅ Documented SOPs — Comprehensive
✅ Central facility — Yes
✅ Training program — Systematic (3 weeks)
✅ Expansion plan — Clear (200+ new stores/year across brands)
✅ International playbook — Developing (11 countries, but mostly franchise-based)

The only deduction is that international expansion, while impressive by count, has yet to prove the same unit economics as the Malaysian operations. The company's growth is overwhelmingly Malaysia-driven.""",
        "content_cn": """评分：85/100

可复制性是Loob Berhad最强的维度之一。特许经营模式成熟度高，全面的标准操作流程、集中的供应链、仅3周的新员工培训计划。

从2017年约150家门店增长到2024年的1,087家以上——7年增长7倍。Bask Bear Coffee 3年内从0增长到135家门店，证明了商业模式可转移到新品牌。"""
    },
    {
        "key": "team_analysis",
        "title": "Team & Organizational Analysis",
        "content_en": """Score: 76/100

Organizational Structure:
Loob Berhad operates with approximately 2,000 employees across 10 departments. The organizational structure is mature for a company of its size, with a formal org chart, semi-annual performance reviews, and a comprehensive employee handbook.

Management Team Assessment:
• The C-suite has been significantly professionalized since 2023, with dedicated CFO, Digital Director, and HR Director hires
• COO Loo Chee Leng (founder's sister, 14 years' tenure) provides operational continuity and institutional knowledge
• The presence of Creador-appointed directors adds governance rigor and capital markets experience
• Gerald Young (Group Digital Strategy Director) brings critical digital transformation capability

Areas of Concern:
• 35% employee turnover rate — while typical for F&B retail in Malaysia, this represents a significant operational cost (estimated RM5-8M annually in recruitment and training)
• The management team outside the founding family is relatively new (2-5 years), which may present integration risks
• HR Director (Muhammad Syamil) has only 3 years' tenure — the people function is still maturing

Culture & Values:
The company has a clearly documented vision, mission, and core values, anchored by Bryan Loo's "People is everything" philosophy. This cultural framework is important for franchise quality consistency and employee engagement, though the high turnover suggests execution gaps between stated values and operational reality.

The team foundation is solid and improving, but not yet at the "best-in-class" level expected of a Bursa Main Market listee. The key milestone will be demonstrating management stability through the IPO process.""",
        "content_cn": """评分：76/100

组织结构成熟，拥有约2,000名员工和10个部门。自2023年以来，高管团队已显著专业化。

需关注领域：35%的员工流失率虽然在餐饮零售中属于典型水平，但代表着显著的运营成本。创始家族以外的管理团队相对较新（2-5年），可能存在整合风险。

团队基础稳固且在改善中，但尚未达到Bursa主板上市公司所期望的"一流"水平。"""
    },
    {
        "key": "growth_analysis",
        "title": "Growth Trajectory & Potential",
        "content_en": """Score: 83/100

Historical Growth:
• Revenue CAGR (FY2022-2024): 18.3% — strong and consistent
• FY2022: RM422.5M → FY2023: RM511.8M (+21.1%) → FY2024: RM591.2M (+15.5%)
• Outlet growth: ~700 (2022) → 1,087+ (2024)

Profitability Trajectory:
• PAT declined significantly in FY2023 (RM64.5M → RM38.5M, -40.3%) due to expansion costs and Bask Bear investment phase
• Strong recovery in FY2024 (RM38.5M → RM51.6M, +34.0%) as new outlets mature
• Gross margins remain stable at 65% — excellent for F&B

Forward Projections:
• Revenue target FY2025: RM700M (18.4% growth)
• Revenue target FY2027: RM1.0B (milestone)
• Revenue target FY2029: RM1.5B
• Growth drivers: 200+ new outlets/year, Bask Bear scaling, FMCG launch, international expansion

Capital Leverage:
• IPO targeted to raise RM660M (US$150M) — this capital injection will fund the expansion to RM1B revenue
• Post-IPO, the company will have both organic cash flow (~RM80-100M PAT) and IPO proceeds to fund growth
• Debt-to-equity is moderate (estimated net gearing 0.24x) — room for additional leverage if needed

Growth Assessment:
The growth trajectory is strong and credible. Revenue CAGR exceeds the 15% threshold for "strong growth" classification. The FY2023 PAT dip is explainable (Bask Bear investment phase) and has already reversed. The path to RM1B revenue is well-supported by the outlet pipeline and proven store economics.

The primary risk is execution — opening 200+ outlets per year while maintaining quality and unit economics requires significant operational discipline.""",
        "content_cn": """评分：83/100

历史增长：收入复合年增长率（FY2022-2024）：18.3%，强劲且持续。

盈利轨迹：FY2023 PAT因扩张成本大幅下降（-40.3%），但FY2024强劲恢复（+34.0%）。毛利率稳定在65%。

增长轨迹强劲可信。收入复合增长率超过15%"强增长"分类阈值。通往10亿令吉收入的路径有门店管线和成熟的门店经济模型支撑。"""
    },
    {
        "key": "recommendations",
        "title": "Recommendations & Action Items",
        "content_en": """Based on the Gene Structure analysis (Score: 82/100, Rating: Strong), the following recommendations are prioritized:

Immediate Actions (0-6 months):
1. Formalize Succession Plan: Document a board-approved succession protocol for the CEO role. Identify and develop 2-3 potential internal successors beyond the founding family.
2. Reduce Employee Turnover: Implement targeted retention programs for store managers and key operational staff. Target reduction from 35% to 25% within 18 months.
3. Strengthen IP Portfolio: Accelerate trademark registrations in international markets ahead of expansion. Consider trade dress protection for store concepts.

Short-term Actions (6-12 months):
4. Board Independence: Ensure board composition meets Bursa Main Market requirements (minimum 1/3 independent directors, diverse expertise).
5. International Unit Economics: Conduct a detailed profitability analysis of international franchise operations. Establish minimum ROI thresholds for new market entry.
6. Competitive Intelligence: Develop a systematic monitoring framework for Mixue's expansion strategy and pricing impact on Tealive's mass-market segment.

Medium-term Actions (12-24 months):
7. Management Bench Depth: Continue building professional management below C-suite level. Each brand should have a dedicated managing director.
8. ESG Framework: Develop a sustainability strategy addressing single-use plastics, supply chain ethics, and employee welfare — increasingly important for institutional investors.
9. Innovation Pipeline: Formalize the R&D process with stage-gate methodology. The FMCG product launch (3-in-1 beverages) should have dedicated resources and P&L accountability.

Capital Market Readiness:
The gene structure supports an IPO timeline of 12-18 months. The key prerequisites are succession plan formalization and demonstration of post-Bask Bear investment PAT normalization. The founder's story and brand resilience will be compelling selling points in the IPO roadshow.""",
        "content_cn": """基于基因结构分析（得分：82/100，评级：强劲），以下建议按优先级排列：

即时行动（0-6个月）：
1. 正式化继任计划
2. 降低员工流失率（目标从35%降至25%）
3. 加强知识产权组合

短期行动（6-12个月）：
4. 董事会独立性
5. 国际单位经济分析
6. 竞争情报框架

中期行动（12-24个月）：
7. 管理层深度建设
8. ESG框架开发
9. 创新管线正式化

资本市场就绪度：基因结构支持12-18个月的IPO时间表。"""
    },
]


# ============================================================
# BUSINESS MODEL REPORT (Module 2) — Standard Tier
# ============================================================

BM_SECTIONS = [
    {
        "key": "bm_executive_summary",
        "title": "Business Model Executive Summary",
        "content_en": """Loob Berhad's business model receives an overall Module 2 score of 79/100, placing it in the "Developing → Mature" category. The company operates a hybrid corporate-franchise model that combines the margin benefits of company-operated stores (676 outlets) with the capital efficiency of franchise operations (290+ outlets).

The business model's core strength lies in its proven replicability — the company has successfully deployed the same playbook across four brands and eleven countries, demonstrating that the revenue engine is not dependent on any single product, geography, or channel.

Revenue quality is strong: 75% recurring revenue driven by daily consumer purchase patterns, zero customer concentration risk (B2C mass market), and stable 65% gross margins. The multi-brand portfolio provides natural diversification, with Bask Bear Coffee emerging as a meaningful second growth engine alongside the mature Tealive brand.

Key challenges include: operating expense pressure from rapid expansion (net margins compressed from 15.3% to 8.7% over two years), the need to defend pricing against ultra-low-cost competitors like Mixue, and the inherent operational complexity of managing 1,087+ outlets across multiple brands and countries.

The business model is well-suited for public market listing — it is transparent, measurable, and has clear unit economics that institutional investors can model and track.""",
        "content_cn": """Loob Berhad的商业模式获得第二模块总分79/100，处于"发展中→成熟"类别。公司运营混合的直营-加盟模式，结合了直营店（676家）的利润率优势和加盟运营（290多家）的资本效率。

商业模式的核心优势在于其经过验证的可复制性——公司已成功在四个品牌和十一个国家部署了相同的模式。

收入质量强劲：75%的经常性收入、零客户集中风险、稳定的65%毛利率。商业模式非常适合公开市场上市。"""
    },
    {
        "key": "revenue_model_analysis",
        "title": "Revenue Model Analysis",
        "content_en": """Score: 81/100

Revenue Streams:
1. Corporate Store Sales (RM385M, ~65%): Direct retail revenue from 676 company-operated Tealive and Bask Bear outlets. Average revenue per store approximately RM570K/year. This is the highest-margin stream.

2. Franchise Operations (RM148M, ~25%): Combination of franchise fees (RM75K per new outlet), 3% ongoing royalties, and raw material supply to 290+ franchise outlets. The raw material supply to franchisees is particularly strategic — it ensures quality consistency while capturing supply chain margin.

3. SodaXpress Products (RM30M, ~5%): B2C product sales of sparkling water machines and refill cartridges. Different business model with lower capital intensity.

4. WonderBrew & Other (RM28M, ~5%): Kombucha sales (35% equity stake), licensing income, and miscellaneous revenue.

Revenue Quality Indicators:
• Recurring Revenue: 75% — driven by daily consumer repeat purchases. Tealive's loyalty program shows average customer visits 3-4x per month.
• Revenue Predictability: High — same-store sales growth is trackable and relatively predictable for mature outlets.
• Seasonality: Mild — Q2 (Oct-Dec) and Q3 (Jan-Mar) are slightly stronger due to holiday season and Chinese New Year. Maximum seasonal variance is ~15%.
• Pricing Power: Moderate — average selling price RM8-12 per drink positions Tealive in the "affordable premium" segment. Room to raise prices exists but is constrained by Mixue's RM3-5 offerings at the low end.

The revenue model scores well due to diversification, high recurring percentage, and proven unit economics. The deduction comes from the pricing pressure in the core bubble tea segment.""",
        "content_cn": """评分：81/100

收入来源：直营店销售（约65%）、加盟运营（约25%）、SodaXpress产品（约5%）、WonderBrew及其他（约5%）。

收入质量指标：75%经常性收入、高可预测性、温和季节性。收入模式因多元化、高经常性比例和经过验证的单位经济模型而获得高分。"""
    },
    {
        "key": "cost_structure_analysis",
        "title": "Cost Structure & Unit Economics",
        "content_en": """Score: 75/100

Cost Structure Breakdown (FY2024):
• COGS: RM206.9M (35% of revenue) — raw materials (tea, coffee, dairy, sugar, cups, packaging)
• Gross Margin: 65% — excellent and stable over 3 years
• Operating Expenses: RM318M (53.8% of revenue) — rent, staff, marketing, corporate overhead
• EBIT Margin: ~11.2% (estimated)
• Net Margin: 8.7% — compressed from 15.3% (FY2022) due to Bask Bear expansion investment

Unit Economics (Estimated per Corporate Store):
• Average Annual Revenue: RM570K
• COGS (35%): RM200K
• Store-Level OpEx (rent, staff, utilities): RM280K
• Store-Level EBITDA: RM90K (~16% margin)
• Payback Period: 12-18 months for a new corporate outlet

Margin Trajectory:
The compression from 15.3% to 8.7% net margin over two years is the primary concern. This is driven by:
1. Bask Bear store opening costs (135 new outlets in investment phase)
2. Corporate overhead scaling ahead of revenue (hiring C-suite team)
3. Rising rental costs in prime locations
4. Raw material cost inflation

However, the gross margin stability at 65% indicates the core product economics remain intact. As Bask Bear outlets mature (typically reaching profitability at month 8-10) and corporate overhead leverage improves, net margins should recover to 10-12% by FY2026.

The cost structure is sound but needs operational discipline to reverse the margin compression trend.""",
        "content_cn": """评分：75/100

毛利率65%——优秀且三年保持稳定。净利率8.7%——从15.3%（FY2022）压缩，主要因Bask Bear扩张投资。

单位经济模型（每家直营店）：平均年收入RM570K，门店级EBITDA约16%，投资回收期12-18个月。

随着Bask Bear门店成熟和企业管理费用杠杆改善，净利率应在FY2026前恢复至10-12%。"""
    },
    {
        "key": "customer_analysis",
        "title": "Customer Segmentation & Acquisition",
        "content_en": """Score: 84/100

Customer Profile:
Loob Berhad serves a mass-market B2C customer base of 5M+ monthly consumers. The customer profile skews towards urban Malaysians aged 18-40, with a slight female skew (estimated 55/45). The company serves approximately 50 million cups annually across all brands.

Customer Concentration: Excellent
• Top 1 customer: 0.1% of revenue — virtually zero concentration risk
• Top 5 customers: 0.5% — mass-market consumer model
• This is one of the strongest customer diversification profiles in Malaysian F&B

Customer Acquisition & Retention:
• Digital Loyalty Platform: 2.8M registered members with an exceptional 57% monthly active rate. This is a major competitive advantage — most F&B chains achieve 20-30% active rates.
• Acquisition Cost: Effectively near-zero per customer — driven by foot traffic from prime retail locations (mall, transit hub, commercial district positioning).
• Retention Rate: ~70% (estimated) — strong for impulse-purchase F&B.
• Average Customer Relationship: 3-5 years, with high-value customers showing 10+ year loyalty from the original Chatime era.

Customer Experience:
• 70+ drink options per brand with seasonal rotations every 6-8 weeks
• Digital ordering (app + delivery platform integration) accounts for growing share
• Consistent quality across outlets through centralized supply chain
• Halal certification provides trust and accessibility for the majority market

The customer dimension scores highly due to exceptional diversification, strong digital engagement, and proven mass-market appeal. The main risk is potential customer defection to lower-priced alternatives (Mixue) in the price-sensitive segment.""",
        "content_cn": """评分：84/100

客户集中度：优秀。前1客户仅占收入的0.1%——几乎零集中风险。这是马来西亚餐饮行业最强的客户多元化档案之一。

数字忠诚度平台：280万注册会员，57%月活率——大多数餐饮连锁仅达到20-30%。"""
    },
    {
        "key": "value_proposition_analysis",
        "title": "Value Proposition Assessment",
        "content_en": """Score: 80/100

Loob Berhad's value proposition centers on "Accessible Premium Lifestyle Beverages" — offering quality drinks at mid-range prices (RM8-12) with convenience (1,087+ locations) and variety (4 brands, 200+ drink options).

Value Proposition Strengths:
• Multi-Brand Portfolio: Covers the complete beverage lifestyle spectrum — tea (Tealive), coffee (Bask Bear), sparkling water (SodaXpress), and kombucha (WonderBrew). Customers can "stay within the ecosystem" regardless of their beverage preference.
• Accessibility: Stores strategically located in high-traffic areas — malls, transit hubs, commercial districts. The average Malaysian in an urban area is within 2km of a Tealive outlet.
• Quality-Price Balance: Positioned between premium (Starbucks at RM15-20) and ultra-budget (Mixue at RM3-5). This "affordable premium" positioning captures the largest addressable market segment.
• Digital Integration: The loyalty app enhances the value proposition with personalized promotions, reward points, and convenience features.

Value Proposition Risks:
• The "affordable premium" positioning could be squeezed from both ends — premium brands moving down and budget brands moving up.
• Brand story is stronger in Malaysia than in international markets where Tealive lacks the Chatime heritage narrative.
• The multi-brand strategy, while diversifying, could lead to brand dilution if not carefully managed.

Overall, the value proposition is clear, differentiated, and well-positioned for the target market. The multi-brand approach provides strategic flexibility that single-brand competitors lack.""",
        "content_cn": """评分：80/100

Loob Berhad的价值主张围绕"可负担的高端生活方式饮品"——以中等价位（RM8-12）提供优质饮品，配合便利性（1,087多个地点）和多样性（4个品牌，200多种饮品选择）。

多品牌组合覆盖完整的饮品生活方式光谱。"可负担高端"定位捕获了最大的可寻址市场细分。"""
    },
    {
        "key": "channel_analysis",
        "title": "Distribution & Channel Analysis",
        "content_en": """Score: 78/100

Channel Mix:
1. Corporate Stores (676 outlets, ~65% of revenue): Highest control and margin. Located in malls, transit hubs, and commercial districts. Average store size 200-400 sq ft. Staff of 4-6 per outlet.

2. Franchise Stores (290+ outlets, ~25% of revenue): Capital-efficient expansion. 5-year franchise agreements with RM75K entry fee and 3% ongoing royalty. Franchisees purchase raw materials from Loob's central supply chain (additional margin capture).

3. Digital / Delivery (~5% of revenue, growing): Integration with GrabFood, Foodpanda, ShopeeFood. In-app ordering through the Tealive loyalty app. This channel is growing 30-40% year-on-year.

4. FMCG / Retail (planned): Ready-to-drink bottled beverages and 3-in-1 sachets for supermarket distribution. This represents a significant new channel opportunity.

Channel Strengths:
• The hybrid corporate-franchise model balances margin quality with expansion speed
• Central supply chain to all outlets (including franchisees) ensures quality consistency
• Digital channel growth provides incremental revenue without proportional cost
• 1,087+ physical touchpoints create an unmatched distribution network in Malaysia

Channel Weaknesses:
• Franchise quality control requires ongoing investment and monitoring
• International franchise operations in 10 countries create operational complexity
• FMCG channel is still in planning — execution risk
• Delivery channel margins are lower due to platform commissions (25-30%)

The distribution network is one of Loob's strongest competitive assets. The planned FMCG expansion could be transformative if executed well.""",
        "content_cn": """评分：78/100

渠道组合：直营店（676家，约65%收入）、加盟店（290多家，约25%收入）、数字/外卖（约5%，增长中）、快消品/零售（计划中）。

混合直营-加盟模式平衡了利润率质量和扩张速度。1,087多个实体接触点在马来西亚创造了无与伦比的分销网络。"""
    },
    {
        "key": "scalability_analysis",
        "title": "Scalability & Margin Expansion",
        "content_en": """Score: 77/100

Current Scale:
Loob Berhad has demonstrated impressive scaling capability — growing from ~150 outlets post-rebrand (2017) to 1,087+ outlets (2024), representing a 7x increase in 7 years. Revenue has scaled proportionally from an estimated RM120M to RM591M.

Scalability Assessment:
• Operational Scalability: HIGH — the franchise model and centralized supply chain allow rapid outlet addition without proportional HQ overhead growth. The company consistently opens 100+ new outlets per year.
• Margin Scalability: MODERATE — while gross margins are stable (65%), operating leverage has not yet materialized. OpEx has grown faster than revenue due to Bask Bear investment and C-suite hires. Net margin should inflect upward as these investments mature.
• Geographic Scalability: MODERATE — proven in Malaysia but international operations (10 countries) are still early-stage. Unit economics in international markets have not been publicly validated.
• Brand Scalability: HIGH — the successful launch and rapid scaling of Bask Bear proves the company can create and scale new brands using the existing infrastructure and playbook.

10x Test:
Could this business support 10x current revenue (RM5.9B)?
• Outlet Network: Would require ~10,000 outlets. Challenging but not impossible with aggressive international franchise expansion.
• Supply Chain: Would require significant investment in central production and distribution infrastructure.
• Management: Would require substantial organizational scaling beyond current structure.
• Verdict: 10x within current model is achievable over 10-15 years with international expansion, but represents a stretch. 3-5x is more realistic within 5-7 years.

Margin Expansion Opportunity:
Post-IPO, margins should benefit from: Bask Bear store maturation, operating leverage on corporate overhead, FMCG channel (higher margin at scale), and reduced cost of capital.""",
        "content_cn": """评分：77/100

Loob Berhad展示了令人印象深刻的扩展能力——从2017年品牌重塑后的约150家门店增长到2024年的1,087多家，7年增长7倍。

10倍测试：在当前模式下，10倍增长在10-15年内通过国际扩张是可以实现的，但具有挑战性。3-5倍在5-7年内更为现实。"""
    },
    {
        "key": "financial_sustainability",
        "title": "Financial Sustainability Outlook",
        "content_en": """Score: 76/100

Revenue Sustainability:
The business model generates highly sustainable revenue driven by daily consumer purchase patterns. Key sustainability indicators:
• 3-year revenue CAGR: 18.3% — consistently above market growth
• Same-store sales growth: estimated 5-8% — indicating organic growth beyond new outlets
• Recurring revenue: 75% — daily consumer visits provide predictable revenue base
• No customer concentration: mass-market B2C model is inherently diversified

Profitability Sustainability:
The gross margin stability at 65% is reassuring, but the net margin trajectory requires attention:
• FY2022: 15.3% → FY2023: 7.5% → FY2024: 8.7%
• The compression is explained by growth investment, but markets will want to see a clear return to 10%+ within 2-3 years
• Operating cash flow remains positive — the business is self-funding at the operating level

Balance Sheet Health:
• Net gearing estimated at 0.24x — conservative and appropriate
• Cash balance of RM60M provides ~2.3 months of runway — tight but typical for capital-efficient F&B operators
• Fixed assets of RM350M reflect the physical store network
• Post-IPO (RM660M raise), the balance sheet will be significantly strengthened

Going Concern Assessment:
No going concern risk. The business is profitable, cash-flow positive from operations, has PE backing (Creador), and is actively preparing for IPO. The short cash runway (2.3 months) is a function of efficient capital deployment rather than financial distress.

The financial sustainability outlook is positive but requires margin recovery execution to achieve a higher score.""",
        "content_cn": """评分：76/100

收入可持续性高：3年收入复合增长率18.3%，75%经常性收入，零客户集中度。

盈利可持续性需关注：净利率从15.3%压缩至8.7%。市场将期望在2-3年内明确回归10%以上。

无持续经营风险。企业盈利、运营现金流为正、拥有PE支持、正在积极准备上市。"""
    },
    {
        "key": "bm_recommendations",
        "title": "Business Model Recommendations",
        "content_en": """Based on the Business Model analysis (Score: 79/100, Rating: Developing → Mature), the following recommendations are prioritized:

Immediate Actions (0-6 months):
1. Margin Recovery Plan: Develop a detailed plan to return net margins to 10%+ by FY2026. Include store-level P&L benchmarking, underperforming outlet review, and corporate overhead optimization.
2. Bask Bear Unit Economics Disclosure: Prepare detailed unit economics data for Bask Bear stores by cohort (months since opening) to demonstrate the path to franchise-level margins.
3. Competitive Response Strategy: Develop a formal response to Mixue's price aggression — whether through a fighter brand, value menu options, or differentiation emphasis.

Short-term Actions (6-12 months):
4. FMCG Channel Launch: Accelerate the ready-to-drink and 3-in-1 product launch into supermarket channels. This diversifies revenue and provides higher-margin volume.
5. Franchise Quality Framework: Implement a formal franchise performance scoring system with mystery shopper audits, customer satisfaction benchmarks, and remediation protocols.
6. Digital Revenue Growth: Invest in the loyalty platform to increase digital ordering share from ~5% to 15-20%. This channel has better margins (no rental cost) and provides valuable consumer data.

Medium-term Actions (12-24 months):
7. International Profitability: Conduct a market-by-market profitability review. Exit or restructure underperforming international markets. Double down on markets showing positive unit economics.
8. Supply Chain Optimization: Evaluate opportunities for vertical integration in key raw materials (tea blending, coffee roasting) to improve gross margins by 2-3 percentage points.
9. Subscription Model: Explore a monthly beverage subscription program for high-frequency customers to lock in recurring revenue and improve predictability.

Capital Market Positioning:
For IPO purposes, position the business model narrative around: (1) proven multi-brand platform with transferable playbook, (2) recovering margins as Bask Bear matures, (3) FMCG upside as a new growth vector, and (4) the digital loyalty ecosystem as a data moat. The comparable peer set should include Kopi Kenangan (Indonesia), Flash Coffee (Singapore), and Mixue (China) rather than traditional F&B companies.""",
        "content_cn": """基于商业模式分析（得分：79/100，评级：发展中→成熟），以下建议按优先级排列：

即时行动（0-6个月）：
1. 利润率恢复计划——目标FY2026前恢复至10%以上
2. Bask Bear单位经济模型披露
3. 竞争应对策略——应对蜜雪冰城的价格攻势

短期行动（6-12个月）：
4. 快消品渠道启动
5. 加盟质量评估框架
6. 数字收入增长——目标数字订单占比从5%提升至15-20%

中期行动（12-24个月）：
7. 国际市场盈利审查
8. 供应链优化（垂直整合）
9. 订阅模式探索

资本市场定位：围绕经过验证的多品牌平台、恢复中的利润率、快消品增长向量和数字忠诚度生态系统进行叙事。"""
    },
]


async def seed():
    assessment_id = await get_latest_assessment_id()
    if not assessment_id:
        print("ERROR: No assessment found for Loob Berhad. Run scoring first.")
        return

    print(f"Company: {COMPANY_ID}")
    print(f"Assessment: {assessment_id}")

    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)

        # --- Gene Structure Report (Standard) ---
        gene_report_id = uuid.uuid4()
        gene_report = Report(
            id=gene_report_id,
            assessment_id=assessment_id,
            company_id=COMPANY_ID,
            report_type=ReportType.module_1,
            title="Gene Structure Assessment Report",
            status=ReportStatus.draft,
            language=ReportLanguage.bilingual,
            version=1,
        )
        session.add(gene_report)
        await session.flush()

        for idx, sec in enumerate(GENE_SECTIONS):
            section = ReportSection(
                id=uuid.uuid4(),
                report_id=gene_report_id,
                section_key=sec["key"],
                section_title=sec["title"],
                content_en=sec["content_en"].strip(),
                content_cn=sec.get("content_cn", "").strip() or None,
                sort_order=idx,
                is_ai_generated=True,
            )
            session.add(section)

        print(f"✓ Gene Structure Report created: {gene_report_id} ({len(GENE_SECTIONS)} sections)")

        # --- Business Model Report (Standard) ---
        bm_report_id = uuid.uuid4()
        bm_report = Report(
            id=bm_report_id,
            assessment_id=assessment_id,
            company_id=COMPANY_ID,
            report_type=ReportType.module_2,
            title="Business Model Assessment Report",
            status=ReportStatus.draft,
            language=ReportLanguage.bilingual,
            version=1,
        )
        session.add(bm_report)
        await session.flush()

        for idx, sec in enumerate(BM_SECTIONS):
            section = ReportSection(
                id=uuid.uuid4(),
                report_id=bm_report_id,
                section_key=sec["key"],
                section_title=sec["title"],
                content_en=sec["content_en"].strip(),
                content_cn=sec.get("content_cn", "").strip() or None,
                sort_order=idx,
                is_ai_generated=True,
            )
            session.add(section)

        print(f"✓ Business Model Report created: {bm_report_id} ({len(BM_SECTIONS)} sections)")

        await session.commit()
        print("\n✅ Demo reports seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
