"""Focused tests for backend planning and freshness helpers."""

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).parents[1]
PACKAGE = "custom_components.mise_en_place_assistant"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if "custom_components" not in sys.modules:
    sys.modules["custom_components"] = types.ModuleType("custom_components")
if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components/mise_en_place_assistant")]
    sys.modules[PACKAGE] = package

_load_module(f"{PACKAGE}.const", ROOT / "custom_components/mise_en_place_assistant/const.py")
planning = _load_module(f"{PACKAGE}.planning", ROOT / "custom_components/mise_en_place_assistant/planning.py")


class TestPlanningHelpers(unittest.TestCase):
    """Keep recipe ranking and freshness policy centralized."""

    def tearDown(self) -> None:
        planning.set_shelf_life_policy(None)

    def test_freshness_status_parses_dates_once(self) -> None:
        self.assertEqual(planning.freshness_status("2026-01-01", today=date(2026, 1, 2))["status"], "stale")
        self.assertEqual(planning.freshness_status("2026-01-03", today=date(2026, 1, 2))["status"], "due")
        self.assertEqual(planning.freshness_status("not-a-date")["status"], "")

    def test_freezer_due_date_uses_item_nature(self) -> None:
        frozen_on = date(2026, 1, 1)

        self.assertEqual(
            planning.freezer_due_date(meal_component_family="fish", frozen_on=frozen_on),
            "2026-03-02",
        )
        self.assertEqual(
            planning.freezer_due_date(meal_component_role="starch", frozen_on=frozen_on),
            "2026-04-01",
        )
        self.assertEqual(
            planning.freezer_due_date(content_kind="ingredient", frozen_on=frozen_on),
            "2026-06-30",
        )

    def test_storage_due_date_uses_location_type_and_item_nature(self) -> None:
        stored_on = date(2026, 1, 1)

        self.assertEqual(
            planning.storage_due_date(location_type="fridge", meal_component_family="fish", stored_on=stored_on),
            "2026-01-03",
        )
        self.assertEqual(
            planning.storage_due_date(location_type="counter", meal_component_role="protein", stored_on=stored_on),
            "2026-01-02",
        )
        self.assertEqual(
            planning.storage_due_date(location_type="pantry", meal_component_family="rice", stored_on=stored_on),
            "2027-01-01",
        )
        self.assertIsNone(planning.storage_due_date(location_type="other", content_kind="ingredient", stored_on=stored_on))

    def test_storage_due_date_delegates_to_shelf_life_policy(self) -> None:
        class OneDayPolicy:
            def storage_due_days(self, **_: object) -> int:
                return 1

        planning.set_shelf_life_policy(OneDayPolicy())

        self.assertEqual(
            planning.storage_due_date(location_type="fridge", meal_component_family="fish", stored_on=date(2026, 1, 1)),
            "2026-01-02",
        )

    def test_recipe_suggestions_pick_earliest_matching_stock_lot(self) -> None:
        recipes = [
            {
                "id": "recipe-1",
                "label": "Tomato pasta",
                "ingredients": [{"label": "Tomatoes", "grocy_product_id": "42", "quantity": 1, "unit": "can"}],
            }
        ]
        item_totals = [
            {
                "product_id": "product-tomatoes",
                "item_id": "42",
                "label": "Tomatoes",
                "quantity": 2,
                "unit": "can",
                "quantities": {"can": 2},
                "source": "grocy",
            }
        ]
        containers = [
            {
                "tag_id": "newer",
                "product_id": "product-tomatoes",
                "item_label": "Tomatoes",
                "canonical_quantity": 1,
                "canonical_unit": "can",
                "best_before_date": "2026-02-01",
            },
            {
                "tag_id": "sooner",
                "product_id": "product-tomatoes",
                "item_label": "Tomatoes",
                "canonical_quantity": 1,
                "canonical_unit": "can",
                "best_before_date": "2026-01-05",
            },
        ]

        suggestions = planning.recipe_suggestions_data(
            recipes=recipes,
            item_totals=item_totals,
            containers=containers,
        )

        self.assertEqual(suggestions[0]["matched"][0]["best_before_date"], "2026-01-05")


if __name__ == "__main__":
    unittest.main()
