"""
AI-powered qualitative scoring using the Anthropic Claude API.

Each scoring method builds a detailed prompt with the exact rubric text from
the IIFLE knowledge base, then calls the Claude API for structured evaluation.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from app.services.ai.provider import get_ai_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class DimensionResult(TypedDict, total=False):
    score: float
    reasoning: str
    sub_scores: dict[str, int] | None


# ---------------------------------------------------------------------------
# Rubric prompt templates — embedded verbatim from knowledge base
# ---------------------------------------------------------------------------

FOUNDER_LEADERSHIP_RUBRIC = """\
## Dimension 1: Founder & Leadership (Gene Structure)

### Scoring Rubric
| Score | Criteria |
|-------|---------|
| 90-100 | 15+ years industry experience; prior successful exit or IPO; EMBA/executive education completed; built strong management team (all C-suite filled, 3+ years stable); clear succession plan; recognized industry leader |
| 70-89 | 10+ years industry experience; no prior exit but strong business track record; EMBA in progress or equivalent education; most C-suite positions filled; management stable 2+ years; succession planning initiated |
| 50-69 | 5-10 years experience; moderate track record; some executive education; key management gaps exist (missing CFO or COO); moderate key person dependency |
| 30-49 | 3-5 years experience; limited track record; no executive education; founder handles most key roles; high key person dependency; no succession plan |
| 0-29 | <3 years experience; first-time entrepreneur in this industry; no management team beyond founder; entire business depends on one person |

### Sub-Factor Breakdown (score each 0-100)
| Sub-Factor | Weight | Input Field |
|-----------|--------|-------------|
| Industry track record (years) | 25% | B1 |
| Prior exit/IPO experience | 15% | B1 |
| Education & continuous learning | 15% | B1 |
| Management team completeness | 20% | B3 |
| Management stability (3+ years) | 15% | B4 |
| Succession readiness | 10% | B4 |

Score each sub-factor individually and provide them in sub_scores.
"""

INDUSTRY_POSITIONING_RUBRIC = """\
## Dimension 2: Industry Positioning (Gene Structure)

### Scoring Rubric
| Score | Criteria |
|-------|---------|
| 90-100 | Large, growing market (TAM >RM1B); industry in Growth or early Maturity phase; company is #1 or #2 in its segment/region; strong macro tailwinds (PESTEL favorable); significant barriers to entry |
| 70-89 | Growing market; company in top 5 in segment; industry has growth runway; most PESTEL factors favorable; moderate barriers to entry |
| 50-69 | Moderate market size; company has meaningful but not leading position; mixed macro factors; some competitive threats; low-moderate barriers |
| 30-49 | Small or declining market; company has weak positioning; unfavorable macro trends; highly competitive with low barriers; commoditized industry |
| 0-29 | Declining or disrupted industry; company has no meaningful market position; severe regulatory or macro headwinds; no barriers to entry |

### Sub-Factor Breakdown (score each 0-100)
| Sub-Factor | Weight | Source |
|-----------|--------|--------|
| TAM size and growth rate | 30% | A2, AI-researched |
| Industry lifecycle stage | 20% | AI-determined |
| Company's market position | 25% | D3 |
| PESTEL alignment | 15% | AI-analyzed |
| Barriers to entry | 10% | D3 |

If web research data is provided, use it to inform TAM, PESTEL, and industry lifecycle assessments.
Score each sub-factor individually and provide them in sub_scores.
"""

PRODUCT_COMPETITIVENESS_RUBRIC = """\
## Dimension 3: Product Competitiveness (Gene Structure)

### Scoring Rubric
| Score | Criteria |
|-------|---------|
| 90-100 | Clear product-market fit with strong differentiation; patents/IP/proprietary tech; high R&D investment (>5% of revenue); multiple growth products; strong customer satisfaction; industry certifications (ISO, Halal, etc.) |
| 70-89 | Good differentiation; some IP or proprietary advantage; moderate R&D; 1-2 strong products driving growth; good customer feedback; relevant certifications |
| 50-69 | Moderate differentiation; no IP but some operational know-how; limited R&D; products are competitive but not leading; mixed customer feedback |
| 30-49 | Weak differentiation; easily replicated products; no R&D; dependent on price competition; limited product range |
| 0-29 | No meaningful differentiation; commodity offering; no innovation; declining product relevance; no certifications |

