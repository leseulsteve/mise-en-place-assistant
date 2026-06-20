"""Regression checks for the Home Assistant custom-panel integration boundary."""

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
PANEL_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/panel.py").read_text()
INIT_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/__init__.py").read_text()


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


if __name__ == "__main__":
    unittest.main()
