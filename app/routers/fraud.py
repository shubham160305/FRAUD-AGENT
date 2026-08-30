from fastapi import APIRouter
from app.models.schemas import FraudCheckRequest, FraudCheckResponse
from app.services import fraud_orchestrator
from app.services.velocity_tracker import get_stats

router = APIRouter()


@router.post("/check", response_model=FraudCheckResponse, summary="Fraud check — all three detectors")
def fraud_check(request: FraudCheckRequest):
    """
    The core intercept endpoint.
    Claude calls this BEFORE triggering UPI Reserve Pay.

    Runs in parallel:
      1. Prompt injection detector
      2. Merchant risk detector
      3. Agent identity + velocity detector

    Returns:
      PASS  → proceed to UPI
      NUDGE → surface warning to user, wait for confirm
      BLOCK → reject, surface reason to user
    """
    return fraud_orchestrator.run(request)


@router.get("/velocity/{merchant_id}", summary="Velocity stats for a merchant")
def velocity_stats(merchant_id: str):
    """
    Returns real-time transaction velocity for a merchant.
    Used by Razorpay fraud team to monitor for coordinated attacks.
    """
    return get_stats(merchant_id)
