from src.agent_state import create_initial_state
from src.governance.decision import calculate_confidence
from src.governance.events import apply_event, make_event
from src.grocery.basket import build_basket_summary
from src.grocery.extraction import extract_items_from_plan, normalize_input_items
from src.grocery.price_provider import EstimatedCatalogPriceProvider
from src.grocery.profile import GroceryProfileFacts


def build_smart_grocery(
    *,
    weekly_plan: str | None,
    shopping_items: list[dict] | None,
    profile_facts: GroceryProfileFacts,
    location_context: str | None = None,
) -> tuple[dict, dict]:
    items = normalize_input_items(shopping_items)
    source = "shopping_items"
    if not items:
        items = extract_items_from_plan(weekly_plan)
        source = "weekly_plan"

    state = create_initial_state(
        istek="Smart Grocery",
        profil_ozeti=profile_facts.summary,
        hafiza=[],
    )
    state = apply_event(
        state,
        "GroceryListGenerated",
        "smart_grocery",
        metadata={"item_count": len(items), "source": source},
    )

    price_provider = EstimatedCatalogPriceProvider()
    basket = build_basket_summary(
        items,
        price_provider=price_provider,
        allergies=profile_facts.allergies,
        diseases=profile_facts.diseases,
        medications=profile_facts.medications,
        location_context=location_context,
    )
    included_count = len(basket["items"])
    excluded_count = len(basket["excluded_items"])
    state["governance_events"] = list(state.get("governance_events") or []) + [
        make_event(
            "HealthComplianceChecked",
            "health_compliance",
            status="blocked" if basket["avoid_items"] else "ok",
            metadata={
                "safe": basket["health_safe_total_items"],
                "caution": basket["caution_items"],
                "avoid": basket["avoid_items"],
                "unknown": basket["unknown_items"],
                "risk_items": basket["risk_items"],
            },
        ),
        make_event(
            "PriceEstimationAttempted",
            "estimated_price_bands",
            metadata={
                "included_item_count": included_count,
                "excluded_item_count": excluded_count,
                "price_catalog_version": basket["price_catalog_version"],
                "live_price": False,
            },
        ),
        make_event(
            "GroceryBasketSuggested",
            "smart_grocery",
            metadata={
                "included_item_count": included_count,
                "excluded_item_count": excluded_count,
                "estimated_min_total": basket["estimated_min_total"],
                "estimated_max_total": basket["estimated_max_total"],
            },
        ),
    ]

    is_safe = basket["avoid_items"] == 0
    confidence = calculate_confidence(safe=is_safe, evidence_found=False, citations=[])
    component_versions = dict(state.get("component_versions") or {})
    component_versions["smart_grocery_price_provider"] = basket["price_catalog_version"]
    state.update(
        {
            "hedef_islem": "SMART_GROCERY",
            "guvenli_mi": is_safe,
            "risk_score": 0.85 if basket["avoid_items"] else (0.45 if basket["caution_items"] else 0.25),
            "confidence": confidence,
            "citations": [],
            "component_versions": component_versions,
        }
    )
    return basket, state
