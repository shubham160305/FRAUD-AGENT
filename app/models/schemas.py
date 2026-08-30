from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class Category(str, Enum):
    groceries  = "groceries"
    household  = "household"
    snacks     = "snacks"
    beverages  = "beverages"
    electronics = "electronics"
    gifting    = "gifting"
    food       = "food"


# ── SKU item ──────────────────────────────────────────────────────────────────

class SKUItem(BaseModel):
    sku_id: str
    name: str
    category: Category
    price_inr: int
    quantity: int = 1


# ── Fraud check request (Claude sends this before UPI fires) ──────────────────

class FraudCheckRequest(BaseModel):
    user_id: str
    merchant_id: str
    intent_string: str = Field(
        description="Raw user intent — 'order my usual groceries'"
    )
    basket: list[SKUItem]
    agent_platform: str = Field(default="claude")
    agent_token: Optional[str] = Field(
        default=None,
        description="Signed JWT from the AI platform proving agent identity"
    )


# ── Merchant registry entry ───────────────────────────────────────────────────

class MerchantProfile(BaseModel):
    merchant_id: str
    name: str
    registered_days_ago: int = Field(
        description="How long ago merchant was KYC verified"
    )
    avg_price_deviation_pct: float = Field(
        default=0.0,
        description="How far below market rate this merchant prices SKUs on average"
    )
    fulfilment_rate: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Order fulfilment rate (1.0 = perfect)"
    )
    dispute_rate: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Chargeback / dispute rate"
    )
    agentic_txn_share: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Fraction of transactions initiated by AI agents vs humans"
    )
    trusted: bool = Field(
        default=False,
        description="Manually verified trusted merchant — skips risk scoring"
    )


# ── Individual detector results ───────────────────────────────────────────────

class DetectorResult(BaseModel):
    passed: bool
    score: float = Field(description="Risk score 0–100. Higher = more suspicious.")
    reason: Optional[str] = None
    detail: Optional[str] = None


# ── Combined fraud decision ───────────────────────────────────────────────────

class FraudDecision(str, Enum):
    pass_   = "PASS"
    nudge   = "NUDGE"
    block   = "BLOCK"


class FraudCheckResponse(BaseModel):
    decision: FraudDecision
    overall_risk_score: float
    reason: Optional[str] = None

    # Individual detector breakdowns
    prompt_injection:    DetectorResult
    merchant_risk:       DetectorResult
    agent_identity:      DetectorResult

    basket_total_inr: int
    nudge_message: Optional[str] = None


# ── Velocity event (recorded per agentic transaction) ────────────────────────

class VelocityEvent(BaseModel):
    merchant_id: str
    user_id: str
    agent_session_id: str
    amount_inr: int
