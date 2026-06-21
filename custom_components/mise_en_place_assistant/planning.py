"""Shared inventory planning and freshness ranking helpers."""

from __future__ import annotations

from datetime import date
import re
from typing import Any, Callable, Protocol

from .const import DEFAULT_UNIT

_MAX_DATE = date.max
FREEZER_DUE_DAYS_BY_NATURE = {
    "fish": 60,
    "seafood": 60,
    "dairy": 60,
    "egg": 60,
    "poultry": 120,
    "red_meat": 120,
    "pork": 120,
    "vegetarian": 150,
    "leafy_green": 150,
    "cruciferous": 180,
    "root": 180,
    "squash": 180,
    "legume": 180,
    "mixed_vegetable": 180,
    "rice": 90,
    "pasta": 90,
    "potato": 90,
    "bread": 90,
    "grain": 120,
    "noodle": 90,
    "corn": 180,
}
FREEZER_DUE_DAYS_BY_CONTENT = {
    "meal": 90,
    "recipe": 90,
    "ingredient": 180,
}
STORAGE_DUE_DAYS_BY_NATURE = {
    "freezer": FREEZER_DUE_DAYS_BY_NATURE,
    "fridge": {
        "fish": 2,
        "seafood": 2,
        "poultry": 3,
        "red_meat": 3,
        "pork": 3,
        "dairy": 7,
        "egg": 21,
        "vegetarian": 5,
        "leafy_green": 5,
        "cruciferous": 7,
        "root": 14,
        "squash": 10,
        "legume": 5,
        "mixed_vegetable": 5,
        "rice": 4,
        "pasta": 4,
        "potato": 5,
        "bread": 7,
        "grain": 5,
        "noodle": 4,
        "corn": 5,
    },
    "counter": {
        "fish": 1,
        "seafood": 1,
        "poultry": 1,
        "red_meat": 1,
        "pork": 1,
        "dairy": 1,
        "egg": 1,
        "vegetarian": 1,
        "leafy_green": 1,
        "cruciferous": 2,
        "mixed_vegetable": 2,
        "bread": 3,
        "grain": 7,
        "root": 7,
        "squash": 14,
    },
    "pantry": {
        "rice": 365,
        "pasta": 365,
        "grain": 180,
        "noodle": 365,
        "legume": 365,
        "corn": 365,
        "bread": 5,
        "root": 30,
        "squash": 60,
        "dairy": 30,
    },
    "dry_storage": {
        "rice": 365,
        "pasta": 365,
        "grain": 180,
        "noodle": 365,
        "legume": 365,
        "corn": 365,
        "bread": 5,
        "root": 30,
        "squash": 60,
        "dairy": 30,
    },
    "cellar": {
        "root": 60,
        "squash": 90,
        "rice": 180,
        "grain": 180,
        "legume": 180,
        "corn": 180,
        "bread": 5,
    },
}
STORAGE_DUE_DAYS_BY_CONTENT = {
    "freezer": FREEZER_DUE_DAYS_BY_CONTENT,
    "fridge": {"meal": 4, "recipe": 4, "ingredient": 7},
    "counter": {"meal": 1, "recipe": 1, "ingredient": 3},
    "pantry": {"meal": 1, "recipe": 1, "ingredient": 180},
    "dry_storage": {"meal": 1, "recipe": 1, "ingredient": 180},
    "cellar": {"meal": 1, "recipe": 1, "ingredient": 60},
}


class ShelfLifePolicy(Protocol):
    """Resolve shelf-life days from storage context and item nature."""

    def storage_due_days(
        self,
        *,
        location_type: Any,
        content_kind: Any = "",
        storage_behavior: Any = "",
        meal_component_role: Any = "",
        meal_component_family: Any = "",
        meal_role: Any = "",
    ) -> int | None:
        """Return shelf-life days, or None when the provider has no answer."""


