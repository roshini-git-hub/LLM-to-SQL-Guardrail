from dataclasses import dataclass, field
from typing import List, Optional

from app.guardrail import policy
from app.guardrail.cost import CostEstimate
from app.guardrail.models import ValidationResult


@dataclass
class RiskAssessment:
    score: int
    decision: str  # ALLOW, REVIEW or BLOCK
    reasons: List[str] = field(default_factory=list)


def assess(validation: ValidationResult, cost: Optional[CostEstimate]) -> RiskAssessment:
    reasons = []

    # Hard rules: any blocking finding means BLOCK immediately
    if validation.blocked:
        for f in validation.findings:
            if f.severity == "block":
                reasons.append(f"[{f.rule}] {f.message}")
        return RiskAssessment(100, "BLOCK", reasons)

    score = 0

    # Soft rules from the validator
    for f in validation.findings:
        score += 10
        reasons.append(f"[{f.rule}] {f.message}")

    # Cost-based points
    if cost is not None:
        if cost.max_cost >= policy.COST_HIGH:
            score += 40
            reasons.append(f"Very high estimated cost ({cost.max_cost:,.0f})")
        elif cost.max_cost >= policy.COST_MEDIUM:
            score += 25
            reasons.append(f"High estimated cost ({cost.max_cost:,.0f})")
        elif cost.max_cost >= policy.COST_LOW:
            score += 10
            reasons.append(f"Moderate estimated cost ({cost.max_cost:,.0f})")

        plan_points = min(45, 15 * len(cost.warnings))
        score += plan_points
        reasons.extend(cost.warnings)

    score = min(score, 100)

    if score >= policy.BLOCK_AT:
        decision = "BLOCK"
    elif score >= policy.REVIEW_AT:
        decision = "REVIEW"
    else:
        decision = "ALLOW"

    return RiskAssessment(score, decision, reasons)