### Consistency Principle Bonus
If all 9 alignment elements (Strategy → Product → Quality → Supply Chain → UX → Marketing → Management → Team) are assessed as "Aligned", add +5 bonus points (cap at 100).

Evaluate the 9 alignment elements and note in your reasoning whether the consistency bonus applies.
Score each sub-factor individually and provide them in sub_scores.
"""

ENTERPRISE_DIFFERENTIATION_RUBRIC = """\
## Dimension 4: Enterprise Differentiation (Gene Structure)

### Scoring Rubric
| Score | Criteria |
|-------|---------|
| 90-100 | 3+ strong moat types present (brand + tech + scale + network effects); defensible competitive position; high switching costs for customers; exclusive supply chain advantages |
| 70-89 | 2 strong moat types; good competitive position; some switching costs or scale advantages; recognized brand in segment |
| 50-69 | 1 moat type (often regulatory license or location); moderate competitive position; limited switching costs; brand awareness developing |
| 30-49 | No clear moat; competitive advantage based primarily on price or relationships; easily disrupted by new entrants |
| 0-29 | No competitive advantage; commodity player; vulnerable to any new entrant or market shift |

### Moat Type Scoring Guide (use to inform your score)
| Moat Type | Strong | Medium | Weak | Absent |
|-----------|--------|--------|------|--------|
| Brand | +20 | +12 | +5 | 0 |
| Technology/IP | +20 | +12 | +5 | 0 |
| Scale/Cost | +15 | +10 | +5 | 0 |
| Network effects | +20 | +12 | +5 | 0 |
| Switching costs | +15 | +10 | +5 | 0 |
| Regulatory/License | +10 | +7 | +3 | 0 |
| Supply chain | +10 | +7 | +3 | 0 |

Score = min(sum of moat points, 100)

Evaluate each moat type and provide individual assessments in sub_scores (as moat point contributions).
"""

BM_CLARITY_RUBRIC = """\
## Dimension 4: Business Model Clarity (Business Model Module)

### Scoring Rubric (AI-Judged)
| Score | Criteria |
|-------|---------|
| 90-100 | Crystal clear value proposition; revenue engine is proven and repeatable; cost structure well-understood and optimized; profit formula documented; anyone can explain the business model in 30 seconds |
| 70-89 | Clear value proposition; revenue mechanism understood; cost structure known but not fully optimized; business model can be articulated clearly |
| 50-69 | Value proposition exists but not sharply defined; revenue model works but isn't systematic; cost structure has unclear areas; hard to explain concisely |
| 30-49 | Vague value proposition; revenue comes in but mechanism is unclear; cost structure not well understood; business model changes frequently |
| 0-29 | No clear value proposition; revenue is opportunistic; no understanding of cost structure; business model is essentially undefined |

Evaluate the clarity of the value proposition, revenue mechanism, cost structure understanding, and profit formula articulation.
"""

SCALABILITY_RUBRIC = """\
## Dimension 6: Scalability (Business Model Module)

### Scoring Rubric (AI-Judged)
| Score | Criteria |
|-------|---------|
| 90-100 | All 4 flows scalable (payment, people, logistics, information); proven multi-geography operation; channel diversification; strong expansion pipeline; central infrastructure; the business could handle 10x volume with proportional investment |
| 70-89 | 3 of 4 flows scalable; expansion to new locations proven; channel expansion in progress; 10x growth possible with significant but achievable investment |
| 50-69 | 2 of 4 flows scalable; limited geographic expansion; single-channel dependency; 10x growth would require fundamental model changes |
| 30-49 | 1 flow scalable; heavily location-dependent; no channel diversification; growth is linear and labor-intensive |
| 0-29 | No flows are scalable; entirely dependent on founder's presence; cannot grow beyond current capacity without reinventing the business |

