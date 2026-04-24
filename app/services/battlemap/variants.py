"""
Per-variant content registry for Phase 1.5 battle maps.

The 10-chapter skeleton is shared; variant-specific content lives here so the
AI prompts stay focused and the classifier's downstream output is predictable.
"""

from __future__ import annotations

from app.models.battlemap import BattleMapVariant


VARIANT_META = {
    BattleMapVariant.replication: {
        "name_zh": "复制扩张作战图",
        "name_en": "Replication & Expansion Battle Map",
        "audience_zh": "从生存经营走向稳定盈利，或从单点业务走向可复制经营。",
        "audience_en": "Moving from survival to stable profit, or from a single point to replicable operations.",
        "core_task_zh": "核心任务不是\"更快扩张\"，而是先把模式、组织和利润质量做稳。",
        "core_task_en": "The core task is not to expand faster — it is to make the model, org, and profit quality stable first.",
        "modules": [
            {"code": "A", "title_zh": "模式标准化", "title_en": "Model Standardization",
             "action_zh": "把报价、签约、交付、续费拆成 SOP，减少老板亲自盯单。",
             "action_en": "Break quoting / signing / delivery / renewal into SOPs; reduce founder oversight."},
            {"code": "B", "title_zh": "组织承接", "title_en": "Org Takeover",
             "action_zh": "把销售、运营、创始人职责边界拉开，培养至少 2 名可独立带结果骨干。",
             "action_en": "Separate sales / ops / founder responsibilities; grow at least 2 independent leaders."},
            {"code": "C", "title_zh": "利润质量升级", "title_en": "Profit Quality Upgrade",
             "action_zh": "提升经常性收入占比，减少一次性项目和返工成本。",
             "action_en": "Raise recurring revenue share; reduce one-off project and rework costs."},
            {"code": "D", "title_zh": "复制试点", "title_en": "Replication Pilot",
             "action_zh": "先跑 1 个新渠道 / 新城市样板，再讨论规模化扩张。",
             "action_en": "Run one new-channel or new-city sample before discussing scale."},
        ],
        "do_not_do": [
            {"title_zh": "暂不建议直接启动融资", "title_en": "Don't launch fundraising yet",
             "reason_zh": "模式尚未被自己跑稳，外部资本会直接压低估值。",
             "reason_en": "Model not self-sustaining — outside capital would compress valuation."},
            {"title_zh": "暂不建议同时进入多个城市", "title_en": "Don't enter multiple cities at once",
             "reason_zh": "单城模型未跑通前多点扩张会放大组织裂缝。",
             "reason_en": "Multi-city expansion before a single-city proof amplifies org cracks."},
            {"title_zh": "暂不建议过早讲上市故事", "title_en": "Don't pitch an IPO story yet",
             "reason_zh": "距离资本市场语言还隔着一整个经营成熟度的鸿沟。",
             "reason_en": "A full layer of operational maturity still sits between here and capital markets."},
        ],
        "timeline_template": {
            "90d": [
                "完成服务分层、报价模板、成交话术与交付清单标准化",
                "建立周目标 / 转化率 / 续费率三项经营 KPI",
                "明确销售、运营、创始人三方职责边界并试运行",
            ],
            "180d": [
                "跑通至少 1 个渠道合作复制样板",
                "把续费型服务收入占比提升至 40%+",
                "培养 2 名可独立带结果的骨干负责人",
            ],
            "12m": [
                "形成单城可复制模型并进入第二城市稳定运营",
                "完成组织架构升级与激励草案",
                "具备进入《融资准备作战图》前置条件",
            ],
        },
        "suggested_next": "一对一顾问深拆",
    },
    BattleMapVariant.financing: {
        "name_zh": "融资准备作战图",
        "name_en": "Financing Readiness Battle Map",
        "audience_zh": "已经有稳定盈利和初步复制基础，但尚未把经营语言翻译成融资语言。",
        "audience_en": "Stable profit and initial replication, but ops language hasn't been translated into investor language yet.",
        "core_task_zh": "核心任务不是先见投资人，而是先把\"可投性\"做清楚。",
        "core_task_en": "The core task is not to meet investors yet — it is to make the company demonstrably investable.",
        "modules": [
            {"code": "A", "title_zh": "复制效率量化", "title_en": "Replication Efficiency Quantified",
             "action_zh": "把单店 / 单区域复制效率、回本周期、同店增长等核心指标量化。",
             "action_en": "Quantify single-unit replication efficiency, payback period, same-store growth."},
            {"code": "B", "title_zh": "融资口径财务", "title_en": "Financing-Grade Finance",
             "action_zh": "建立月报包、预算、12个月预测和资金用途表。",
             "action_en": "Build monthly reporting pack, budget, 12-month forecast, and use-of-funds schedule."},
            {"code": "C", "title_zh": "组织与供应链承接", "title_en": "Org & Supply Chain Capability",
             "action_zh": "证明团队和供应链能支撑扩张，而不是老板单点驱动。",
             "action_en": "Prove team + supply chain can carry expansion — not founder-driven."},
            {"code": "D", "title_zh": "融资材料准备", "title_en": "Fundraising Materials",
             "action_zh": "完成 BP 第一版、资金用途、问答库和投资人优先级。",
             "action_en": "First BP, use-of-funds, Q&A bank, prioritized investor list."},
        ],
        "do_not_do": [
            {"title_zh": "暂不建议盲目多城同步扩店", "title_en": "Don't blindly expand across cities",
             "reason_zh": "组织与供应链的承接能力决定扩张天花板，而不是资金。",
             "reason_en": "Org + supply chain capacity — not money — sets the ceiling on expansion."},
            {"title_zh": "暂不建议只讲品牌故事不讲回本模型", "title_en": "Don't pitch brand without unit economics",
             "reason_zh": "投资人首先要看的是回本周期和单位经济，不是品牌梦。",
             "reason_en": "Investors read payback and unit economics before brand vision."},
            {"title_zh": "暂不建议在财务口径未统一前直接见投资人", "title_en": "Don't meet investors before aligning financials",
             "reason_zh": "口径不一致的第一次会议会直接拉低信任度与估值。",
             "reason_en": "Inconsistent financials on first meeting crushes trust and valuation."},
        ],
        "timeline_template": {
            "90d": [
                "完成门店 / 业务单元分层指标体系：回本周期、同店增长、核心复购率",
                "梳理融资用途与资金分配：扩张、供应链、系统、团队",
                "搭建融资口径月报包与 12 个月经营预测",
            ],
            "180d": [
                "跑出 2–3 个可作为融资样板的新单元",
                "完成中央能力（供应链 / 中台 / 交付）效率优化方案",
                "完成 BP 第一版与投融资问答库",
            ],
            "12m": [
                "具备启动天使 / VC / 战略资本沟通条件",
                "形成区域扩张路线图与组织梯队计划",
                "升级进入更完整的资本准备 / PE 对接阶段",
            ],
        },
        "suggested_next": "融资准备",
    },
    BattleMapVariant.capitalization: {
        "name_zh": "资本化推进图",
        "name_en": "Capitalization Roadmap",
        "audience_zh": "业务与融资基础已较成熟，下一步进入资本化推进、上市预备或更高级资本市场对接。",
        "audience_en": "Business and fundraising base already mature; next step is capitalization, pre-IPO, or higher capital-market interfaces.",
        "core_task_zh": "核心任务是把成熟业务翻译成资本市场认可的结构、治理与叙事。",
        "core_task_en": "The core task is translating a mature business into the structure, governance, and narrative capital markets accept.",
        "modules": [
            {"code": "A", "title_zh": "治理与披露", "title_en": "Governance & Disclosure",
             "action_zh": "对治理、授权、审计、信息披露与合规 readiness 做系统梳理。",
             "action_en": "Systematically map governance, authorization, audit, disclosure, and compliance readiness."},
            {"code": "B", "title_zh": "资本叙事统一", "title_en": "Unified Capital Narrative",
             "action_zh": "统一董事会、管理层、老股东对估值、退出与上市路径的预期。",
             "action_en": "Align board, management, existing shareholders on valuation, exit, and listing path."},
            {"code": "C", "title_zh": "资本化时间表", "title_en": "Capitalization Timeline",
             "action_zh": "明确 90天、180天、12个月的关键结构整改与顾问协同。",
             "action_en": "Define 90/180/365-day structural fixes and advisor coordination."},
            {"code": "D", "title_zh": "上市预备接口", "title_en": "Pre-IPO Interfaces",
             "action_zh": "进入审计、法律、IR、架构与路演前置准备。",
             "action_en": "Engage audit, legal, IR, structuring, and roadshow prep workstreams."},
        ],
        "do_not_do": [
            {"title_zh": "暂不建议在治理细节未统一前贸然公开讲上市时间表", "title_en": "Don't publicize an IPO timeline with governance unresolved",
             "reason_zh": "治理短板一旦在路演阶段暴露，修复周期会比现在长 3–6 倍。",
             "reason_en": "Governance gaps exposed during roadshow take 3–6× longer to fix than now."},
            {"title_zh": "暂不建议只强调 AI 概念而忽略审计与披露准备", "title_en": "Don't over-index on thematic story (e.g. AI) and under-invest in audit/disclosure",
             "reason_zh": "叙事溢价建立在可审计的业绩之上，反之则会反噬估值。",
             "reason_en": "Narrative premium stands on auditable performance — without it, it backfires."},
            {"title_zh": "暂不建议忽视老股东退出与后续轮次协调", "title_en": "Don't neglect existing-shareholder exit and follow-on coordination",
             "reason_zh": "老股东退出预期不一致是资本化推进最常见的暗雷。",
             "reason_en": "Misaligned legacy-shareholder exit expectations is the most common hidden blocker."},
        ],
        "timeline_template": {
            "90d": [
                "完成资本化 readiness 清单：治理、财务、法务、股权、披露五大模块",
                "统一董事会、管理层与主要股东的资本路径预期",
                "梳理上市地、路径与时间窗的初步决策框架",
            ],
            "180d": [
                "启动上市前顾问协同：审计、法律、IR、结构设计",
                "完成核心 KPI 与对外披露口径统一",
                "形成资本化故事线、投资人问答库与风险披露框架",
            ],
            "12m": [
                "达到上市预备阶段的内部 readiness",
                "完成关键结构整改并进入正式项目评估",
                "具备对接更高阶资本市场服务与路演准备条件",
            ],
        },
        "suggested_next": "资本化 / 上市前规划",
    },
}


def variant_meta(variant: BattleMapVariant) -> dict:
    return VARIANT_META[variant]
