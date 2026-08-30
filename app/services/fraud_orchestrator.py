"""
Fraud orchestrator — runs all three detectors and combines into one decision.

Decision logic:
  ANY detector score >= 60   → BLOCK
  ANY detector score >= 30   → NUDGE  (unless another already BLOCK)
  All detectors score < 30   → PASS

Nudge message: used when merchant is new but not yet confirmed rogue.
Block reason: most severe detector's reason surfaces to user.
"""

from app.models.schemas import (
    FraudCheckRequest, FraudCheckResponse, FraudDecision, DetectorResult
)
from app.services import (
    prompt_injection_detector,
    merchant_risk_detector,
    agent_identity_detector,
)

BLOCK_THRESHOLD = 60.0
NUDGE_THRESHOLD = 30.0

NEW_MERCHANT_NUDGE = (
    "This is a newer merchant on Razorpay. "
    "Your order looks fine — confirm to proceed or cancel to review."
)


def run(request: FraudCheckRequest) -> FraudCheckResponse:
    basket_total = sum(i.price_inr * i.quantity for i in request.basket)

    # ── Run all three detectors ───────────────────────────────────────────────
    injection_result = prompt_injection_detector.run(
        request.intent_string, request.basket
    )
    merchant_result = merchant_risk_detector.run(request.merchant_id)
    identity_result = agent_identity_detector.run(
        request.agent_token, request.user_id, request.merchant_id
    )

    results = [injection_result, merchant_result, identity_result]

    # ── Combine into overall score (max of three) ─────────────────────────────
    overall_score = max(r.score for r in results)

    # ── Decision ──────────────────────────────────────────────────────────────
    if overall_score >= BLOCK_THRESHOLD:
        decision = FraudDecision.block
        # Surface reason from the highest-scoring detector
        worst = max(results, key=lambda r: r.score)
        reason = worst.reason
        nudge_message = None

    elif overall_score >= NUDGE_THRESHOLD:
        decision = FraudDecision.nudge
        reason = "elevated_risk_detected"
        nudge_message = NEW_MERCHANT_NUDGE

    else:
        decision = FraudDecision.pass_
        reason = None
        nudge_message = None

    return FraudCheckResponse(
        decision=decision,
        overall_risk_score=round(overall_score, 1),
        reason=reason,
        prompt_injection=injection_result,
        merchant_risk=merchant_result,
        agent_identity=identity_result,
        basket_total_inr=basket_total,
        nudge_message=nudge_message,
    )
