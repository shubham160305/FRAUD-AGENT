"""
Test suite — Razorpay Fraud Guard Agent (Problem #2)
Covers all three attack types + clean passes + edge cases.
"""

import json, time
import pytest
from app.models.schemas import FraudCheckRequest, SKUItem, Category, FraudDecision
from app.services import fraud_orchestrator
from app.services.velocity_tracker import _merchant_events


@pytest.fixture(autouse=True)
def clear_velocity():
    """Reset velocity tracker between tests."""
    _merchant_events.clear()
    yield


def make_request(basket, intent="order my usual groceries",
                 merchant="zepto", user="user_priya", token=None):
    return FraudCheckRequest(
        user_id=user,
        merchant_id=merchant,
        intent_string=intent,
        basket=basket,
        agent_token=token,
    )


def valid_token(user_id="user_priya", session_id="sess_abc"):
    return json.dumps({
        "platform": "claude",
        "version": "sonnet-4-6",
        "session_id": session_id,
        "user_id_hash": user_id,
        "issued_at": int(time.time()),
        "signature": "mock_sig_xyz",
    })


GROCERY_BASKET = [
    SKUItem(sku_id="z001", name="Amul Milk 1L",      category=Category.groceries, price_inr=68),
    SKUItem(sku_id="z002", name="Aashirvaad Atta 5kg", category=Category.groceries, price_inr=290),
]

INJECTION_BASKET = [
    SKUItem(sku_id="z001", name="Amul Milk 1L",      category=Category.groceries,   price_inr=68),
    SKUItem(sku_id="e001", name="boAt Airdopes 141", category=Category.electronics, price_inr=999),
]


# ── Attack 1: Prompt Injection ────────────────────────────────────────────────

def test_prompt_injection_blocked():
    """Electronics added to grocery order → BLOCK."""
    result = fraud_orchestrator.run(make_request(
        INJECTION_BASKET,
        intent="order my usual groceries",
        token=valid_token()
    ))
    assert result.decision == FraudDecision.block
    assert result.prompt_injection.passed is False
    assert "electronics" in result.prompt_injection.detail.lower()


def test_gifting_in_grocery_blocked():
    """Ferrero Rocher in grocery order → BLOCK."""
    basket = [
        SKUItem(sku_id="z001", name="Amul Milk", category=Category.groceries, price_inr=68),
        SKUItem(sku_id="g001", name="Ferrero Rocher", category=Category.gifting, price_inr=650),
    ]
    result = fraud_orchestrator.run(make_request(basket, token=valid_token()))
    assert result.decision == FraudDecision.block
    assert result.prompt_injection.passed is False


def test_party_intent_allows_snacks():
    """Party intent — snacks and beverages should pass."""
    basket = [
        SKUItem(sku_id="s001", name="Lays",       category=Category.snacks,     price_inr=40),
        SKUItem(sku_id="b001", name="Coca-Cola",  category=Category.beverages,  price_inr=60),
    ]
    result = fraud_orchestrator.run(make_request(
        basket, intent="get me snacks for the party", token=valid_token()
    ))
    assert result.prompt_injection.passed is True


def test_clean_grocery_passes_injection():
    """Normal grocery order — no injection."""
    result = fraud_orchestrator.run(make_request(GROCERY_BASKET, token=valid_token()))
    assert result.prompt_injection.passed is True
    assert result.prompt_injection.score == 0.0


# ── Attack 2: Counterfeit Merchant ────────────────────────────────────────────

def test_counterfeit_merchant_blocked():
    """SportXpress — rogue merchant signature → BLOCK."""
    result = fraud_orchestrator.run(make_request(
        GROCERY_BASKET, merchant="sportxpress", token=valid_token()
    ))
    assert result.decision == FraudDecision.block
    assert result.merchant_risk.passed is False
    assert result.merchant_risk.score >= 60


def test_trusted_merchant_passes_risk():
    """Zepto — trusted merchant always score 0."""
    result = fraud_orchestrator.run(make_request(GROCERY_BASKET, token=valid_token()))
    assert result.merchant_risk.passed is True
    assert result.merchant_risk.score == 0.0


def test_new_merchant_has_nonzero_risk_score():
    """FreshMart — new merchant scores above 0 but below block threshold."""
    result = fraud_orchestrator.run(make_request(
        GROCERY_BASKET, merchant="freshmart", token=valid_token()
    ))
    # New merchant carries nonzero risk — not trusted like Zepto
    assert result.merchant_risk.score > 0
    # But not rogue either — should not be hard-blocked on score alone
    assert result.merchant_risk.score < 60
    assert "new merchant" in result.merchant_risk.detail.lower()


def test_unknown_merchant_blocked():
    """Unregistered merchant → BLOCK immediately."""
    result = fraud_orchestrator.run(make_request(
        GROCERY_BASKET, merchant="shady_store_xyz", token=valid_token()
    ))
    assert result.decision == FraudDecision.block
    assert result.merchant_risk.reason == "unknown_merchant"


# ── Attack 3: Agent Impersonation ─────────────────────────────────────────────

def test_no_token_raises_score():
    """Missing agent token — score increases."""
    result = fraud_orchestrator.run(make_request(GROCERY_BASKET, token=None))
    assert result.agent_identity.score >= 50


def test_expired_token_penalised():
    """Old token — should raise risk score."""
    old_token = json.dumps({
        "platform": "claude",
        "version": "sonnet-4-6",
        "session_id": "sess_old",
        "user_id_hash": "user_priya",
        "issued_at": int(time.time()) - 600,   # 10 minutes ago
        "signature": "mock_sig",
    })
    result = fraud_orchestrator.run(make_request(GROCERY_BASKET, token=old_token))
    assert result.agent_identity.score > 0


def test_unknown_platform_penalised():
    """Unknown AI platform → identity risk score increases."""
    bad_token = json.dumps({
        "platform": "evil_bot",
        "session_id": "sess_evil",
        "issued_at": int(time.time()),
        "signature": "fake",
    })
    result = fraud_orchestrator.run(make_request(GROCERY_BASKET, token=bad_token))
    assert result.agent_identity.score >= 40


def test_valid_token_low_score():
    """Valid Claude token — identity score should be low."""
    result = fraud_orchestrator.run(make_request(GROCERY_BASKET, token=valid_token()))
    # With valid token + trusted merchant + clean basket → PASS
    assert result.agent_identity.score < 60


# ── Full clean pass ───────────────────────────────────────────────────────────

def test_full_clean_pass():
    """
    Trusted merchant + clean basket + valid token + intent matches
    → PASS with low overall score.
    """
    result = fraud_orchestrator.run(make_request(GROCERY_BASKET, token=valid_token()))
    assert result.decision == FraudDecision.pass_
    assert result.overall_risk_score < 30
    assert result.prompt_injection.passed is True
    assert result.merchant_risk.passed is True


# ── Velocity detection ────────────────────────────────────────────────────────

def test_velocity_same_session_multiple_users():
    """Same session_id across many users → velocity flag."""
    from app.services.velocity_tracker import record, SESSION_USER_LIMIT

    session = "stolen_session_123"
    for i in range(SESSION_USER_LIMIT + 2):
        result = record("zepto", f"user_{i}", session)

    assert result["flagged"] is True
    assert any("session" in f.lower() for f in result["flags"])