class BuiltInShelfLifePolicy:
    """Built-in shelf-life defaults used when no provider owns the answer."""

    def storage_due_days(
        self,
        *,
        location_type: Any,
        content_kind: Any = "",
        storage_behavior: Any = "",
        meal_component_role: Any = "",
        meal_component_family: Any = "",
        meal_role: Any = "",
    ) -> int | None:
        """Return storage shelf-life days from location type and item nature."""
        location_key = _nature_key(location_type)
        if location_key not in STORAGE_DUE_DAYS_BY_CONTENT:
            return None
        family = _nature_key(meal_component_family)
        nature_days = STORAGE_DUE_DAYS_BY_NATURE.get(location_key, {})
        if family in nature_days:
            return nature_days[family]
        role = _nature_key(meal_component_role)
        if role == "starch":
            return {
                "freezer": 90,
                "fridge": 4,
                "counter": 2,
                "pantry": 180,
                "dry_storage": 180,
                "cellar": 60,
            }.get(location_key)
        if role == "veggie":
            return {
                "freezer": 180,
                "fridge": 5,
                "counter": 2,
                "pantry": 14,
                "dry_storage": 14,
                "cellar": 45,
            }.get(location_key)
        if role == "protein":
            return {
                "freezer": 120,
                "fridge": 3,
                "counter": 1,
                "pantry": 1,
                "dry_storage": 1,
                "cellar": 1,
            }.get(location_key)
        meal_role_key = _nature_key(meal_role)
        if meal_role_key in {"prepared_component", "staple"}:
            return {
                "freezer": 90,
                "fridge": 4,
                "counter": 1,
                "pantry": 7,
                "dry_storage": 7,
                "cellar": 7,
            }.get(location_key)
        storage_key = _nature_key(storage_behavior)
        if storage_key == location_key == "freezer":
            return 365
        return STORAGE_DUE_DAYS_BY_CONTENT[location_key].get(_nature_key(content_kind), 120)


_SHELF_LIFE_POLICY: ShelfLifePolicy = BuiltInShelfLifePolicy()


def set_shelf_life_policy(policy: ShelfLifePolicy | None) -> None:
    """Override the shelf-life provider boundary for tests or future integrations."""
    global _SHELF_LIFE_POLICY
    _SHELF_LIFE_POLICY = policy or BuiltInShelfLifePolicy()


def parse_inventory_date(value: Any) -> date | None:
    """Parse supported inventory date values without raising."""
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def date_in_range(value: Any, start: date, end: date) -> bool:
    """Return whether a stored inventory date falls in an inclusive range."""
    parsed = parse_inventory_date(value)
    return bool(parsed and start <= parsed <= end)


def freshness_status(value: Any, *, today: date | None = None) -> dict[str, Any]:
    """Return score and display status for one best-before date."""
    parsed = parse_inventory_date(value)
    if not parsed:
        return {"score": 0, "status": "", "days": None}
    days = (parsed - (today or date.today())).days
    if days < 0:
        return {"score": 6, "status": "stale", "days": days}
    if days <= 1:
        return {"score": 8, "status": "due", "days": days}
    if days <= 3:
        return {"score": 6, "status": "soon", "days": days}
    if days <= 7:
        return {"score": 3, "status": "upcoming", "days": days}
    return {"score": 0, "status": "", "days": days}


def freshness_rank_key(value: Any) -> tuple[date, str]:
    """Sort dated inventory before undated or malformed rows."""
    parsed = parse_inventory_date(value)
    return (parsed or _MAX_DATE, "" if parsed else str(value or ""))


def freezer_due_date(
    *,
    content_kind: Any = "",
    storage_behavior: Any = "",
    meal_component_role: Any = "",
    meal_component_family: Any = "",
    meal_role: Any = "",
    frozen_on: date | None = None,
) -> str:
    """Return the freezer-adjusted due date for an item's planning nature."""
    due_date = storage_due_date(
        location_type="freezer",
        content_kind=content_kind,
        storage_behavior=storage_behavior,
        meal_component_role=meal_component_role,
        meal_component_family=meal_component_family,
        meal_role=meal_role,
        stored_on=frozen_on,
    )
    return due_date or date.fromordinal((frozen_on or date.today()).toordinal() + 120).isoformat()


def storage_due_date(
    *,
    location_type: Any,
    content_kind: Any = "",
    storage_behavior: Any = "",
    meal_component_role: Any = "",
    meal_component_family: Any = "",
    meal_role: Any = "",
    stored_on: date | None = None,
) -> str | None:
    """Return a storage-adjusted due date for an item's planning nature."""
    stored_on = stored_on or date.today()
    days = storage_due_days(
        location_type=location_type,
        content_kind=content_kind,
        storage_behavior=storage_behavior,
        meal_component_role=meal_component_role,
        meal_component_family=meal_component_family,
        meal_role=meal_role,
    )
    return date.fromordinal(stored_on.toordinal() + days).isoformat() if days is not None else None


def freezer_due_days(
    *,
    content_kind: Any = "",
    storage_behavior: Any = "",
    meal_component_role: Any = "",
    meal_component_family: Any = "",
    meal_role: Any = "",
) -> int:
    """Return freezer shelf-life days from item nature metadata."""
    days = storage_due_days(
        location_type="freezer",
        content_kind=content_kind,
        storage_behavior=storage_behavior,
        meal_component_role=meal_component_role,
        meal_component_family=meal_component_family,
        meal_role=meal_role,
    )
    return days if days is not None else 120


