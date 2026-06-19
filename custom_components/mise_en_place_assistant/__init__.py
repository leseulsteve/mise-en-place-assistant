"""The Mise en Place Assistant integration."""

from __future__ import annotations

import logging
import math

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_M5DIAL_SERVICE_PREFIX,
    CONF_M5DIAL_EVENT_SOURCE,
    DEFAULT_UNIT,
    DEFAULT_M5DIAL_SERVICE_PREFIX,
    DOMAIN,
    EVENT_MISE_EN_PLACE_ASSISTANT_CREATE_CONTAINER,
    EVENT_MISE_EN_PLACE_ASSISTANT_MARK_CLEAN,
    EVENT_MISE_EN_PLACE_ASSISTANT_SCAN,
    EVENT_MISE_EN_PLACE_ASSISTANT_UPDATE_CONTAINER,
    EVENT_INVENTORY_CONFIRM,
    MOCK_ITEMS,
    PLATFORMS,
    SERVICE_CREATE_CONTAINER,
    SERVICE_CREATE_LOCATION,
    SERVICE_FILL_CONTAINER,
    SERVICE_MOCK_API,
    SERVICE_MARK_CONTAINER_CLEAN,
    SERVICE_REMOVE_ITEMS,
    SERVICE_SCAN_CONTAINER,
    SERVICE_UPDATE_CONTAINER,
)
from .panel import async_register_panel, async_unregister_panel
from .store import MiseEnPlaceAssistantInventory

_LOGGER = logging.getLogger(__name__)

ATTR_DELTA = "delta"
ATTR_LOCATION = "location"
ATTR_MODE = "mode"
ATTR_NAME = "name"
ATTR_QUANTITY = "quantity"
ATTR_STATE = "state"
ATTR_TAG_ID = "tag_id"
ATTR_UNIT = "unit"
ATTR_ITEM_FORMAT = "item_format"
ATTR_ITEM_ID = "item_id"
ATTR_ITEM_LABEL = "item_label"

SCAN_MODES = ["set", "add", "remove"]


def _nonnegative_number(value) -> int | float:
    """Validate a finite, non-negative inventory quantity."""
    try:
        value = float(value)
    except (TypeError, ValueError) as err:
        raise vol.Invalid("value must be a number") from err
    if not math.isfinite(value) or value < 0:
        raise vol.Invalid("value must be a finite non-negative number")
    return int(value) if value.is_integer() else value


def _finite_number(value) -> int | float:
    """Validate a finite number that may be a signed adjustment."""
    try:
        value = float(value)
    except (TypeError, ValueError) as err:
        raise vol.Invalid("value must be a number") from err
    if not math.isfinite(value):
        raise vol.Invalid("value must be finite")
    return int(value) if value.is_integer() else value


def _positive_number(value) -> int | float:
    """Validate a finite quantity greater than zero."""
    value = _nonnegative_number(value)
    if value <= 0:
        raise vol.Invalid("value must be greater than zero")
    return value


def _manager(hass: HomeAssistant) -> MiseEnPlaceAssistantInventory:
    """Return the loaded Mise en Place Assistant inventory manager."""
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data:
        raise ServiceValidationError("Mise en Place Assistant is not loaded")
    return next(iter(domain_data.values()))


