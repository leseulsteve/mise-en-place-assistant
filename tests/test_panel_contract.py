"""Regression checks for the Home Assistant custom-panel integration boundary."""

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
PANEL_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/panel.py").read_text()
INIT_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/__init__.py").read_text()
STORE_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/store.py").read_text()
FRONTEND_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/panel_frontend.js").read_text()
M5DIAL_SOURCE = (ROOT / "m5dial/m5dial-mise-en-place-assistant.yaml").read_text()


class TestPanelContract(unittest.TestCase):
    """Keep the sidebar panel on Home Assistant's public custom-panel API."""

    def test_registers_a_local_custom_panel(self) -> None:
        self.assertIn("from homeassistant.components import frontend, panel_custom, websocket_api", PANEL_SOURCE)
        self.assertIn("await panel_custom.async_register_panel(", PANEL_SOURCE)
        self.assertIn("webcomponent_name=PANEL_COMPONENT_NAME", PANEL_SOURCE)
        self.assertIn("module_url=PANEL_MODULE_URL", PANEL_SOURCE)
        self.assertIn("embed_iframe=False", PANEL_SOURCE)
        self.assertIn("trust_external=False", PANEL_SOURCE)
        self.assertIn("Received sidebar overview WebSocket request", PANEL_SOURCE)
        self.assertIn("Could not build sidebar overview response", PANEL_SOURCE)
        self.assertNotIn('"_panel_custom"', PANEL_SOURCE)

    def test_waits_for_panel_registration(self) -> None:
        self.assertIn("await async_register_panel(hass)", INIT_SOURCE)

    def test_mocked_catalog_seeds_bounded_sample_data_on_first_setup(self) -> None:
        self.assertIn("manager.effective_catalog_providers() == [PROVIDER_MOCKED] and not manager.containers", INIT_SOURCE)
        self.assertIn("await manager.async_seed_demo_data()", INIT_SOURCE)
        self.assertIn("async_seed_demo_data", STORE_SOURCE)
        self.assertIn("Demo tag IDs are deliberately stable", STORE_SOURCE)

    def test_locations_are_managed_by_stable_id(self) -> None:
        self.assertIn('VOID_LOCATION_ID = "__void__"', (ROOT / "custom_components/mise_en_place_assistant/const.py").read_text())
        self.assertIn("SERVICE_CREATE_LOCATION", INIT_SOURCE)
        self.assertIn("SERVICE_UPDATE_LOCATION", INIT_SOURCE)
        self.assertIn("SERVICE_DELETE_LOCATION", INIT_SOURCE)
        self.assertIn("SERVICE_MOVE_CONTAINER", INIT_SOURCE)
        self.assertIn("incoming_location_ids", M5DIAL_SOURCE)
        self.assertIn("location_id: !lambda 'return id(selected_location_id);'", M5DIAL_SOURCE)
        self.assertNotIn("incoming_locations", M5DIAL_SOURCE)
        self.assertIn('"location_id": container.get("location_id")', PANEL_SOURCE)
        self.assertIn("storage_locations", STORE_SOURCE)
        self.assertIn("Create storage locations in Grocy", STORE_SOURCE)
        self.assertIn("VOID_LOCATION_NAME", STORE_SOURCE)

    def test_panel_has_location_management_tab(self) -> None:
        self.assertIn("Manage locations & containers", FRONTEND_SOURCE)
        self.assertIn("Storage locations", FRONTEND_SOURCE)
        self.assertIn('"update_location"', FRONTEND_SOURCE)
        self.assertNotIn('"create_location"', FRONTEND_SOURCE)
        self.assertIn('this._hass.callService("mise_en_place_assistant", "delete_location"', FRONTEND_SOURCE)
        self.assertIn('this._hass.callService("mise_en_place_assistant", "move_container"', FRONTEND_SOURCE)
        self.assertIn("_locationCard(location)", FRONTEND_SOURCE)

    def test_panel_has_dev_tab_for_live_testing(self) -> None:
        self.assertIn('id="tab-dev"', FRONTEND_SOURCE)
        self.assertIn("_devView(data)", FRONTEND_SOURCE)
        self.assertIn("Dev controls", FRONTEND_SOURCE)
        self.assertIn("Copy overview JSON", FRONTEND_SOURCE)
        self.assertIn("_loadIfNoEventSocket", FRONTEND_SOURCE)
        self.assertIn("Queue Grocy minimum stock", FRONTEND_SOURCE)

    def test_panel_surfaces_shopping_workflow_status(self) -> None:
        self.assertIn('"shopping": manager.shopping_workflow_status()', PANEL_SOURCE)
        self.assertIn("Shopping workflow", FRONTEND_SOURCE)
        self.assertIn("add_missing_products_to_shopping_list", FRONTEND_SOURCE)
        self.assertNotIn("sync_grocy_products_to_mealie", FRONTEND_SOURCE)
        self.assertNotIn("grocy_mealie_food_sync", STORE_SOURCE)

    def test_panel_surfaces_product_attention_metadata(self) -> None:
        self.assertIn('"product_attention": manager.product_attention_items()', PANEL_SOURCE)
        self.assertIn("product_metadata", STORE_SOURCE)
        self.assertIn("product_attention_items", STORE_SOURCE)
        self.assertIn("PROVIDER_MOCKED", STORE_SOURCE)
        self.assertIn("async_update_product_metadata", STORE_SOURCE)
        self.assertIn("SERVICE_UPDATE_PRODUCT_METADATA", INIT_SOURCE)
        self.assertIn("update_product_metadata", FRONTEND_SOURCE)
        self.assertIn("Container policy", FRONTEND_SOURCE)
        self.assertIn("Storage behavior", FRONTEND_SOURCE)
        self.assertIn("available_in_mealie", STORE_SOURCE)
        self.assertIn("Available in Mealie", FRONTEND_SOURCE)
        self.assertIn("meal_role", STORE_SOURCE)


if __name__ == "__main__":
    unittest.main()
