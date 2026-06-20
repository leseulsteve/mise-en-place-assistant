"""Regression checks for the selectable food-catalog boundary."""

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
STORE_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/store.py").read_text()
INIT_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/__init__.py").read_text()
FLOW_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/config_flow.py").read_text()
MOCKED_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/mocked.py").read_text()
MEALIE_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/mealie.py").read_text()
GROCY_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/grocy.py").read_text()
KITCHENOWL_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/kitchenowl.py").read_text()
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
        self.assertIn('item.get("provider", manager.catalog_provider())', INIT_SOURCE)
        self.assertIn("def catalog_providers", STORE_SOURCE)
        self.assertIn("CONF_CATALOG_PROVIDERS", STORE_SOURCE)
        self.assertIn("def effective_catalog_providers", STORE_SOURCE)

    def test_config_flow_reuses_home_assistant_mealie_before_manual_setup(self) -> None:
        self.assertIn("CONF_CATALOG_PROVIDER", FLOW_SOURCE)
        self.assertIn("CONF_CATALOG_PROVIDERS", FLOW_SOURCE)
        self.assertIn("CONF_DEV_MODE", FLOW_SOURCE)
        self.assertIn("provider_required", FLOW_SOURCE)
        self.assertIn("async_step_mealie", FLOW_SOURCE)
        self.assertIn('async_entries(_MEALIE_DOMAIN)', FLOW_SOURCE)
        self.assertIn("async_step_mealie_manual", FLOW_SOURCE)
        self.assertIn("CONF_MEALIE_ENTRY_ID", FLOW_SOURCE)
        self.assertIn("async_get_entry(source_entry_id)", STORE_SOURCE)
        self.assertGreaterEqual(MOCKED_SOURCE.count('("'), 40)

    def test_grocy_can_supply_products_without_replacing_mealie(self) -> None:
        self.assertIn("PROVIDER_GROCY", CONST_SOURCE)
        self.assertIn("GrocyCatalogClient", STORE_SOURCE)
        self.assertIn("async_fetch_products", GROCY_SOURCE)
        self.assertIn("async_fetch_stock", GROCY_SOURCE)
        self.assertIn("async_fetch_locations", GROCY_SOURCE)
        self.assertIn("async_add_stock", GROCY_SOURCE)
        self.assertIn("async_consume_stock", GROCY_SOURCE)
        self.assertIn('"GROCY-API-KEY"', GROCY_SOURCE)
        self.assertIn('elif provider == PROVIDER_GROCY', STORE_SOURCE)
        self.assertIn('PROVIDER_MEALIE in providers', FLOW_SOURCE)
        self.assertIn('PROVIDER_GROCY in providers', FLOW_SOURCE)
        self.assertIn("PROVIDER_MOCKED", STORE_SOURCE)
        self.assertIn("mock_catalog_enabled", STORE_SOURCE)
        self.assertIn("MOCKED_STOCK", STORE_SOURCE)
        self.assertIn("MOCKED_STORAGE_LOCATIONS", STORE_SOURCE)
        self.assertIn('"mocked:dark-chocolate"', MOCKED_SOURCE)
        self.assertIn('"quantity": 750.5', MOCKED_SOURCE)
        self.assertIn('"mocked:bananas"', STORE_SOURCE)
        self.assertIn('"no_container"', STORE_SOURCE)

    def test_grocy_products_sync_to_mealie_from_review_metadata(self) -> None:
        self.assertNotIn("SERVICE_SYNC_GROCY_PRODUCTS_TO_MEALIE", CONST_SOURCE)
        self.assertNotIn("handle_sync_grocy_products_to_mealie", INIT_SOURCE)
        self.assertIn("async_update_product_metadata", STORE_SOURCE)
        self.assertIn("available_in_mealie", STORE_SOURCE)
        self.assertIn("async_sync_grocy_products", MEALIE_SOURCE)
        self.assertIn("_GROCY_PRODUCT_EXTRA_KEY", MEALIE_SOURCE)
        self.assertIn('"mise_en_place_grocy_product_id"', MEALIE_SOURCE)
        self.assertIn('await self._async_post("foods"', MEALIE_SOURCE)
        self.assertIn('await self._async_put(f"foods/{food_id}"', MEALIE_SOURCE)
        self.assertIn("name.casefold() in by_name", MEALIE_SOURCE)
        self.assertIn("Mealie food sync is unavailable", STORE_SOURCE)
        self.assertNotIn("sync_grocy_products_to_mealie", (ROOT / "custom_components/mise_en_place_assistant/services.yaml").read_text())

    def test_grocy_owns_live_inventory_quantities(self) -> None:
        self.assertIn("_async_apply_grocy_stock_replacement", STORE_SOURCE)
        self.assertIn("await client.async_add_stock", STORE_SOURCE)
        self.assertIn("await client.async_consume_stock", STORE_SOURCE)
        self.assertIn('self.data["stock"] = await client.async_fetch_stock()', STORE_SOURCE)
        self.assertIn('source.get("provider") != PROVIDER_GROCY', STORE_SOURCE)
        self.assertIn("Empty a Grocy-backed container before changing its product", STORE_SOURCE)
        self.assertIn("Empty a Grocy-backed container before moving it to another location", STORE_SOURCE)
        self.assertIn("location_id=after_location_id", STORE_SOURCE)
        self.assertIn("location_id=before_location_id", STORE_SOURCE)
        self.assertIn('"source": "grocy"', STORE_SOURCE)
        self.assertNotIn("create_missing=True", STORE_SOURCE)
        self.assertIn("await self.async_update_container(tag_id=tag_id, quantity=set_quantity, delta=delta)", STORE_SOURCE)

    def test_grocy_owns_storage_location_identity(self) -> None:
        self.assertIn('await grocy.async_fetch_locations()', STORE_SOURCE)
        self.assertIn('self.data["storage_locations"]', STORE_SOURCE)
        self.assertIn("def storage_locations", STORE_SOURCE)
        self.assertIn("Create storage locations in Grocy", STORE_SOURCE)
        self.assertIn("Location annotated", STORE_SOURCE)

    def test_live_mode_supports_grocy_shopping_while_retaining_kitchenowl(self) -> None:
        self.assertIn("KitchenOwlShoppingClient", STORE_SOURCE)
        self.assertIn("async_validate_workflow_providers", STORE_SOURCE)
        self.assertIn("set(providers) != set(CATALOG_PROVIDERS)", FLOW_SOURCE)
        self.assertIn("CONF_SHOPPING_LIST_PROVIDER", FLOW_SOURCE)
        self.assertIn("SHOPPING_LIST_PROVIDER_AUTO", STORE_SOURCE)
        self.assertIn("async_add_product_to_shopping_list", GROCY_SOURCE)
        self.assertIn("async_add_missing_products_to_shopping_list", GROCY_SOURCE)
        self.assertIn("CONF_KITCHENOWL_SHOPPING_LIST_ID", FLOW_SOURCE)
        self.assertIn("async_add_empty_containers_to_shopping_list", STORE_SOURCE)
        self.assertIn("async_add_missing_products_to_shopping_list", STORE_SOURCE)
        self.assertIn("DEV mode is read-only; use live providers to test CRUD", STORE_SOURCE)
        self.assertNotIn('"Shopping item mocked"', STORE_SOURCE)
        self.assertNotIn('"Empty containers mocked"', STORE_SOURCE)
        self.assertIn("add-item-by-name", KITCHENOWL_SOURCE)
        self.assertIn("HEAD", KITCHENOWL_SOURCE.upper())
        self.assertIn("SERVICE_ADD_TO_SHOPPING_LIST", INIT_SOURCE)
        self.assertIn("SERVICE_ADD_MISSING_PRODUCTS_TO_SHOPPING_LIST", INIT_SOURCE)
        self.assertNotIn("KitchenOwl must be configured outside DEV mode", STORE_SOURCE)

    def test_container_lifecycle_is_explicit_and_non_destructive(self) -> None:
        self.assertIn("SERVICE_CLEAR_CONTAINER", INIT_SOURCE)
        self.assertIn("SERVICE_ARCHIVE_CONTAINER", INIT_SOURCE)
        self.assertIn("SERVICE_RESTORE_CONTAINER", INIT_SOURCE)
        self.assertIn("async_clear_container", STORE_SOURCE)
        self.assertIn("async_archive_container", STORE_SOURCE)
        self.assertIn("async_restore_container", STORE_SOURCE)
        self.assertIn("Clear the container before archiving it", STORE_SOURCE)
        self.assertIn('"archived": False', STORE_SOURCE)
        self.assertNotIn("async_delete_container", STORE_SOURCE)

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
        frontend = (ROOT / "custom_components/mise_en_place_assistant/panel_frontend.js").read_text()
        self.assertIn("Ingredients use the product catalog", frontend)
        self.assertNotIn("Ingredients use a Mealie food", frontend)
        self.assertNotIn("CONTAINER_STATE_DIRTY", STORE_SOURCE)

    def test_storage_version_does_not_downgrade_existing_inventory(self) -> None:
        self.assertIn("STORAGE_VERSION = 5", CONST_SOURCE)


if __name__ == "__main__":
    unittest.main()
