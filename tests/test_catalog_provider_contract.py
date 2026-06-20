"""Regression checks for the selectable food-catalog boundary."""

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
STORE_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/store.py").read_text()
INIT_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/__init__.py").read_text()
FLOW_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/config_flow.py").read_text()
MOCKED_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/mocked.py").read_text()
MEALIE_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/mealie.py").read_text()
UNITS_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/units.py").read_text()
CONST_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/const.py").read_text()


class TestCatalogProviderContract(unittest.TestCase):
    """Keep provider selection explicit and catalog data authoritative."""

    def test_startup_refreshes_the_selected_provider(self) -> None:
        self.assertIn("await manager.async_refresh_catalog()", INIT_SOURCE)
        self.assertIn("raise ConfigEntryNotReady", INIT_SOURCE)
        self.assertIn("async_track_time_interval", INIT_SOURCE)

    def test_new_container_foods_are_resolved_from_selected_provider(self) -> None:
        self.assertIn("await manager.async_catalog_item", INIT_SOURCE)
        self.assertIn("source_provider=manager.catalog_provider()", INIT_SOURCE)
        self.assertIn("if provider == PROVIDER_MOCKED", STORE_SOURCE)

    def test_config_flow_reuses_home_assistant_mealie_before_manual_setup(self) -> None:
        self.assertIn("CONF_CATALOG_PROVIDER", FLOW_SOURCE)
        self.assertIn("async_step_mealie", FLOW_SOURCE)
        self.assertIn('async_entries(_MEALIE_DOMAIN)', FLOW_SOURCE)
        self.assertIn("async_step_mealie_manual", FLOW_SOURCE)
        self.assertIn("CONF_MEALIE_ENTRY_ID", FLOW_SOURCE)
        self.assertIn("async_get_entry(source_entry_id)", STORE_SOURCE)
        self.assertGreaterEqual(MOCKED_SOURCE.count('("'), 40)

    def test_mealie_food_unit_defaults_are_explicit_and_pint_validated(self) -> None:
        self.assertIn('await self._async_get_all("units")', MEALIE_SOURCE)
        self.assertIn('"mise_en_place_unit_id", "mise_en_place_unit"', MEALIE_SOURCE)
        self.assertIn("normalized_inventory_unit", MEALIE_SOURCE)
        self.assertIn('return "items"', MEALIE_SOURCE)
        self.assertIn('if normalized["unit_dimension"] == "custom"', UNITS_SOURCE)

    def test_recipe_containers_use_mealie_tags_for_ready_meal_inventory(self) -> None:
        self.assertIn("async_fetch_recipes", MEALIE_SOURCE)
        self.assertIn('"mpa:component:"', STORE_SOURCE)
        self.assertIn('"mpa:primary-protein:"', STORE_SOURCE)
        self.assertIn("async_create_recipe_container", STORE_SOURCE)
        self.assertIn("def meal_inventory", STORE_SOURCE)
        self.assertIn('content_kind not in {"ingredient", "recipe", "meal"}', STORE_SOURCE)
        self.assertNotIn("CONTAINER_STATE_DIRTY", STORE_SOURCE)

    def test_storage_version_does_not_downgrade_existing_inventory(self) -> None:
        self.assertIn("STORAGE_VERSION = 5", CONST_SOURCE)


if __name__ == "__main__":
    unittest.main()
