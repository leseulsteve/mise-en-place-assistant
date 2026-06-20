"""The Mise en Place Assistant integration."""

from __future__ import annotations

import logging
import math
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
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
    PLATFORMS,
    SERVICE_CREATE_CONTAINER,
    SERVICE_CREATE_LOCATION,
    SERVICE_FILL_CONTAINER,
    SERVICE_MARK_CONTAINER_CLEAN,
    SERVICE_REMOVE_ITEMS,
    SERVICE_SCAN_CONTAINER,
    SERVICE_UPDATE_CONTAINER,
)
from .panel import async_register_panel, async_unregister_panel
from .mealie import MealieCatalogError
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
ATTR_ITEM_ID = "item_id"

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Mise en Place Assistant services."""

    async def handle_create_location(call: ServiceCall) -> None:
        manager = _manager(hass)
        _LOGGER.info("Creating Mise en Place Assistant location: %s", call.data[ATTR_NAME])
        await manager.async_create_location(call.data[ATTR_NAME])

    async def handle_create_container(call: ServiceCall) -> None:
        manager = _manager(hass)
        try:
            item = await manager.async_catalog_item(call.data[ATTR_ITEM_ID])
        except (MealieCatalogError, ValueError) as err:
            raise ServiceValidationError(str(err)) from err
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
                unit=item["unit"],
                item_id=item["id"],
                item_label=item["label"],
                item_format=item["format"],
                source_provider=manager.catalog_provider(),
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_update_container(call: ServiceCall) -> None:
        manager = _manager(hass)
        item = None
        if ATTR_ITEM_ID in call.data:
            try:
                item = await manager.async_catalog_item(call.data[ATTR_ITEM_ID])
            except (MealieCatalogError, ValueError) as err:
                raise ServiceValidationError(str(err)) from err
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
                unit=call.data.get(ATTR_UNIT) or (item or {}).get("unit"),
                item_id=(item or {}).get("id"),
                item_label=(item or {}).get("label"),
                item_format=(item or {}).get("format"),
                source_provider=manager.catalog_provider() if item else "local",
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
                vol.Required(ATTR_ITEM_ID): cv.string,
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
    _LOGGER.debug("Registered Mise en Place Assistant services")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mise en Place Assistant from a config entry."""
    _LOGGER.debug("Starting Mise en Place Assistant config-entry setup")
    manager = MiseEnPlaceAssistantInventory(hass, entry)
    await manager.async_load()
    try:
        await manager.async_refresh_catalog()
    except MealieCatalogError as err:
        raise ConfigEntryNotReady("The selected catalog provider must be available before Mise en Place Assistant can start") from err

    async def refresh_catalog(_now) -> None:
        """Keep the selected provider's food names current without switching source."""
        try:
            await manager.async_refresh_catalog()
        except MealieCatalogError as err:
            _LOGGER.warning("Catalog provider refresh failed; food updates are paused: %s", err)

    entry.async_on_unload(
        async_track_time_interval(hass, refresh_catalog, timedelta(minutes=5))
    )
    _LOGGER.debug(
        "Loaded inventory storage: containers=%d locations=%d logbook=%d",
        len(manager.containers),
        len(manager.locations),
        len(manager.logbook),
    )

    enrolled_source = entry.options.get(
        CONF_M5DIAL_EVENT_SOURCE,
        entry.data.get(CONF_M5DIAL_EVENT_SOURCE, ""),
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Forwarded integration platform setups: platforms=%s", PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    if len(hass.data[DOMAIN]) == 1:
        await async_register_panel(hass)
    else:
        _LOGGER.debug("Sidebar panel already registered; reusing it for another inventory entry")
    _LOGGER.info(
        "Mise en Place Assistant entry loaded: containers=%d locations=%d",
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

    async def show_dial_operation_result(tag_id: str, *, success: bool, message: str) -> None:
        """Acknowledge the completed Dial write instead of assuming it succeeded."""
        await call_m5dial(
            "show_operation_result",
            {
                "tag_id": tag_id,
                "success": success,
                "message": message,
            },
        )

    async def show_create_flow(tag_id: str) -> None:
        """Tell the M5Dial to show the create-container flow."""
        payload = await manager.async_catalog_payload()
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
        payload = await manager.async_catalog_payload()
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
                "item_label": manager.item_label_for_container(container)
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
        payload = await manager.async_catalog_payload()
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
        quantity = event.data.get(ATTR_QUANTITY, 0)
        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            _LOGGER.debug(
                "Invalid Mise en Place Assistant create quantity from M5Dial: tag_id=%s quantity=%s",
                tag_id,
                event.data.get(ATTR_QUANTITY),
            )
            hass.async_create_task(
                show_dial_operation_result(
                    tag_id,
                    success=False,
                    message="Could not save",
                )
            )
            return
        _LOGGER.info(
            "Creating Mise en Place Assistant container from M5Dial: tag_id=%s item_id=%s quantity=%s location=%s",
            tag_id,
            event.data.get(ATTR_ITEM_ID),
            quantity,
            event.data.get(ATTR_LOCATION),
        )
        async def create_from_mealie() -> None:
            try:
                item = await manager.async_catalog_item(event.data.get(ATTR_ITEM_ID, ""))
                await manager.async_create_container(
                    tag_id=tag_id, quantity=quantity, location=event.data.get(ATTR_LOCATION),
                    state=event.data.get(ATTR_STATE, "unknown"), unit=item["unit"], item_id=item["id"],
                    item_label=item["label"], item_format=item["format"], source_provider=manager.catalog_provider(),
                )
            except (MealieCatalogError, ValueError) as err:
                _LOGGER.warning("Could not create M5Dial container for tag_id=%s: %s", tag_id, err)
                await show_dial_operation_result(
                    tag_id,
                    success=False,
                    message="Could not save",
                )
            except Exception:  # noqa: BLE001 - the Dial needs an explicit write failure.
                _LOGGER.exception("Could not create M5Dial container for tag_id=%s", tag_id)
                await show_dial_operation_result(
                    tag_id,
                    success=False,
                    message="Could not save",
                )
            else:
                await show_dial_operation_result(tag_id, success=True, message="Saved")

        hass.async_create_task(create_from_mealie())

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
            hass.async_create_task(
                show_dial_operation_result(
                    tag_id,
                    success=False,
                    message="Could not save",
                )
            )
            return
        _LOGGER.info(
            "Updating Mise en Place Assistant container from M5Dial: tag_id=%s quantity=%s location=%s",
            tag_id,
            quantity,
            event.data.get(ATTR_LOCATION),
        )
        async def update_from_dial() -> None:
            try:
                await manager.async_update_container(
                    tag_id=tag_id,
                    quantity=quantity,
                    location=event.data.get(ATTR_LOCATION),
                    create_missing=True,
                )
            except ValueError as err:
                _LOGGER.warning("Could not update M5Dial container for tag_id=%s: %s", tag_id, err)
                await show_dial_operation_result(
                    tag_id,
                    success=False,
                    message="Could not save",
                )
            except Exception:  # noqa: BLE001 - the Dial needs an explicit write failure.
                _LOGGER.exception("Could not update M5Dial container for tag_id=%s", tag_id)
                await show_dial_operation_result(
                    tag_id,
                    success=False,
                    message="Could not save",
                )
            else:
                await show_dial_operation_result(tag_id, success=True, message="Saved")

        hass.async_create_task(update_from_dial())

    @callback
    def handle_clean_from_dial(event) -> None:
        """Mark a known container clean after the Dial's post-wash scan."""
        if not is_enrolled_dial_event(event):
            return
        tag_id = event.data.get(ATTR_TAG_ID)
        if not tag_id:
            _LOGGER.debug("Ignoring Mise en Place Assistant clean event without tag_id")
            return
        async def clean_from_dial() -> None:
            try:
                await manager.async_mark_container_clean(tag_id, location=event.data.get(ATTR_LOCATION))
            except (KeyError, ValueError) as err:
                _LOGGER.warning("Could not mark M5Dial container clean for tag_id=%s: %s", tag_id, err)
                await show_dial_operation_result(
                    tag_id,
                    success=False,
                    message="Could not save",
                )
            except Exception:  # noqa: BLE001 - the Dial needs an explicit write failure.
                _LOGGER.exception("Could not mark M5Dial container clean for tag_id=%s", tag_id)
                await show_dial_operation_result(
                    tag_id,
                    success=False,
                    message="Could not save",
                )
            else:
                await show_dial_operation_result(tag_id, success=True, message="Saved")

        hass.async_create_task(clean_from_dial())

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
    _LOGGER.debug("Starting Mise en Place Assistant config-entry unload")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            async_unregister_panel(hass)
            _LOGGER.debug("Removed final inventory entry and sidebar panel")
        else:
            _LOGGER.debug("Keeping sidebar panel for %d remaining inventory entries", len(hass.data[DOMAIN]))
        _LOGGER.info("Mise en Place Assistant entry unloaded")
    else:
        _LOGGER.warning("Could not unload Mise en Place Assistant platforms; sidebar panel remains registered")
    return unload_ok
