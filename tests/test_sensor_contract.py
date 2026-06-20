"""Regression checks for the Home Assistant entity boundary."""

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SENSOR_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/sensor.py").read_text()
TRANSLATIONS_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/translations/en.json").read_text()


class TestSensorContract(unittest.TestCase):
    """Keep provider-owned inventory quantities out of MPA's HA sensors."""

    def test_only_mpa_workflow_state_is_exposed_as_sensors(self) -> None:
        self.assertIn("MiseEnPlaceAssistantContainerStatusSensor", SENSOR_SOURCE)
        self.assertIn("MiseEnPlaceAssistantLocationSensor", SENSOR_SOURCE)
        self.assertIn("MiseEnPlaceAssistantStorageAttentionSensor", SENSOR_SOURCE)
        self.assertIn("storage_attention_summary", SENSOR_SOURCE)
        self.assertIn("containers_needing_location_count", SENSOR_SOURCE)
        self.assertIn("unhealthy_locations_count", SENSOR_SOURCE)
        self.assertIn("critical_locations_count", SENSOR_SOURCE)
        self.assertIn("warning_locations_count", SENSOR_SOURCE)
        self.assertIn("prepared_inventory_at_risk_count", SENSOR_SOURCE)
        self.assertIn('"status_label": summary["status_label"]', SENSOR_SOURCE)
        self.assertIn('"critical_locations": summary["critical_locations"]', SENSOR_SOURCE)
        self.assertIn('"warning_locations": summary["warning_locations"]', SENSOR_SOURCE)
        self.assertIn('"storage_attention"', TRANSLATIONS_SOURCE)
        self.assertIn('if kind == "container"', SENSOR_SOURCE)
        self.assertIn('elif kind == "location"', SENSOR_SOURCE)
        self.assertNotIn("MiseEnPlaceAssistantItemTotalSensor", SENSOR_SOURCE)
        self.assertNotIn("BinarySensorEntity", SENSOR_SOURCE)
        self.assertNotIn("MiseEnPlaceAssistantStorageUnsafeBinarySensor", SENSOR_SOURCE)
        self.assertNotIn("item_total", SENSOR_SOURCE)
        self.assertNotIn("product_entity", SENSOR_SOURCE)
        self.assertNotIn('elif kind == "product"', SENSOR_SOURCE)
        self.assertNotIn("_product_", SENSOR_SOURCE)
        self.assertNotIn("item_total", TRANSLATIONS_SOURCE)


if __name__ == "__main__":
    unittest.main()