### 10x Test
Also assess: "Can this business grow 10x with capital?"
- "Yes" → +5 bonus to the module total
- "Partially" → no change
- "No" → -5 penalty to the module total

Include your 10x test verdict in sub_scores as {"ten_x_test": 100 for Yes, 50 for Partially, 0 for No}.
Evaluate each of the 4 flows (payment, people, logistics, information) individually in sub_scores.
"""

PLATFORM_POTENTIAL_RUBRIC = """\
## Dimension 8: Platform Potential (Business Model Module)

### Scoring Rubric (AI-Judged)
| Score | Criteria |
|-------|---------|
| 90-100 | True platform model with strong network effects; multi-sided marketplace; proprietary data advantage; ecosystem lock-in demonstrated |
| 70-89 | Some platform characteristics; data advantage developing; potential for network effects; marketplace features in development |
| 50-69 | Linear business model but with some digital/platform elements; data collection capability; could evolve toward platform |
| 30-49 | Traditional business model; minimal digital infrastructure; no network effects; limited data advantage |
| 0-29 | Purely offline/traditional; no digital presence; no path to platform model |

Evaluate network effects, data advantage, marketplace characteristics, and digital infrastructure.
"""

# ---------------------------------------------------------------------------
# Calibration example — Swift Haulage
# ---------------------------------------------------------------------------

SWIFT_HAULAGE_CALIBRATION = {
    "company": "Swift Haulage Berhad",
    "industry": "Logistics",
    "context": (
        "Listed logistics company in Malaysia. Specialises in haulage and "
        "container transport. Revenue ~RM200M. Overall valuation score 66% "
        "(Satisfactory). Growth 67%, Profitability 86%, Efficiency 60%, Credit 50%."
    ),
    "expected_scores": {
        "industry_positioning": "60-70 (mature logistics, competitive, moderate barriers)",
        "product_competitiveness": "55-65 (operational excellence but limited IP)",
        "enterprise_differentiation": "50-60 (scale advantage + fleet, but limited moats)",
    },
}


# ---------------------------------------------------------------------------
# AI Scorer
# ---------------------------------------------------------------------------

class AIScorer:
    """Scores qualitative dimensions by calling Claude with rubric-guided prompts."""

    def __init__(self, client: Any = None) -> None:
        self._client = client or get_ai_client()

    # ------------------------------------------------------------------
    # Gene Structure dimensions
    # ------------------------------------------------------------------

    async def score_founder_leadership(self, intake_data: dict[str, Any]) -> DimensionResult:
        """Gene D1: Founder & Leadership (AI-judged, 6 sub-factors)."""
        relevant = _extract_keys(intake_data, [
            "founder_name", "founder_experience_years", "prior_exit_ipo",
            "education", "executive_education", "management_team",
            "c_suite_filled", "management_stability_years", "succession_plan",
            "key_person_dependency", "founder_roles",
            # Stage 1 field references
            "B1", "B3", "B4", "b1", "b3", "b4",
        ])
        result = await self._client.score_dimension(
            dimension_name="Founder & Leadership",
            rubric=FOUNDER_LEADERSHIP_RUBRIC,
            input_data=relevant,
        )
        return _to_dimension_result(result)

    async def score_industry_positioning(
        self,
        intake_data: dict[str, Any],
        research_data: dict[str, Any] | None = None,
    ) -> DimensionResult:
        """Gene D2: Industry Positioning (AI + data-supported)."""
        relevant = _extract_keys(intake_data, [
            "industry", "primary_industry", "sub_industry",
            "market_position", "tam_estimate", "competitors",
            "barriers_to_entry", "industry_lifecycle",
            "A2", "D3", "a2", "d3",
        ])
        if research_data:
            relevant["web_research"] = research_data

        few_shot = [SWIFT_HAULAGE_CALIBRATION]
        result = await self._client.score_dimension(
            dimension_name="Industry Positioning",
            rubric=INDUSTRY_POSITIONING_RUBRIC,
            input_data=relevant,
            few_shot_examples=few_shot,
        )
        return _to_dimension_result(result)

    async def score_product_competitiveness(self, intake_data: dict[str, Any]) -> DimensionResult:
        """Gene D3: Product Competitiveness (AI-judged + consistency bonus)."""
        relevant = _extract_keys(intake_data, [
            "products", "product_description", "ip_patents",
            "r_and_d_investment", "r_and_d_pct", "certifications",
            "customer_satisfaction", "product_range",
            "alignment_elements", "consistency_assessment",
            "D1", "D2", "D3", "d1", "d2", "d3",
        ])
        result = await self._client.score_dimension(
            dimension_name="Product Competitiveness",
            rubric=PRODUCT_COMPETITIVENESS_RUBRIC,
            input_data=relevant,
        )
        return _to_dimension_result(result)

    async def score_enterprise_differentiation(self, intake_data: dict[str, Any]) -> DimensionResult:
        """Gene D4: Enterprise Differentiation (AI + moat scoring)."""
        relevant = _extract_keys(intake_data, [
            "moats", "competitive_advantages", "brand_strength",
            "technology_ip", "scale_advantage", "network_effects",
            "switching_costs", "regulatory_license", "supply_chain_advantage",
            "D3", "d3",
        ])
        result = await self._client.score_dimension(
            dimension_name="Enterprise Differentiation",
            rubric=ENTERPRISE_DIFFERENTIATION_RUBRIC,
            input_data=relevant,
        )
        return _to_dimension_result(result)

    # ------------------------------------------------------------------
    # Business Model dimensions
    # ------------------------------------------------------------------

    async def score_business_model_clarity(self, intake_data: dict[str, Any]) -> DimensionResult:
        """BM D4: Business Model Clarity (AI-judged)."""
        relevant = _extract_keys(intake_data, [
            "value_proposition", "revenue_model", "revenue_mechanism",
            "cost_structure", "profit_formula", "business_model_description",
            "business_model_canvas", "elevator_pitch",
        ])
        result = await self._client.score_dimension(
            dimension_name="Business Model Clarity",
            rubric=BM_CLARITY_RUBRIC,
            input_data=relevant,
        )
        return _to_dimension_result(result)

    async def score_scalability(self, intake_data: dict[str, Any]) -> DimensionResult:
        """BM D6: Scalability (AI-judged + 10x test modifier)."""
        relevant = _extract_keys(intake_data, [
            "payment_flow", "people_flow", "logistics_flow", "information_flow",
            "geographic_presence", "expansion_plans", "channels",
            "central_infrastructure", "scalability_assessment",
            "num_locations", "growth_bottleneck",
        ])
        result = await self._client.score_dimension(
            dimension_name="Scalability",
            rubric=SCALABILITY_RUBRIC,
            input_data=relevant,
        )
        return _to_dimension_result(result)

    async def score_platform_potential(self, intake_data: dict[str, Any]) -> DimensionResult:
        """BM D8: Platform Potential (AI-judged)."""
        relevant = _extract_keys(intake_data, [
            "platform_model", "digital_infrastructure", "data_advantage",
            "network_effects", "marketplace_features", "digital_presence",
            "tech_stack", "online_revenue_pct",
        ])
        result = await self._client.score_dimension(
            dimension_name="Platform Potential",
            rubric=PLATFORM_POTENTIAL_RUBRIC,
            input_data=relevant,
        )
        return _to_dimension_result(result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_keys(data: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Extract relevant keys from intake data, including nested lookups."""
    result: dict[str, Any] = {}
    for key in keys:
        if key in data:
            result[key] = data[key]
        # Also check lowercase / uppercase variants
        lower = key.lower()
        upper = key.upper()
        if lower in data and lower not in result:
            result[lower] = data[lower]
        if upper in data and upper not in result:
            result[upper] = data[upper]
    # If very little data found, include all non-None top-level fields
    if len(result) < 2:
        for k, v in data.items():
            if v is not None:
                result[k] = v
    return result


def _to_dimension_result(raw: dict[str, Any]) -> DimensionResult:
    """Convert raw tool output to DimensionResult."""
    return DimensionResult(
        score=float(max(0, min(100, raw.get("score", 0)))),
        reasoning=raw.get("reasoning", ""),
        sub_scores=raw.get("sub_scores"),
    )
