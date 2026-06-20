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
    EVENT_MISE_EN_PLACE_ASSISTANT_SCAN,
    EVENT_MISE_EN_PLACE_ASSISTANT_UPDATE_CONTAINER,
    EVENT_INVENTORY_CONFIRM,
    PLATFORMS,
    SERVICE_CREATE_CONTAINER,
    SERVICE_ARCHIVE_CONTAINER,
    SERVICE_CLEAR_CONTAINER,
    SERVICE_ADD_EMPTY_CONTAINERS_TO_SHOPPING_LIST,
    SERVICE_ADD_MISSING_PRODUCTS_TO_SHOPPING_LIST,
    SERVICE_ADD_TO_SHOPPING_LIST,
    SERVICE_UPDATE_PRODUCT_METADATA,
    SERVICE_CREATE_RECIPE_CONTAINER,
    SERVICE_CREATE_LOCATION,
    SERVICE_DELETE_LOCATION,
    SERVICE_MOVE_CONTAINER,
    SERVICE_UPDATE_LOCATION,
    SERVICE_FILL_CONTAINER,
    SERVICE_REMOVE_ITEMS,
    SERVICE_RESTORE_CONTAINER,
    SERVICE_SCAN_CONTAINER,
    SERVICE_UPDATE_CONTAINER,
    PROVIDER_MOCKED,
    LOCATION_TYPES,
    PRODUCT_CONTAINER_POLICIES,
    PRODUCT_MEAL_ROLES,
    PRODUCT_STORAGE_BEHAVIORS,
)
from .grocy import GrocyCatalogError
from .kitchenowl import KitchenOwlError
from .panel import async_register_panel, async_unregister_panel
from .mealie import MealieCatalogError
from .store import MiseEnPlaceAssistantInventory

_LOGGER = logging.getLogger(__name__)

ATTR_DELTA = "delta"
ATTR_LOCATION = "location"
ATTR_MODE = "mode"
ATTR_NAME = "name"
ATTR_QUANTITY = "quantity"
ATTR_TAG_ID = "tag_id"
ATTR_UNIT = "unit"
ATTR_ITEM_ID = "item_id"
ATTR_RECIPE_ID = "recipe_id"
ATTR_CONTENT_KIND = "content_kind"
ATTR_LOCATION_ID = "location_id"
ATTR_LOCATION_TYPE = "location_type"
ATTR_AREA_ID = "area_id"
ATTR_SENSORS = "sensors"
ATTR_MONITORING = "monitoring"
ATTR_DESCRIPTION = "description"
ATTR_BEST_BEFORE_DATE = "best_before_date"
ATTR_PURCHASED_DATE = "purchased_date"
ATTR_OPENED_DATE = "opened_date"
ATTR_PRICE = "price"
ATTR_CONTAINER_POLICY = "container_policy"
ATTR_STORAGE_BEHAVIOR = "storage_behavior"
ATTR_MEAL_ROLE = "meal_role"
ATTR_AVAILABLE_IN_MEALIE = "available_in_mealie"
ATTR_REQUEST_ID = "request_id"
ATTR_SOURCE_PROVIDER = "source_provider"

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


