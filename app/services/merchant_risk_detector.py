"""
Detector 2 — Counterfeit Merchant
Scores merchant risk in real time using behavioural signals.
A merchant can pass KYC and then go rogue — this catches post-KYC behaviour.

Risk signals (weighted):
  - New merchant (<60 days)            → +25 pts
  - Price far below market (>15%)      → +30 pts
  - High agentic txn share (>80%)      → +20 pts
  - Low fulfilment rate (<70%)          → +15 pts
  - High dispute rate (>10%)           → +10 pts

Score 0–30  → PASS
Score 30–60 → NUDGE (new merchant warning)
Score >60   → BLOCK (counterfeit signature)
"""

from app.models.schemas import MerchantProfile, DetectorResult

BLOCK_THRESHOLD = 60.0
NUDGE_THRESHOLD = 30.0


def _score_profile(p: MerchantProfile) -> tuple[float, list[str]]:
    score = 0.0
    flags = []

    if p.registered_days_ago < 30:
        score += 25
        flags.append(f"Very new merchant ({p.registered_days_ago} days old)")
    elif p.registered_days_ago < 60:
        score += 15
        flags.append(f"New merchant ({p.registered_days_ago} days old)")

    if p.avg_price_deviation_pct > 25:
        score += 30
        flags.append(f"Price {p.avg_price_deviation_pct:.0f}% below market — extreme undercutting")
    elif p.avg_price_deviation_pct > 15:
        score += 20
        flags.append(f"Price {p.avg_price_deviation_pct:.0f}% below market")

    if p.agentic_txn_share > 0.85:
        score += 20
        flags.append(f"Agentic txn share {p.agentic_txn_share*100:.0f}% — almost exclusively bots")
    elif p.agentic_txn_share > 0.70:
        score += 10
        flags.append(f"High agentic txn share {p.agentic_txn_share*100:.0f}%")

    if p.fulfilment_rate < 0.60:
        score += 15
        flags.append(f"Very low fulfilment rate {p.fulfilment_rate*100:.0f}%")
    elif p.fulfilment_rate < 0.80:
        score += 8
        flags.append(f"Low fulfilment rate {p.fulfilment_rate*100:.0f}%")

    if p.dispute_rate > 0.15:
        score += 10
        flags.append(f"High dispute rate {p.dispute_rate*100:.0f}%")
    elif p.dispute_rate > 0.08:
        score += 5
        flags.append(f"Elevated dispute rate {p.dispute_rate*100:.0f}%")

    return min(100.0, score), flags


def run(merchant_id: str) -> DetectorResult:
    from app.services.merchant_registry import get

    profile = get(merchant_id)

    if not profile:
        return DetectorResult(
            passed=False,
            score=100.0,
            reason="unknown_merchant",
            detail=f"Merchant '{merchant_id}' not in Razorpay registry. Block until verified."
        )

    # Trusted large merchants skip scoring entirely
    if profile.trusted:
        return DetectorResult(
            passed=True,
            score=0.0,
            reason="trusted_merchant",
            detail=f"{profile.name} is a verified trusted merchant."
        )

    score, flags = _score_profile(profile)
    passed = score < BLOCK_THRESHOLD

    if score >= BLOCK_THRESHOLD:
        reason = "counterfeit_merchant_suspected"
    elif score >= NUDGE_THRESHOLD:
        reason = "new_merchant_warning"
    else:
        reason = "merchant_risk_acceptable"

    return DetectorResult(
        passed=passed,
        score=round(score, 1),
        reason=reason,
        detail=" | ".join(flags) if flags else "No risk signals detected."
    )
