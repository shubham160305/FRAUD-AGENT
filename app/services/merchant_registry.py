"""
Merchant registry — stores risk profiles for known merchants.
Production: replace with Postgres + real-time signals from Razorpay's merchant data.
"""

from app.models.schemas import MerchantProfile

_registry: dict[str, MerchantProfile] = {
    # Trusted large-platform merchants — always pass
    "zepto": MerchantProfile(
        merchant_id="zepto", name="Zepto",
        registered_days_ago=900, avg_price_deviation_pct=2.0,
        fulfilment_rate=0.97, dispute_rate=0.008,
        agentic_txn_share=0.35, trusted=True
    ),
    "swiggy": MerchantProfile(
        merchant_id="swiggy", name="Swiggy",
        registered_days_ago=1800, avg_price_deviation_pct=1.5,
        fulfilment_rate=0.95, dispute_rate=0.010,
        agentic_txn_share=0.30, trusted=True
    ),
    "zomato": MerchantProfile(
        merchant_id="zomato", name="Zomato",
        registered_days_ago=2100, avg_price_deviation_pct=1.0,
        fulfilment_rate=0.96, dispute_rate=0.009,
        agentic_txn_share=0.28, trusted=True
    ),
    # New legitimate merchant — moderate risk
    "freshmart": MerchantProfile(
        merchant_id="freshmart", name="FreshMart",
        registered_days_ago=45, avg_price_deviation_pct=8.0,
        fulfilment_rate=0.88, dispute_rate=0.04,
        agentic_txn_share=0.50, trusted=False
    ),
    # Simulated counterfeit merchant — should be blocked
    "sportxpress": MerchantProfile(
        merchant_id="sportxpress", name="SportXpress",
        registered_days_ago=18, avg_price_deviation_pct=28.0,
        fulfilment_rate=0.40, dispute_rate=0.22,
        agentic_txn_share=0.92, trusted=False
    ),
}


def get(merchant_id: str) -> MerchantProfile | None:
    return _registry.get(merchant_id)


def register(profile: MerchantProfile) -> MerchantProfile:
    _registry[profile.merchant_id] = profile
    return profile


def all_merchants() -> list[MerchantProfile]:
    return list(_registry.values())