def storage_due_days(
    *,
    location_type: Any,
    content_kind: Any = "",
    storage_behavior: Any = "",
    meal_component_role: Any = "",
    meal_component_family: Any = "",
    meal_role: Any = "",
) -> int | None:
    """Return storage shelf-life days from location type and item nature."""
    return _SHELF_LIFE_POLICY.storage_due_days(
        location_type=location_type,
        content_kind=content_kind,
        storage_behavior=storage_behavior,
        meal_component_role=meal_component_role,
        meal_component_family=meal_component_family,
        meal_role=meal_role,
    )


def meal_candidate_rank(candidate: dict[str, Any]) -> tuple:
    """Rank meal candidates by shared use-soonest freshness signals."""
    return (
        freshness_rank_key(candidate.get("best_before_date")),
        0 if candidate.get("opened_date") else 1,
        candidate.get("available", 0),
        candidate.get("updated_at") or "",
        candidate.get("label") or "",
    )


def word_tokens(value: Any) -> list[str]:
    """Normalize labels and log text into comparable tokens."""
    return re.findall(r"[a-z0-9]+", str(value).casefold())


def _nature_key(value: Any) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def recipe_suggestions_data(
    *,
    recipes: list[dict[str, Any]],
    item_totals: list[dict[str, Any]],
    containers: list[dict[str, Any]],
    log_for: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
) -> list[dict[str, Any]]:
    """Score recipes against stock, prioritizing the best dated matching row."""
    index = RecipeStockIndex(item_totals=item_totals, containers=containers)
    suggestions: list[dict[str, Any]] = []
    for recipe in recipes:
        ingredients = [
            ingredient
            for ingredient in recipe.get("ingredients") or []
            if isinstance(ingredient, dict) and (ingredient.get("label") or ingredient.get("original"))
        ]
        if not ingredients:
            continue
        matched: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        best_before: list[dict[str, Any]] = []
        score = 0
        for ingredient in ingredients:
            stock = index.match_ingredient(ingredient)
            if not stock:
                missing.append(recipe_ingredient_summary(ingredient))
                continue
            urgency = freshness_status(stock.get("best_before_date"))
            matched.append(
                {
                    **recipe_ingredient_summary(ingredient),
                    "stock_label": stock.get("label") or "",
                    "stock_quantity": stock_quantity_label(stock),
                    "best_before_date": stock.get("best_before_date") or "",
                    "best_before_status": urgency["status"],
                }
            )
            score += 10 + urgency["score"]
            if urgency["status"] in {"due", "soon", "stale"}:
                best_before.append(
                    {
                        "label": stock.get("label") or ingredient.get("label") or "Ingredient",
                        "best_before_date": stock.get("best_before_date"),
                        "status": urgency["status"],
                        "days": urgency["days"],
                    }
                )
        if not matched:
            continue
        coverage = len(matched) / len(ingredients)
        score += round(coverage * 20)
        if missing:
            score -= len(missing) * 4
        best_before = sorted(best_before, key=lambda row: freshness_rank_key(row.get("best_before_date")))
        suggestions.append(
            {
                "id": recipe.get("id") or recipe.get("slug") or recipe.get("label"),
                "label": recipe.get("label") or "Recipe",
                "provider": recipe.get("provider") or "",
                "score": score,
                "coverage": round(coverage, 2),
                "matched_count": len(matched),
                "ingredient_count": len(ingredients),
                "missing_count": len(missing),
                "matched": matched[:6],
                "missing": missing[:6],
                "best_before": best_before[:4],
                "reason": recipe_suggestion_reason(matched, missing, best_before),
                "log": log_for(recipe) if log_for else None,
            }
        )
    return sorted(suggestions, key=lambda row: (-row["score"], row["label"].casefold()))[:8]


class RecipeStockIndex:
    """Indexed stock rows for recipe ingredient matching."""

    def __init__(self, *, item_totals: list[dict[str, Any]], containers: list[dict[str, Any]]) -> None:
        self.rows = _stock_rows(item_totals=item_totals, containers=containers)
        self.by_id: dict[str, list[dict[str, Any]]] = {}
        self.token_rows: list[tuple[set[str], dict[str, Any]]] = []
        for row in self.rows:
            for value in (row.get("item_id"), row.get("product_id")):
                if value:
                    self.by_id.setdefault(str(value).casefold(), []).append(row)
            tokens = {token for token in word_tokens(row.get("label") or "") if len(token) > 2}
            if tokens:
                self.token_rows.append((tokens, row))

    def match_ingredient(self, ingredient: dict[str, Any]) -> dict[str, Any] | None:
        """Return the freshest, use-soonest stock row for an ingredient."""
        ids = {
            str(value).casefold()
            for value in (ingredient.get("grocy_product_id"), ingredient.get("food_id"), ingredient.get("product_id"))
            if value
        }
        id_matches = [row for value in ids for row in self.by_id.get(value, [])]
        if id_matches:
            return min(id_matches, key=stock_row_rank)

        ingredient_tokens = {
            token
            for token in word_tokens(f"{ingredient.get('label', '')} {ingredient.get('original', '')}")
            if len(token) > 2
        }
        if not ingredient_tokens:
            return None
        candidates: list[tuple[int, tuple, dict[str, Any]]] = []
        for label_tokens, row in self.token_rows:
            overlap = len(ingredient_tokens & label_tokens)
            if overlap:
                candidates.append((-overlap, stock_row_rank(row), row))
        if not candidates:
            return None
        return min(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]


