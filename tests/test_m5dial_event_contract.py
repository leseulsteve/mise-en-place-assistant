"""Focused contract checks for M5Dial events and service failure paths."""

from pathlib import Path
import re
from typing import Optional
import unittest


ROOT = Path(__file__).parents[1]
INIT_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/__init__.py").read_text()
STORE_SOURCE = (ROOT / "custom_components/mise_en_place_assistant/store.py").read_text()
M5DIAL_SOURCE = (ROOT / "m5dial/m5dial-mise-en-place-assistant.yaml").read_text()


def _body_after(source: str, marker: str, *, until: Optional[str] = None) -> str:
    """Return source after a marker, optionally bounded by a later marker."""
    start = source.index(marker)
    body = source[start:]
    if until:
        end = body.index(until)
        return body[:end]
    return body


class TestM5DialEventContract(unittest.TestCase):
    """Keep Home Assistant and ESPHome aligned on unsafe event paths."""

    def test_dial_event_quantities_are_finite_non_negative_before_mutation(self) -> None:
        create_body = _body_after(INIT_SOURCE, "def handle_create_from_dial", until="def handle_update_from_dial")
        update_body = _body_after(INIT_SOURCE, "def handle_update_from_dial", until="async def _async_confirm_inventory")
        for body in (create_body, update_body):
            self.assertIn("quantity = float(quantity)", body)
            self.assertIn("not math.isfinite(quantity) or quantity < 0", body)
            self.assertIn('title="Bad quantity"', body)
            self.assertIn('message="Quantity must be finite and non-negative"', body)
        self.assertLess(create_body.index("not math.isfinite(quantity) or quantity < 0"), create_body.index("async_create_container"))
        self.assertLess(update_body.index("not math.isfinite(quantity) or quantity < 0"), update_body.index("async_update_container"))

    def test_malformed_create_selection_fails_without_creating_inventory(self) -> None:
        create_body = _body_after(INIT_SOURCE, "def handle_create_from_dial", until="def handle_update_from_dial")
        self.assertIn('content_kind not in {"ingredient", "recipe", "meal"}', create_body)
        self.assertIn('title="Bad selection"', create_body)
        self.assertIn('message="Content kind unavailable"', create_body)
        self.assertLess(create_body.index('content_kind not in {"ingredient", "recipe", "meal"}'), create_body.index("async_create_container"))
        self.assertIn("except (MealieCatalogError, ValueError) as err", create_body)
        self.assertIn("except Exception", create_body)

    def test_scan_and_update_handlers_ignore_malformed_or_wrong_source_events(self) -> None:
        for marker in (
            "def handle_mise_en_place_assistant_scan",
            "def handle_create_from_dial",
            "def handle_update_from_dial",
            "def handle_inventory_confirm",
        ):
            body = _body_after(INIT_SOURCE, marker)
            self.assertIn("if not is_enrolled_dial_event(event):", body)
            self.assertIn("if not tag_id:", body)
        self.assertIn('return int(event.data.get(ATTR_REQUEST_ID, 0) or 0)', INIT_SOURCE)
        self.assertIn("except (TypeError, ValueError)", INIT_SOURCE)

    def test_esphome_rejects_stale_home_assistant_responses_before_showing_or_saving(self) -> None:
        self.assertIn("id(ha_response_accepted) = id(current_view) == 1 && id(last_tag_id) == tag_id && id(active_request_id) == request_id", M5DIAL_SOURCE)
        self.assertIn("Ignoring stale create response", M5DIAL_SOURCE)
        self.assertIn("Ignoring stale known-container response", M5DIAL_SOURCE)
        self.assertIn("Ignoring stale operation result", M5DIAL_SOURCE)
        self.assertIn("id(active_request_id) = 0;", M5DIAL_SOURCE)
        self.assertIn("source: \"${device_name}\"", M5DIAL_SOURCE)
        self.assertRegex(M5DIAL_SOURCE, re.compile(r"event: esphome\.mise_en_place_assistant_create_container.*?request_id:", re.S))
        self.assertRegex(M5DIAL_SOURCE, re.compile(r"event: esphome\.mise_en_place_assistant_update_container.*?request_id:", re.S))

    def test_home_assistant_consumes_active_dial_request_before_inventory_mutation(self) -> None:
        create_body = _body_after(INIT_SOURCE, "def handle_create_from_dial", until="def handle_update_from_dial")
        update_body = _body_after(INIT_SOURCE, "def handle_update_from_dial", until="async def _async_confirm_inventory")
        self.assertIn("active_dial_requests: dict[str, int] = {}", INIT_SOURCE)
        self.assertIn("hass.loop.call_later", INIT_SOURCE)
        self.assertIn("def _consume_dial_request", INIT_SOURCE)
        for body, mutation in (
            (create_body, "async_create_container"),
            (update_body, "async_update_container"),
        ):
            self.assertIn("if not _consume_dial_request(tag_id, request_id):", body)
            self.assertIn('title="Scan expired"', body)
            self.assertLess(body.index("if not _consume_dial_request(tag_id, request_id):"), body.index(mutation))

    def test_dial_and_integration_reject_missing_or_protected_location_before_save(self) -> None:
        create_body = _body_after(INIT_SOURCE, "def handle_create_from_dial", until="def handle_update_from_dial")
        update_body = _body_after(INIT_SOURCE, "def handle_update_from_dial", until="async def _async_confirm_inventory")
        self.assertIn("def _dial_location_id", INIT_SOURCE)
        self.assertIn("location_id == VOID_LOCATION_ID", INIT_SOURCE)
        for body, mutation in (
            (create_body, "async_create_container"),
            (update_body, "async_update_container"),
        ):
            self.assertIn("location_id = _dial_location_id(event)", body)
            self.assertIn('title="Bad location"', body)
            self.assertLess(body.index("location_id = _dial_location_id(event)"), body.index(mutation))
        self.assertIn("id(press_view) == 13 && !id(last_tag_id).empty() && !id(selected_item_id).empty() && !id(selected_location_id).empty()", M5DIAL_SOURCE)
        self.assertIn("id(press_view) == 21 && !id(last_tag_id).empty() && !id(selected_location_id).empty()", M5DIAL_SOURCE)
        self.assertIn("Cannot update container with incomplete selection", M5DIAL_SOURCE)

    def test_service_schemas_match_mutating_store_method_inputs(self) -> None:
        for service_name, required in {
            "SERVICE_CREATE_CONTAINER": ("ATTR_TAG_ID", "ATTR_ITEM_ID"),
            "SERVICE_CREATE_RECIPE_CONTAINER": ("ATTR_TAG_ID", "ATTR_RECIPE_ID", "ATTR_CONTENT_KIND"),
            "SERVICE_UPDATE_CONTAINER": ("ATTR_TAG_ID",),
            "SERVICE_FILL_CONTAINER": ("ATTR_TAG_ID", "ATTR_QUANTITY"),
            "SERVICE_REMOVE_ITEMS": ("ATTR_TAG_ID", "ATTR_QUANTITY"),
            "SERVICE_MOVE_CONTAINER": ("ATTR_TAG_ID", "ATTR_LOCATION_ID"),
            "SERVICE_UPDATE_PRODUCT_METADATA": ("ATTR_ITEM_ID", "ATTR_CONTAINER_POLICY", "ATTR_STORAGE_BEHAVIOR", "ATTR_MEAL_ROLE"),
        }.items():
            block = _body_after(INIT_SOURCE, service_name)
            self.assertIn("schema=vol.Schema", block)
            for attr in required:
                self.assertIn(f"vol.Required({attr})", block)
        self.assertIn("vol.Optional(ATTR_QUANTITY, default=0): _nonnegative_number", INIT_SOURCE)
        self.assertIn("vol.Required(ATTR_QUANTITY): _positive_number", INIT_SOURCE)
        self.assertIn("vol.Optional(ATTR_DELTA): _finite_number", INIT_SOURCE)

    def test_provider_failures_are_logged_with_auditable_details(self) -> None:
        update_body = _body_after(STORE_SOURCE, "async def _async_update_container", until="async def async_scan_container")
        self.assertLess(update_body.index("await self._async_apply_grocy_stock_replacement"), update_body.index("self.containers[tag_id] = candidate"))
        self.assertIn("Grocy stock write failed", STORE_SOURCE)
        self.assertIn('raise ValueError("Grocy rejected the stock decrease") from err', STORE_SOURCE)
        self.assertIn('raise ValueError("Grocy rejected the stock increase") from err', STORE_SOURCE)
        self.assertIn('"provider": PROVIDER_GROCY', STORE_SOURCE)
        self.assertIn('"operations": stock_events', STORE_SOURCE)
        self.assertIn('"provider": provider', STORE_SOURCE)
        self.assertIn('"targets"', STORE_SOURCE)
        self.assertIn('"item_count": sent', STORE_SOURCE)
        self.assertIn('"reason": "empty_container_refill"', STORE_SOURCE)
        self.assertIn('"reason": "grocy_minimum_stock"', STORE_SOURCE)
        self.assertIn('"reason": "explicit_shopping_request"', STORE_SOURCE)


if __name__ == "__main__":
    unittest.main()