def _mock_item(item_id: str | None) -> dict | None:
    """Return a mock API item by ID."""
    if not item_id:
        return None
    for item in MOCK_ITEMS:
        if item["id"] == item_id:
            return item
    return None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Mise en Place Assistant services."""

    async def handle_create_location(call: ServiceCall) -> None:
        manager = _manager(hass)
        _LOGGER.info("Creating Mise en Place Assistant location: %s", call.data[ATTR_NAME])
        await manager.async_create_location(call.data[ATTR_NAME])

    async def handle_create_container(call: ServiceCall) -> None:
        manager = _manager(hass)
        item = _mock_item(call.data.get(ATTR_ITEM_ID))
        _LOGGER.info(
            "Creating Mise en Place Assistant container from service: tag_id=%s item_id=%s quantity=%s location=%s",
            call.data[ATTR_TAG_ID],
            call.data.get(ATTR_ITEM_ID),
            call.data.get(ATTR_QUANTITY, 0),
            call.data.get(ATTR_LOCATION),
        )
        try:
            await manager.async_create_container(
                tag_id=call.data[ATTR_TAG_ID],
                name=call.data.get(ATTR_NAME),
                quantity=call.data.get(ATTR_QUANTITY, 0),
                location=call.data.get(ATTR_LOCATION),
                state=call.data.get(ATTR_STATE),
                unit=call.data.get(ATTR_UNIT) or (item or {}).get("unit", DEFAULT_UNIT),
                item_id=call.data.get(ATTR_ITEM_ID),
                item_label=call.data.get(ATTR_ITEM_LABEL) or (item or {}).get("label"),
                item_format=call.data.get(ATTR_ITEM_FORMAT) or (item or {}).get("format"),
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_update_container(call: ServiceCall) -> None:
        manager = _manager(hass)
        _LOGGER.info(
            "Updating Mise en Place Assistant container from service: tag_id=%s quantity=%s delta=%s location=%s state=%s",
            call.data[ATTR_TAG_ID],
            call.data.get(ATTR_QUANTITY),
            call.data.get(ATTR_DELTA),
            call.data.get(ATTR_LOCATION),
            call.data.get(ATTR_STATE),
        )
        try:
            await manager.async_update_container(
                tag_id=call.data[ATTR_TAG_ID],
                quantity=call.data.get(ATTR_QUANTITY),
                delta=call.data.get(ATTR_DELTA),
                location=call.data.get(ATTR_LOCATION),
                state=call.data.get(ATTR_STATE),
                name=call.data.get(ATTR_NAME),
                unit=call.data.get(ATTR_UNIT),
                item_id=call.data.get(ATTR_ITEM_ID),
                item_label=call.data.get(ATTR_ITEM_LABEL),
                item_format=call.data.get(ATTR_ITEM_FORMAT),
            )
        except (KeyError, ValueError) as err:
            raise ServiceValidationError(
                f"Unknown Mise en Place Assistant container tag_id: {err.args[0]}"
                if isinstance(err, KeyError) else str(err)
            ) from err

    async def handle_fill_container(call: ServiceCall) -> None:
        manager = _manager(hass)
        _LOGGER.info(
            "Filling Mise en Place Assistant container: tag_id=%s quantity=%s",
            call.data[ATTR_TAG_ID],
            call.data[ATTR_QUANTITY],
        )
        try:
            await manager.async_update_container(
                tag_id=call.data[ATTR_TAG_ID],
                delta=call.data[ATTR_QUANTITY],
            )
        except KeyError as err:
            raise ServiceValidationError(
                f"Unknown Mise en Place Assistant container tag_id: {err.args[0]}"
            ) from err

    async def handle_remove_items(call: ServiceCall) -> None:
        manager = _manager(hass)
        _LOGGER.info(
            "Removing Mise en Place Assistant items: tag_id=%s quantity=%s",
            call.data[ATTR_TAG_ID],
            call.data[ATTR_QUANTITY],
        )
        try:
            await manager.async_update_container(
                tag_id=call.data[ATTR_TAG_ID],
                delta=-call.data[ATTR_QUANTITY],
            )
        except KeyError as err:
            raise ServiceValidationError(
                f"Unknown Mise en Place Assistant container tag_id: {err.args[0]}"
            ) from err

    async def handle_scan_container(call: ServiceCall) -> None:
        manager = _manager(hass)
        _LOGGER.info(
            "Applying Mise en Place Assistant scan service: tag_id=%s quantity=%s mode=%s",
            call.data[ATTR_TAG_ID],
            call.data.get(ATTR_QUANTITY),
            call.data.get(ATTR_MODE, "set"),
        )
        await manager.async_scan_container(
            tag_id=call.data[ATTR_TAG_ID],
            quantity=call.data.get(ATTR_QUANTITY),
            mode=call.data.get(ATTR_MODE, "set"),
        )

    async def handle_mark_container_clean(call: ServiceCall) -> None:
        """Record a washed container without changing its stable NFC identity."""
        manager = _manager(hass)
        try:
            await manager.async_mark_container_clean(
                call.data[ATTR_TAG_ID], location=call.data.get(ATTR_LOCATION)
            )
        except KeyError as err:
            raise ServiceValidationError(
                f"Unknown Mise en Place Assistant container tag_id: {err.args[0]}"
            ) from err

    async def handle_mock_api(call: ServiceCall) -> None:
        manager = _manager(hass)
        _LOGGER.debug("Firing Mise en Place Assistant mock API response event")
        hass.bus.async_fire("mise_en_place_assistant.mock_api_response", manager.mock_api_payload())

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_LOCATION,
        handle_create_location,
        schema=vol.Schema({vol.Required(ATTR_NAME): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_CONTAINER,
        handle_create_container,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TAG_ID): cv.string,
                vol.Optional(ATTR_NAME): cv.string,
                vol.Optional(ATTR_QUANTITY, default=0): _nonnegative_number,
                vol.Optional(ATTR_LOCATION): cv.string,
                vol.Optional(ATTR_STATE): cv.string,
                vol.Optional(ATTR_UNIT, default=DEFAULT_UNIT): cv.string,
                vol.Optional(ATTR_ITEM_ID): cv.string,
                vol.Optional(ATTR_ITEM_LABEL): cv.string,
                vol.Optional(ATTR_ITEM_FORMAT): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_CONTAINER,
        handle_update_container,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TAG_ID): cv.string,
                vol.Optional(ATTR_NAME): cv.string,
                vol.Optional(ATTR_QUANTITY): _nonnegative_number,
                vol.Optional(ATTR_DELTA): _finite_number,
                vol.Optional(ATTR_LOCATION): cv.string,
                vol.Optional(ATTR_STATE): cv.string,
                vol.Optional(ATTR_UNIT): cv.string,
                vol.Optional(ATTR_ITEM_ID): cv.string,
                vol.Optional(ATTR_ITEM_LABEL): cv.string,
                vol.Optional(ATTR_ITEM_FORMAT): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FILL_CONTAINER,
        handle_fill_container,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TAG_ID): cv.string,
                vol.Required(ATTR_QUANTITY): _positive_number,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_ITEMS,
        handle_remove_items,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TAG_ID): cv.string,
                vol.Required(ATTR_QUANTITY): _positive_number,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN_CONTAINER,
        handle_scan_container,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TAG_ID): cv.string,
                vol.Optional(ATTR_QUANTITY): _nonnegative_number,
                vol.Optional(ATTR_MODE, default="set"): vol.In(SCAN_MODES),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_CONTAINER_CLEAN,
        handle_mark_container_clean,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TAG_ID): cv.string,
                vol.Optional(ATTR_LOCATION): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MOCK_API,
        handle_mock_api,
        schema=vol.Schema({}),
    )
    _LOGGER.debug("Registered Mise en Place Assistant services")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mise en Place Assistant from a config entry."""
    manager = MiseEnPlaceAssistantInventory(hass, entry)
    await manager.async_load()

    enrolled_source = entry.options.get(
        CONF_M5DIAL_EVENT_SOURCE,
        entry.data.get(CONF_M5DIAL_EVENT_SOURCE, ""),
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    async_register_panel(hass)
    _LOGGER.info(
        "Mise en Place Assistant entry loaded: entry_id=%s containers=%d locations=%d",
        entry.entry_id,
        len(manager.containers),
        len(manager.locations),
    )

    async def call_m5dial(action: str, data: dict) -> None:
        """Call a user-defined ESPHome action on the M5Dial."""
        service_prefix = entry.options.get(
            CONF_M5DIAL_SERVICE_PREFIX,
            entry.data.get(CONF_M5DIAL_SERVICE_PREFIX, DEFAULT_M5DIAL_SERVICE_PREFIX),
        )
        service = f"{service_prefix}_{action}"
        _LOGGER.debug(
            "Calling ESPHome action esphome.%s with keys=%s",
            service,
            sorted(data),
        )
        try:
            await hass.services.async_call(
                "esphome",
                service,
                data,
                blocking=True,
            )
            _LOGGER.info("Called ESPHome action esphome.%s successfully", service)
        except HomeAssistantError as err:
            _LOGGER.warning("Could not call ESPHome action esphome.%s: %s", service, err)

    async def show_create_flow(tag_id: str) -> None:
        """Tell the M5Dial to show the create-container flow."""
        payload = manager.mock_api_payload()
        _LOGGER.info(
            "Showing Mise en Place Assistant create flow on M5Dial: tag_id=%s items=%d locations=%d",
            tag_id,
            len(payload["items"]),
            len(payload["locations"]),
        )
        await call_m5dial(
            "show_create_container",
            {
                "tag_id": tag_id,
                "incoming_item_ids": [item["id"] for item in payload["items"]],
                "incoming_item_labels": [item["label"] for item in payload["items"]],
                "incoming_item_formats": [item["format"] for item in payload["items"]],
                "incoming_item_units": [item["unit"] for item in payload["items"]],
                "incoming_locations": payload["locations"],
            },
        )

    async def show_known_flow(tag_id: str, container: dict) -> None:
        """Tell the M5Dial to show the known-container flow."""
        payload = manager.mock_api_payload()
        _LOGGER.info(
            "Showing Mise en Place Assistant known flow on M5Dial: tag_id=%s quantity=%s location=%s",
            tag_id,
            container.get("quantity"),
            container.get("location"),
        )
        await call_m5dial(
            "show_known_container",
            {
                "tag_id": tag_id,
                "item_label": container.get("item_label")
                or container.get("name")
                or "Container",
                "item_format": container.get("item_format") or "",
                "quantity": float(container.get("quantity", 0)),
                "unit": container.get("unit") or DEFAULT_UNIT,
                "location": container.get("location") or "unknown",
                "state": container.get("state") or "unknown",
                "incoming_locations": payload["locations"],
            },
        )

    async def show_clean_flow(tag_id: str, container: dict) -> None:
        """Ask for confirmation when a dirty container is scanned after washing."""
        service_prefix = entry.options.get(
            CONF_M5DIAL_SERVICE_PREFIX,
            entry.data.get(CONF_M5DIAL_SERVICE_PREFIX, DEFAULT_M5DIAL_SERVICE_PREFIX),
        )

        if not hass.services.has_service("esphome", f"{service_prefix}_show_clean_container"):
            _LOGGER.warning(
                "M5Dial clean flow is not available yet; using the existing known-container flow"
            )
            await show_known_flow(tag_id, container)
            return
        payload = manager.mock_api_payload()
        await call_m5dial(
            "show_clean_container",
            {
                "tag_id": tag_id,
                "container_name": container.get("name") or manager.default_container_name(tag_id),
                "location": container.get("location") or "Container storage",
                "incoming_locations": payload["locations"],
            },
        )

    def is_enrolled_dial_event(event) -> bool:
        """Accept only events emitted by the configured M5Dial when known."""
        if not enrolled_source:
            return True
        source = event.data.get("source")
        if source == enrolled_source:
            return True
        _LOGGER.warning(
            "Ignoring Mise en Place Assistant event from unexpected ESPHome source: %s", source
        )
        return False

    @callback
    def handle_mise_en_place_assistant_scan(event) -> None:
        """Handle a raw NFC scan from the M5Dial."""
        if not is_enrolled_dial_event(event):
            return
        tag_id = event.data.get(ATTR_TAG_ID)
        if not tag_id:
            _LOGGER.debug("Ignoring Mise en Place Assistant scan event without tag_id")
            return
        container = manager.get_container(tag_id)
        if container and container.get("state") == "clean":
            _LOGGER.info("Clean Mise en Place Assistant NFC tag scanned for refill: tag_id=%s", tag_id)
            hass.async_create_task(show_create_flow(tag_id))
        elif container and container.get("state") == "dirty":
            _LOGGER.info("Dirty Mise en Place Assistant NFC tag scanned: tag_id=%s", tag_id)
            hass.async_create_task(show_clean_flow(tag_id, container))
        elif container:
            _LOGGER.info("Known Mise en Place Assistant NFC tag scanned: tag_id=%s", tag_id)
            hass.async_create_task(show_known_flow(tag_id, container))
        else:
            _LOGGER.info("Unknown Mise en Place Assistant NFC tag scanned: tag_id=%s", tag_id)
            hass.async_create_task(show_create_flow(tag_id))

    @callback
    def handle_create_from_dial(event) -> None:
        """Create a container from the M5Dial flow."""
        if not is_enrolled_dial_event(event):
            return
        tag_id = event.data.get(ATTR_TAG_ID)
        if not tag_id:
            _LOGGER.debug("Ignoring Mise en Place Assistant create event without tag_id")
            return
        item = _mock_item(event.data.get(ATTR_ITEM_ID))
        quantity = event.data.get(ATTR_QUANTITY, 0)
        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            _LOGGER.debug(
                "Invalid Mise en Place Assistant create quantity from M5Dial: tag_id=%s quantity=%s",
                tag_id,
                event.data.get(ATTR_QUANTITY),
            )
            quantity = 0
        _LOGGER.info(
            "Creating Mise en Place Assistant container from M5Dial: tag_id=%s item_id=%s quantity=%s location=%s",
            tag_id,
            event.data.get(ATTR_ITEM_ID),
            quantity,
            event.data.get(ATTR_LOCATION),
        )
        hass.async_create_task(
            manager.async_create_container(
                tag_id=tag_id,
                quantity=quantity,
                location=event.data.get(ATTR_LOCATION),
                state=event.data.get(ATTR_STATE, "unknown"),
                unit=event.data.get(ATTR_UNIT) or (item or {}).get("unit", DEFAULT_UNIT),
                item_id=event.data.get(ATTR_ITEM_ID),
                item_label=event.data.get(ATTR_ITEM_LABEL) or (item or {}).get("label"),
                item_format=event.data.get(ATTR_ITEM_FORMAT)
                or (item or {}).get("format"),
            )
        )

    @callback
    def handle_update_from_dial(event) -> None:
        """Update a container from the M5Dial flow."""
        if not is_enrolled_dial_event(event):
            return
        tag_id = event.data.get(ATTR_TAG_ID)
        if not tag_id:
            _LOGGER.debug("Ignoring Mise en Place Assistant update event without tag_id")
            return
        quantity = event.data.get(ATTR_QUANTITY)
        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            _LOGGER.debug(
                "Ignoring Mise en Place Assistant update with invalid quantity: tag_id=%s quantity=%s",
                tag_id,
                quantity,
            )
            return
        _LOGGER.info(
            "Updating Mise en Place Assistant container from M5Dial: tag_id=%s quantity=%s location=%s",
            tag_id,
            quantity,
            event.data.get(ATTR_LOCATION),
        )
        hass.async_create_task(
            manager.async_update_container(
                tag_id=tag_id,
                quantity=quantity,
                location=event.data.get(ATTR_LOCATION),
                create_missing=True,
            )
        )

    @callback
    def handle_clean_from_dial(event) -> None:
        """Mark a known container clean after the Dial's post-wash scan."""
        if not is_enrolled_dial_event(event):
            return
        tag_id = event.data.get(ATTR_TAG_ID)
        if not tag_id:
            _LOGGER.debug("Ignoring Mise en Place Assistant clean event without tag_id")
            return
        hass.async_create_task(
            manager.async_mark_container_clean(tag_id, location=event.data.get(ATTR_LOCATION))
        )

    @callback
    def handle_inventory_confirm(event) -> None:
        """Handle scanner events from ESPHome/M5Dial."""
        if not is_enrolled_dial_event(event):
            return
        tag_id = event.data.get(ATTR_TAG_ID)
        if not tag_id:
            _LOGGER.debug("Ignoring Mise en Place Assistant inventory confirm event without tag_id")
            return
        quantity = event.data.get(ATTR_QUANTITY)
        if quantity is not None:
            try:
                quantity = float(quantity)
            except (TypeError, ValueError):
                _LOGGER.debug(
                    "Ignoring Mise en Place Assistant inventory confirm with invalid quantity: tag_id=%s quantity=%s",
                    tag_id,
                    quantity,
                )
                return
        mode = event.data.get(ATTR_MODE, "set")
        _LOGGER.info(
            "Applying Mise en Place Assistant inventory confirm event: tag_id=%s quantity=%s mode=%s",
            tag_id,
            quantity,
            mode,
        )
        hass.async_create_task(
            manager.async_scan_container(tag_id=tag_id, quantity=quantity, mode=mode)
        )

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_INVENTORY_CONFIRM, handle_inventory_confirm)
    )
    entry.async_on_unload(hass.bus.async_listen(EVENT_MISE_EN_PLACE_ASSISTANT_SCAN, handle_mise_en_place_assistant_scan))
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_MISE_EN_PLACE_ASSISTANT_CREATE_CONTAINER, handle_create_from_dial)
    )
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_MISE_EN_PLACE_ASSISTANT_UPDATE_CONTAINER, handle_update_from_dial)
    )
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_MISE_EN_PLACE_ASSISTANT_MARK_CLEAN, handle_clean_from_dial)
    )
    _LOGGER.debug("Registered Mise en Place Assistant event listeners")
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload Mise en Place Assistant when options change."""
    _LOGGER.info("Reloading Mise en Place Assistant entry after options update: %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Mise en Place Assistant config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            async_unregister_panel(hass)
        _LOGGER.info("Mise en Place Assistant entry unloaded: entry_id=%s", entry.entry_id)
    return unload_ok
