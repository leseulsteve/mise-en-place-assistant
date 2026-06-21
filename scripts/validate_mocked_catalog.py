#!/usr/bin/env python3
"""Validate the offline mocked catalog used by tests and demo setup."""

from __future__ import annotations

import importlib.util
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOCKED_PATH = ROOT / "custom_components/mise_en_place_assistant/mocked.py"

PRIVATE_PATTERN = re.compile(
    r"(@|https?://|192\.168\.|10\.\d+\.|172\.(?:1[6-9]|2\d|3[01])\.|"
    r"password|token|api[_-]?key|authorization|bearer)",
    re.IGNORECASE,
)
SUPPORTED_TEST_UNITS = {"each", "g", "kg", "ml", "portions"}
REQUIRED_FOOD_FIELDS = {"id", "label", "format", "unit"}
REQUIRED_LOCATION_FIELDS = {"id", "name", "provider", "active"}
REQUIRED_RECIPE_FIELDS = {"id", "label", "format", "unit", "tags", "categories"}


def _load_mocked_module():
    spec = importlib.util.spec_from_file_location("mocked_catalog_for_validation", MOCKED_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load {MOCKED_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _unique_ids(records: list[dict], label: str) -> set[str]:
    ids = [record.get("id") for record in records]
    _require(all(isinstance(record_id, str) and record_id for record_id in ids), f"{label} ids must be non-empty strings")
    _require(len(ids) == len(set(ids)), f"{label} ids must be unique")
    return set(ids)


def _no_private_text(records: list[dict], label: str) -> None:
    for record in records:
        text = " ".join(str(value) for value in record.values())
        _require(not PRIVATE_PATTERN.search(text), f"{label} contains private-looking text: {record.get('id')}")


def validate_mocked_catalog() -> None:
    """Raise AssertionError if the mocked provider is not release-safe."""
    mocked = _load_mocked_module()
    foods = list(mocked.MOCKED_FOODS)
    stock = list(mocked.MOCKED_STOCK)
    locations = list(mocked.MOCKED_STORAGE_LOCATIONS)
    recipes = list(mocked.MOCKED_RECIPES)

    _require(len(foods) >= 40, "mocked catalog should stay broad enough for panel and Dial tests")
    _require(len(stock) >= 10, "mocked stock should cover empty, low, normal, and attention states")
    _require(len(locations) >= 3, "mocked locations should cover fridge, freezer, and pantry flows")
    _require(len(recipes) >= 200, "mocked recipes should cover a broad Mealie-style recipe catalog")

    food_ids = _unique_ids(foods, "mocked food")
    recipe_ids = _unique_ids(recipes, "mocked recipe")
    location_ids = _unique_ids(locations, "mocked location")
    stock_ids = _unique_ids(stock, "mocked stock")

    _require(stock_ids <= food_ids, "mocked stock must reference real mocked foods")
    _require(all(record["id"].startswith("mocked:") for record in foods), "mocked food ids must use the mocked: prefix")
    _require(all(record["id"].startswith("mocked:recipe:") for record in recipes), "mocked recipe ids must use the mocked:recipe: prefix")
    _require(all(record["id"].startswith("mocked:") for record in locations), "mocked location ids must use the mocked: prefix")
    _require(not (food_ids & recipe_ids), "mocked foods and recipes must not share ids")
    _require({"mocked:fridge", "mocked:freezer", "mocked:pantry"} <= location_ids, "core mocked locations are required")

    for food in foods:
        _require(REQUIRED_FOOD_FIELDS <= food.keys(), f"mocked food is missing fields: {food}")
        _require(food["unit"] in SUPPORTED_TEST_UNITS, f"mocked food uses unsupported test unit: {food}")
        _require(food["label"].strip() == food["label"], f"mocked food label has unstable whitespace: {food}")

    for stock_item in stock:
        quantity = stock_item.get("quantity")
        _require(isinstance(quantity, (int, float)) and math.isfinite(quantity) and quantity >= 0, f"mocked stock quantity must be finite and non-negative: {stock_item}")

    for location in locations:
        _require(REQUIRED_LOCATION_FIELDS <= location.keys(), f"mocked location is missing fields: {location}")
        _require(location["provider"] == "mocked", f"mocked location must keep provider attribution: {location}")
        _require(isinstance(location["active"], bool), f"mocked location active flag must be boolean: {location}")

    recipe_tags = set()
    component_counts = {"protein": 0, "vegetable": 0, "starch": 0}
    families_by_component: dict[str, set[str]] = {component: set() for component in component_counts}
    details_by_component: dict[str, set[str]] = {component: set() for component in component_counts}
    for recipe in recipes:
        _require(REQUIRED_RECIPE_FIELDS <= recipe.keys(), f"mocked recipe is missing fields: {recipe}")
        _require(recipe["unit"] == "portions", f"mocked recipes should remain portion-counted: {recipe}")
        _require(isinstance(recipe["tags"], list) and recipe["tags"], f"mocked recipe needs workflow tags: {recipe}")
        recipe_tags.update(recipe["tags"])
        component = next((tag.removeprefix("mpa:component:") for tag in recipe["tags"] if tag.startswith("mpa:component:")), None)
        if component in component_counts:
            component_counts[component] += 1
            for tag in recipe["tags"]:
                if tag.startswith(("mpa:primary-protein:", "mpa:component-family:")):
                    families_by_component[component].add(tag.rsplit(":", 1)[1])
                if tag.startswith(("mpa:protein-detail:", "mpa:component-detail:")):
                    details_by_component[component].add(tag.rsplit(":", 1)[1])

    _require(any(tag.startswith("mpa:component:") for tag in recipe_tags), "mocked recipes need component tags")
    _require(any(tag.startswith("mpa:primary-protein:") for tag in recipe_tags), "mocked recipes need primary protein tags")
    _require(component_counts["protein"] >= 20, "mocked recipes need enough protein components for TV dinner dice")
    _require(component_counts["vegetable"] >= 20, "mocked recipes need enough vegetable components for TV dinner dice")
    _require(component_counts["starch"] >= 20, "mocked recipes need enough starch components for TV dinner dice")
    for component, families in families_by_component.items():
        _require(len(families) >= 4, f"mocked {component} recipes need enough families for TV dinner variety")
    for component, details in details_by_component.items():
        _require(len(details) >= 5, f"mocked {component} recipes need enough details for TV dinner variety")
    _no_private_text(foods + stock + locations + recipes, "mocked catalog")


def main() -> int:
    try:
        validate_mocked_catalog()
    except AssertionError as err:
        print(f"Mocked catalog validation failed: {err}", file=sys.stderr)
        return 1
    print("mocked catalog ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