def stock_row_rank(row: dict[str, Any]) -> tuple:
    """Rank stock rows by best-before first, then opened and display label."""
    return (
        freshness_rank_key(row.get("best_before_date")),
        0 if row.get("opened_date") else 1,
        row.get("label") or "",
        row.get("source") or "",
    )


def recipe_ingredient_summary(ingredient: dict[str, Any]) -> dict[str, Any]:
    """Return panel-safe ingredient text."""
    quantity = ingredient.get("quantity")
    amount = f"{quantity:g}" if isinstance(quantity, (int, float)) else str(quantity or "").strip()
    unit = str(ingredient.get("unit") or "").strip()
    return {
        "label": ingredient.get("label") or ingredient.get("original") or "Ingredient",
        "amount": " ".join(part for part in (amount, unit) if part),
        "original": ingredient.get("original") or "",
    }


def stock_quantity_label(stock: dict[str, Any]) -> str:
    """Return a compact stock quantity label."""
    if stock.get("quantity") is not None and stock.get("unit"):
        return f"{stock.get('quantity')} {stock.get('unit')}".strip()
    return format_quantities(stock.get("quantities") or {})


def format_quantities(quantities: dict[str, Any]) -> str:
    """Format simple quantity maps for compact panel rows."""
    return " + ".join(f"{amount} {unit}" for unit, amount in quantities.items()) or "Ready"


def recipe_suggestion_reason(
    matched: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    best_before: list[dict[str, Any]],
) -> str:
    """Explain why a recipe was suggested."""
    if best_before:
        first = best_before[0]
        return f"Uses {first.get('label') or 'stock'} before {first.get('best_before_date')} and matches {len(matched)} stocked ingredients."
    if missing:
        return f"Matches {len(matched)} stocked ingredients; {len(missing)} ingredients still need shopping or review."
    return f"All {len(matched)} known ingredients are stocked."


def _stock_rows(*, item_totals: list[dict[str, Any]], containers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    product_index = {str(item.get("product_id") or ""): item for item in item_totals if item.get("product_id")}
    rows: list[dict[str, Any]] = []
    seen_containers: set[str] = set()
    for item in item_totals:
        if _as_float(item.get("quantity")) > 0 or item.get("quantities"):
            rows.append(_stock_row_from_item(item))
        for container in item.get("physical_containers") or []:
            row = _stock_row_from_container(container, item)
            if row:
                seen_containers.add(str(container.get("tag_id") or id(container)))
                rows.append(row)
    for container in containers:
        key = str(container.get("tag_id") or id(container))
        if key in seen_containers:
            continue
        amount = _as_float(container.get("canonical_quantity", container.get("quantity", 0)))
        if amount <= 0:
            continue
        item = product_index.get(str(container.get("product_id") or ""))
        rows.append(_stock_row_from_container(container, item))
    return [row for row in rows if row]


def _stock_row_from_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": item.get("source") or "stock",
        "product_id": item.get("product_id") or "",
        "item_id": item.get("item_id") or "",
        "label": item.get("label") or "Stock",
        "quantity": item.get("quantity"),
        "unit": item.get("unit"),
        "quantities": item.get("quantities") or {},
        "best_before_date": _best_before_value(item),
        "opened_date": item.get("opened_date") or "",
    }


def _stock_row_from_container(container: dict[str, Any], item: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "source": "mise_container",
        "product_id": container.get("product_id") or (item or {}).get("product_id") or "",
        "item_id": (item or {}).get("item_id") or container.get("item_id") or "",
        "label": (item or {}).get("label") or container.get("item_label") or container.get("name") or "Container stock",
        "quantity": container.get("canonical_quantity", container.get("quantity", 0)),
        "unit": container.get("canonical_unit", container.get("unit")) or DEFAULT_UNIT,
        "quantities": {
            container.get("canonical_unit", container.get("unit")) or DEFAULT_UNIT: container.get(
                "canonical_quantity", container.get("quantity", 0)
            )
        },
        "best_before_date": _best_before_value(container),
        "opened_date": container.get("opened_date") or "",
    }


def _best_before_value(row: dict[str, Any]) -> Any:
    for key in ("best_before_date", "next_best_before_date", "due_date", "next_due_date"):
        if row.get(key):
            return row.get(key)
    return ""


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0