def _location_data(call: ServiceCall) -> dict:
    """Extract validated configuration that belongs to a location."""
    sensors = call.data.get(ATTR_SENSORS, {})
    if not isinstance(sensors, dict):
        raise ServiceValidationError("sensors must be an object")
    allowed_roles = {"temperature", "humidity", "door", "power", "energy", "power_switch"}
    for role, entity_id in sensors.items():
        if role not in allowed_roles or not isinstance(entity_id, str) or "." not in entity_id:
            raise ServiceValidationError("Invalid location sensor association")
        domain = entity_id.split(".", 1)[0]
        if role == "door" and domain != "binary_sensor":
            raise ServiceValidationError("door must reference a binary_sensor entity")
        if role == "power_switch" and domain != "switch":
            raise ServiceValidationError("power_switch must reference a switch entity")
        if role not in {"door", "power_switch"} and domain != "sensor":
            raise ServiceValidationError(f"{role} must reference a sensor entity")
    monitoring = call.data.get(ATTR_MONITORING, {})
    if not isinstance(monitoring, dict):
        raise ServiceValidationError("monitoring must be an object")
    for key in ("temperature_min", "temperature_max"):
        if key in monitoring:
            monitoring[key] = _finite_number(monitoring[key])
    return {
        "name": call.data.get(ATTR_NAME),
        "location_type": call.data.get(ATTR_LOCATION_TYPE, "other"),
        "area_id": call.data.get(ATTR_AREA_ID),
        "sensors": sensors,
        "monitoring": monitoring,
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Mise en Place Assistant services."""

    async def handle_create_location(call: ServiceCall) -> None:
        manager = _manager(hass)
        try:
            await manager.async_create_location_record(**_location_data(call))
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_update_location(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_update_location(call.data[ATTR_LOCATION_ID], **_location_data(call))
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_delete_location(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_delete_location(call.data[ATTR_LOCATION_ID])
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_move_container(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_update_container(
                tag_id=call.data[ATTR_TAG_ID], location_id=call.data[ATTR_LOCATION_ID]
            )
        except (KeyError, ValueError) as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_clear_container(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_clear_container(call.data[ATTR_TAG_ID])
        except (KeyError, ValueError) as err:
            raise ServiceValidationError(
                f"Unknown Mise en Place Assistant container tag_id: {err.args[0]}"
                if isinstance(err, KeyError) else str(err)
            ) from err

    async def handle_archive_container(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_archive_container(call.data[ATTR_TAG_ID])
        except (KeyError, ValueError) as err:
            raise ServiceValidationError(
                f"Unknown Mise en Place Assistant container tag_id: {err.args[0]}"
                if isinstance(err, KeyError) else str(err)
            ) from err

    async def handle_restore_container(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_restore_container(call.data[ATTR_TAG_ID])
        except (KeyError, ValueError) as err:
            raise ServiceValidationError(
                f"Unknown Mise en Place Assistant container tag_id: {err.args[0]}"
                if isinstance(err, KeyError) else str(err)
            ) from err

    async def handle_create_container(call: ServiceCall) -> None:
        manager = _manager(hass)
        try:
            item = await manager.async_catalog_item(call.data[ATTR_ITEM_ID])
        except (MealieCatalogError, ValueError) as err:
            raise ServiceValidationError(str(err)) from err
        _LOGGER.info(
            "Creating Mise en Place Assistant container from service: tag_id=%s item_id=%s quantity=%s location=%s location_id=%s",
            call.data[ATTR_TAG_ID], call.data.get(ATTR_ITEM_ID),
            call.data.get(ATTR_QUANTITY, 0), call.data.get(ATTR_LOCATION),
            call.data.get(ATTR_LOCATION_ID),
        )
        try:
            await manager.async_create_container(
                tag_id=call.data[ATTR_TAG_ID], name=call.data.get(ATTR_NAME),
                quantity=call.data.get(ATTR_QUANTITY, 0), location=call.data.get(ATTR_LOCATION),
                location_id=call.data.get(ATTR_LOCATION_ID),
                unit=item["unit"], item_id=item["id"], item_label=item["label"],
                item_format=item["format"], source_provider=item.get("provider", manager.catalog_provider()),
                best_before_date=call.data.get(ATTR_BEST_BEFORE_DATE),
                purchased_date=call.data.get(ATTR_PURCHASED_DATE),
                opened_date=call.data.get(ATTR_OPENED_DATE),
                price=call.data.get(ATTR_PRICE),
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_create_recipe_container(call: ServiceCall) -> None:
        manager = _manager(hass)
        try:
            await manager.async_create_recipe_container(
                recipe_id=call.data[ATTR_RECIPE_ID],
                content_kind=call.data[ATTR_CONTENT_KIND],
                tag_id=call.data[ATTR_TAG_ID], name=call.data.get(ATTR_NAME),
                quantity=call.data.get(ATTR_QUANTITY, 0), location=call.data.get(ATTR_LOCATION),
                location_id=call.data.get(ATTR_LOCATION_ID),
            )
        except (MealieCatalogError, ValueError) as err:
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
            "Updating Mise en Place Assistant container from service: tag_id=%s quantity=%s delta=%s location=%s location_id=%s",
            call.data[ATTR_TAG_ID],
            call.data.get(ATTR_QUANTITY),
            call.data.get(ATTR_DELTA),
            call.data.get(ATTR_LOCATION),
            call.data.get(ATTR_LOCATION_ID),
        )
        try:
            await manager.async_update_container(
                tag_id=call.data[ATTR_TAG_ID],
                quantity=call.data.get(ATTR_QUANTITY),
                delta=call.data.get(ATTR_DELTA),
                location=call.data.get(ATTR_LOCATION),
                location_id=call.data.get(ATTR_LOCATION_ID),
                name=call.data.get(ATTR_NAME),
                unit=call.data.get(ATTR_UNIT) or (item or {}).get("unit"),
                item_id=(item or {}).get("id"),
                item_label=(item or {}).get("label"),
                item_format=(item or {}).get("format"),
                source_provider=item.get("provider", manager.catalog_provider()) if item else "local",
                best_before_date=call.data.get(ATTR_BEST_BEFORE_DATE),
                purchased_date=call.data.get(ATTR_PURCHASED_DATE),
                opened_date=call.data.get(ATTR_OPENED_DATE),
                price=call.data.get(ATTR_PRICE),
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
        except (KeyError, ValueError) as err:
            raise ServiceValidationError(
                f"Unknown Mise en Place Assistant container tag_id: {err.args[0]}"
                if isinstance(err, KeyError) else str(err)
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
        except (KeyError, ValueError) as err:
            raise ServiceValidationError(
                f"Unknown Mise en Place Assistant container tag_id: {err.args[0]}"
                if isinstance(err, KeyError) else str(err)
            ) from err

    async def handle_scan_container(call: ServiceCall) -> None:
        manager = _manager(hass)
        _LOGGER.info(
            "Applying Mise en Place Assistant scan service: tag_id=%s quantity=%s mode=%s",
            call.data[ATTR_TAG_ID],
            call.data.get(ATTR_QUANTITY),
            call.data.get(ATTR_MODE, "set"),
        )
        try:
            await manager.async_scan_container(
                tag_id=call.data[ATTR_TAG_ID],
                quantity=call.data.get(ATTR_QUANTITY),
                mode=call.data.get(ATTR_MODE, "set"),
            )
        except (KeyError, ValueError) as err:
            raise ServiceValidationError(
                f"Unknown Mise en Place Assistant container tag_id: {err.args[0]}"
                if isinstance(err, KeyError) else str(err)
            ) from err

    async def handle_add_to_shopping_list(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_add_to_shopping_list(
                call.data.get(ATTR_NAME, ""),
                call.data.get(ATTR_DESCRIPTION, ""),
                item_id=call.data.get(ATTR_ITEM_ID),
                quantity=call.data.get(ATTR_QUANTITY, 1),
            )
        except (KitchenOwlError, ValueError, MealieCatalogError) as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_add_empty_containers_to_shopping_list(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_add_empty_containers_to_shopping_list()
        except (KitchenOwlError, GrocyCatalogError, ValueError) as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_add_missing_products_to_shopping_list(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_add_missing_products_to_shopping_list()
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def handle_update_product_metadata(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_update_product_metadata(
                call.data[ATTR_ITEM_ID],
                container_policy=call.data.get(ATTR_CONTAINER_POLICY, "unknown"),
                storage_behavior=call.data.get(ATTR_STORAGE_BEHAVIOR, "unknown"),
                meal_role=call.data.get(ATTR_MEAL_ROLE, "unknown"),
                available_in_mealie=call.data.get(ATTR_AVAILABLE_IN_MEALIE),
            )
        except (MealieCatalogError, ValueError) as err:
            raise ServiceValidationError(str(err)) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_LOCATION,
        handle_create_location,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_NAME, default=""): cv.string,
                vol.Optional(ATTR_LOCATION_TYPE, default="other"): vol.In(LOCATION_TYPES),
                vol.Optional(ATTR_AREA_ID): cv.string,
                vol.Optional(ATTR_SENSORS, default={}): dict,
                vol.Optional(ATTR_MONITORING, default={}): dict,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_LOCATION,
        handle_update_location,
        schema=vol.Schema(
            {
                vol.Required(ATTR_LOCATION_ID): cv.string,
                vol.Optional(ATTR_NAME, default=""): cv.string,
                vol.Optional(ATTR_LOCATION_TYPE, default="other"): vol.In(LOCATION_TYPES),
                vol.Optional(ATTR_AREA_ID): cv.string,
                vol.Optional(ATTR_SENSORS, default={}): dict,
                vol.Optional(ATTR_MONITORING, default={}): dict,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_LOCATION,
        handle_delete_location,
        schema=vol.Schema({vol.Required(ATTR_LOCATION_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MOVE_CONTAINER,
        handle_move_container,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TAG_ID): cv.string,
                vol.Required(ATTR_LOCATION_ID): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CONTAINER,
        handle_clear_container,
        schema=vol.Schema({vol.Required(ATTR_TAG_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ARCHIVE_CONTAINER,
        handle_archive_container,
        schema=vol.Schema({vol.Required(ATTR_TAG_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTORE_CONTAINER,
        handle_restore_container,
        schema=vol.Schema({vol.Required(ATTR_TAG_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_RECIPE_CONTAINER,
        handle_create_recipe_container,
        schema=vol.Schema(
            {
                vol.Required(ATTR_TAG_ID): cv.string,
                vol.Required(ATTR_RECIPE_ID): cv.string,
                vol.Required(ATTR_CONTENT_KIND): vol.In(["recipe", "meal"]),
                vol.Optional(ATTR_NAME): cv.string,
                vol.Optional(ATTR_QUANTITY, default=0): _nonnegative_number,
                vol.Optional(ATTR_LOCATION): cv.string,
                vol.Optional(ATTR_LOCATION_ID): cv.string,
            }
        ),
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
                vol.Optional(ATTR_LOCATION_ID): cv.string,
                vol.Required(ATTR_ITEM_ID): cv.string,
                vol.Optional(ATTR_BEST_BEFORE_DATE): cv.string,
                vol.Optional(ATTR_PURCHASED_DATE): cv.string,
                vol.Optional(ATTR_OPENED_DATE): cv.string,
                vol.Optional(ATTR_PRICE): _nonnegative_number,
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
                vol.Optional(ATTR_LOCATION_ID): cv.string,
                vol.Optional(ATTR_UNIT): cv.string,
                vol.Optional(ATTR_ITEM_ID): cv.string,
                vol.Optional(ATTR_BEST_BEFORE_DATE): cv.string,
                vol.Optional(ATTR_PURCHASED_DATE): cv.string,
                vol.Optional(ATTR_OPENED_DATE): cv.string,
                vol.Optional(ATTR_PRICE): _nonnegative_number,
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
        SERVICE_ADD_TO_SHOPPING_LIST,
        handle_add_to_shopping_list,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_NAME, default=""): cv.string,
                vol.Optional(ATTR_DESCRIPTION, default=""): cv.string,
                vol.Optional(ATTR_ITEM_ID): cv.string,
                vol.Optional(ATTR_QUANTITY, default=1): _positive_number,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_EMPTY_CONTAINERS_TO_SHOPPING_LIST,
        handle_add_empty_containers_to_shopping_list,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_MISSING_PRODUCTS_TO_SHOPPING_LIST,
        handle_add_missing_products_to_shopping_list,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_PRODUCT_METADATA,
        handle_update_product_metadata,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ITEM_ID): cv.string,
                vol.Required(ATTR_CONTAINER_POLICY): vol.In(PRODUCT_CONTAINER_POLICIES),
                vol.Required(ATTR_STORAGE_BEHAVIOR): vol.In(PRODUCT_STORAGE_BEHAVIORS),
                vol.Required(ATTR_MEAL_ROLE): vol.In(PRODUCT_MEAL_ROLES),
                vol.Required(ATTR_AVAILABLE_IN_MEALIE): cv.boolean,
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
        await manager.async_validate_workflow_providers()
    except MealieCatalogError as err:
        raise ConfigEntryNotReady("Configured data providers must be available before Mise en Place Assistant can start") from err
    if manager.effective_catalog_providers() == [PROVIDER_MOCKED] and not manager.containers:
        seeded = await manager.async_seed_demo_data()
        _LOGGER.info("Seeded %d sample containers for the Mocked catalog", seeded)

    async def refresh_catalog(_now) -> None:
        """Keep configured providers' food names current without switching source."""
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
        len(manager.storage_locations()),
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
        len(manager.storage_locations()),
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

    def _event_request_id(event) -> int:
        """Return the Dial request id, or 0 for older firmware."""
        try:
            return int(event.data.get(ATTR_REQUEST_ID, 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _dial_success_title(container: dict | None = None, item: dict | None = None) -> str:
        """Return a concise provider-aware Dial success title."""
        product = manager.product_for_container(container or {}) if container else None
        provider = ((product or item or {}).get("source") or {}).get("provider") or (item or {}).get("provider")
        if provider == "grocy":
            return "Grocy stock saved"
        if provider == "mealie" or str(provider).endswith("_recipe"):
            return "Mealie prep saved"
        return "Mise saved"

    async def show_dial_operation_result(
        tag_id: str,
        *,
        success: bool,
        message: str,
        request_id: int = 0,
        title: str | None = None,
    ) -> None:
        """Acknowledge the completed Dial write instead of assuming it succeeded."""
        await call_m5dial(
            "show_operation_result",
            {
                "tag_id": tag_id,
                "request_id": request_id,
                "success": success,
                "title": title or ("Saved" if success else "Could not save"),
                "message": message,
            },
        )

    async def show_create_flow(tag_id: str, request_id: int = 0) -> None:
        """Tell the M5Dial to show the create-container flow."""
        payload = await manager.async_catalog_payload()
        dial_items = [
            {**item, "content_kind": "ingredient"}
            for item in payload["items"]
        ] + [
            {**recipe, "content_kind": "meal", "provider": manager.recipe_provider_for_item(recipe)}
            for recipe in payload["recipes"]
        ]
        _LOGGER.info(
            "Showing Mise en Place Assistant create flow on M5Dial: tag_id=%s items=%d locations=%d request_id=%s",
            tag_id,
            len(dial_items),
            len(payload["locations"]),
            request_id,
        )
        await call_m5dial(
            "show_create_container",
            {
                "tag_id": tag_id,
                "request_id": request_id,
                "incoming_item_ids": [item["id"] for item in dial_items],
                "incoming_item_labels": [item["label"] for item in dial_items],
                "incoming_item_formats": [item["format"] for item in dial_items],
                "incoming_item_units": [item["unit"] for item in dial_items],
                "incoming_item_providers": [item.get("provider", "") for item in dial_items],
                "incoming_item_content_kinds": [item.get("content_kind", "ingredient") for item in dial_items],
                "incoming_location_ids": [location["id"] for location in payload["locations"]],
                "incoming_location_labels": [location["label"] for location in payload["locations"]],
            },
        )

    async def show_known_flow(tag_id: str, container: dict, request_id: int = 0) -> None:
        """Tell the M5Dial to show the known-container flow."""
        payload = await manager.async_catalog_payload()
        product = manager.product_for_container(container) or {}
        source = product.get("source") or {}
        _LOGGER.info(
            "Showing Mise en Place Assistant known flow on M5Dial: tag_id=%s quantity=%s location=%s request_id=%s",
            tag_id,
            container.get("quantity"),
            container.get("location"),
            request_id,
        )
        await call_m5dial(
            "show_known_container",
            {
                "tag_id": tag_id,
                "request_id": request_id,
                "item_label": manager.item_label_for_container(container)
                or container.get("name")
                or "Container",
                "item_format": container.get("item_format") or "",
                "item_provider": source.get("provider") or "",
                "content_kind": container.get("content_kind") or "ingredient",
                "quantity": float(container.get("quantity", 0)),
                "unit": container.get("unit") or DEFAULT_UNIT,
                "location_id": container.get("location_id") or "",
                "location_label": container.get("location") or "The Void",
                "incoming_location_ids": [location["id"] for location in payload["locations"]],
                "incoming_location_labels": [location["label"] for location in payload["locations"]],
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
        request_id = _event_request_id(event)
        container = manager.get_container(tag_id)
        if container:
            _LOGGER.info("Known Mise en Place Assistant NFC tag scanned: tag_id=%s request_id=%s", tag_id, request_id)
            hass.async_create_task(show_known_flow(tag_id, container, request_id))
        else:
            _LOGGER.info("Unknown Mise en Place Assistant NFC tag scanned: tag_id=%s request_id=%s", tag_id, request_id)
            hass.async_create_task(show_create_flow(tag_id, request_id))

    @callback
    def handle_create_from_dial(event) -> None:
        """Create a container from the M5Dial flow."""
        if not is_enrolled_dial_event(event):
            return
        tag_id = event.data.get(ATTR_TAG_ID)
        if not tag_id:
            _LOGGER.debug("Ignoring Mise en Place Assistant create event without tag_id")
            return
        request_id = _event_request_id(event)
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
                    request_id=request_id,
                    title="Bad quantity",
                    message="Quantity was not a number",
                )
            )
            return
        content_kind = event.data.get(ATTR_CONTENT_KIND) or "ingredient"
        _LOGGER.info(
            "Creating Mise en Place Assistant container from M5Dial: tag_id=%s item_id=%s quantity=%s location=%s content_kind=%s provider=%s request_id=%s",
            tag_id,
            event.data.get(ATTR_ITEM_ID),
            quantity,
            event.data.get(ATTR_LOCATION_ID),
            content_kind,
            event.data.get(ATTR_SOURCE_PROVIDER),
            request_id,
        )
        async def create_from_mealie() -> None:
            try:
                if content_kind in {"recipe", "meal"}:
                    item = await manager.async_recipe_item(event.data.get(ATTR_ITEM_ID, ""))
                    await manager.async_create_recipe_container(
                        tag_id=tag_id,
                        quantity=quantity,
                        location_id=event.data.get(ATTR_LOCATION_ID),
                        recipe_id=item["id"],
                        content_kind=content_kind,
                    )
                else:
                    item = await manager.async_catalog_item(event.data.get(ATTR_ITEM_ID, ""))
                    await manager.async_create_container(
                        tag_id=tag_id, quantity=quantity, location_id=event.data.get(ATTR_LOCATION_ID),
                        unit=item["unit"], item_id=item["id"],
                        item_label=item["label"], item_format=item["format"],
                        source_provider=item.get("provider", manager.catalog_provider()),
                    )
            except (MealieCatalogError, ValueError) as err:
                _LOGGER.warning("Could not create M5Dial container for tag_id=%s: %s", tag_id, err)
                await show_dial_operation_result(
                    tag_id,
                    success=False,
                    request_id=request_id,
                    title="Save failed",
                    message=str(err)[:64] or "Could not save",
                )
            except Exception:  # noqa: BLE001 - the Dial needs an explicit write failure.
                _LOGGER.exception("Could not create M5Dial container for tag_id=%s", tag_id)
                await show_dial_operation_result(
                    tag_id,
                    success=False,
                    request_id=request_id,
                    title="Save failed",
                    message="Unexpected Home Assistant error",
                )
            else:
                await show_dial_operation_result(
                    tag_id,
                    success=True,
                    request_id=request_id,
                    title=_dial_success_title(item=item),
                    message=f"{item['label']} at {event.data.get(ATTR_LOCATION) or event.data.get(ATTR_LOCATION_ID) or 'selected location'}",
                )

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
        request_id = _event_request_id(event)
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
                    request_id=request_id,
                    title="Bad quantity",
                    message="Quantity was not a number",
                )
            )
            return
        _LOGGER.info(
            "Updating Mise en Place Assistant container from M5Dial: tag_id=%s quantity=%s location=%s request_id=%s",
            tag_id,
            quantity,
            event.data.get(ATTR_LOCATION_ID),
            request_id,
        )
        async def update_from_dial() -> None:
            before = manager.get_container(tag_id)
            try:
                await manager.async_update_container(
                    tag_id=tag_id,
                    quantity=quantity,
                    location_id=event.data.get(ATTR_LOCATION_ID),
                )
            except (KeyError, ValueError) as err:
                _LOGGER.warning("Could not update M5Dial container for tag_id=%s: %s", tag_id, err)
                await show_dial_operation_result(
                    tag_id,
                    success=False,
                    request_id=request_id,
                    title="Save failed",
                    message=str(err)[:64] or "Could not save",
                )
            except Exception:  # noqa: BLE001 - the Dial needs an explicit write failure.
                _LOGGER.exception("Could not update M5Dial container for tag_id=%s", tag_id)
                await show_dial_operation_result(
                    tag_id,
                    success=False,
                    request_id=request_id,
                    title="Save failed",
                    message="Unexpected Home Assistant error",
                )
            else:
                after = manager.get_container(tag_id) or before
                await show_dial_operation_result(
                    tag_id,
                    success=True,
                    request_id=request_id,
                    title=_dial_success_title(after),
                    message=f"{quantity:g} {(after or {}).get('unit') or DEFAULT_UNIT} at {event.data.get(ATTR_LOCATION) or (after or {}).get('location') or 'selected location'}",
                )

        hass.async_create_task(update_from_dial())

    async def _async_confirm_inventory(
        manager: MiseEnPlaceAssistantInventory,
        tag_id: str,
        quantity: float | None,
        mode: str,
    ) -> None:
        try:
            await manager.async_scan_container(tag_id=tag_id, quantity=quantity, mode=mode)
        except (KeyError, ValueError) as err:
            _LOGGER.warning("Could not apply inventory confirm for tag_id=%s: %s", tag_id, err)

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
            _async_confirm_inventory(manager, tag_id, quantity, mode)
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
