"""
Detector 1 — Prompt Injection
Compares user's raw intent string against the actual SKU categories in the basket.
If unexpected categories appear, the basket was likely corrupted by a hidden instruction.

Logic:
  - Map intent keywords → expected categories
  - Check each basket SKU category against expected set
  - Score by: number of unexpected SKUs + their price weight
  - High-value unexpected SKUs score higher (₹999 earphone > ₹40 snack)
"""

from app.models.schemas import SKUItem, Category, DetectorResult

# Intent keyword → expected category mapping
INTENT_CATEGORY_MAP: dict[str, list[Category]] = {
    "groceries":   [Category.groceries, Category.household],
    "grocery":     [Category.groceries, Category.household],
    "vegetables":  [Category.groceries],
    "milk":        [Category.groceries],
    "dal":         [Category.groceries],
    "rice":        [Category.groceries],
    "snacks":      [Category.snacks, Category.beverages],
    "party":       [Category.snacks, Category.beverages, Category.household, Category.gifting],
    "food":        [Category.food, Category.snacks, Category.beverages],
    "dinner":      [Category.food],
    "lunch":       [Category.food],
    "breakfast":   [Category.food, Category.groceries],
    "household":   [Category.household],
    "cleaning":    [Category.household],
    "home":        [Category.household, Category.groceries],
    "usual":       [Category.groceries, Category.household, Category.food, Category.snacks],
    "order":       [Category.groceries, Category.food, Category.snacks, Category.household],
    "gift":        [Category.gifting],
    "drinks":      [Category.beverages],
    "beverages":   [Category.beverages],
}

# Categories that are NEVER expected from a grocery/food intent
HIGH_RISK_UNEXPECTED = {Category.electronics, Category.gifting}

BLOCK_THRESHOLD = 60.0
NUDGE_THRESHOLD = 30.0


def _expected_categories(intent: str) -> set[Category]:
    """Derive expected categories from user intent string."""
    intent_lower = intent.lower()
    expected = set()
    for keyword, cats in INTENT_CATEGORY_MAP.items():
        if keyword in intent_lower:
            expected.update(cats)
    # If nothing matched, allow broad set — don't over-block new users
    if not expected:
        expected = set(Category)
    return expected


def run(intent_string: str, basket: list[SKUItem]) -> DetectorResult:
    if not basket:
        return DetectorResult(passed=True, score=0.0, reason="Empty basket")

    expected = _expected_categories(intent_string)
    basket_total = sum(item.price_inr * item.quantity for item in basket)

    unexpected_skus = [
        item for item in basket
        if item.category not in expected
    ]

    if not unexpected_skus:
        return DetectorResult(
            passed=True,
            score=0.0,
            reason="All basket categories match intent"
        )

    # Score: weighted by unexpected SKU value as share of basket total
    unexpected_value = sum(i.price_inr * i.quantity for i in unexpected_skus)
    value_weight = (unexpected_value / basket_total) * 100 if basket_total > 0 else 0

    # High-risk unexpected categories push score up harder
    high_risk_count = sum(
        1 for i in unexpected_skus if i.category in HIGH_RISK_UNEXPECTED
    )
    risk_boost = high_risk_count * 20

    score = min(100.0, value_weight + risk_boost)

    unexpected_names = [i.name for i in unexpected_skus]
    unexpected_cats  = list({i.category for i in unexpected_skus})

    passed = score < BLOCK_THRESHOLD

    return DetectorResult(
        passed=passed,
        score=round(score, 1),
        reason="prompt_injection_suspected" if not passed else "minor_category_deviation",
        detail=(
            f"Intent '{intent_string}' expected {[c.value for c in expected]}. "
            f"Unexpected items: {unexpected_names} "
            f"(categories: {[c.value for c in unexpected_cats]}). "
            f"Unexpected value: ₹{unexpected_value} ({value_weight:.0f}% of basket)."
        )
    )
