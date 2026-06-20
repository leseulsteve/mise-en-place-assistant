"""Constants for the Mise en Place Assistant integration."""

from __future__ import annotations

DOMAIN = "mise_en_place_assistant"
NAME = "Mise en Place Assistant"

PLATFORMS = ["sensor", "select"]
PANEL_URL_PATH = "mise_en_place_assistant"

CONF_INITIAL_LOCATIONS = "initial_locations"
CONF_M5DIAL_SERVICE_PREFIX = "m5dial_service_prefix"
CONF_M5DIAL_DEVICE_ID = "m5dial_device_id"
CONF_M5DIAL_EVENT_SOURCE = "m5dial_event_source"
CONF_M5DIAL_PRESENCE_ENTITY_IDS = "m5dial_presence_entity_ids"
CONF_MEALIE_URL = "mealie_url"
CONF_MEALIE_TOKEN = "mealie_token"
CONF_MEALIE_ENTRY_ID = "mealie_entry_id"
CONF_GROCY_URL = "grocy_url"
CONF_GROCY_TOKEN = "grocy_token"
CONF_KITCHENOWL_URL = "kitchenowl_url"
CONF_KITCHENOWL_TOKEN = "kitchenowl_token"
CONF_KITCHENOWL_SHOPPING_LIST_ID = "kitchenowl_shopping_list_id"
CONF_SHOPPING_LIST_PROVIDER = "shopping_list_provider"
CONF_CATALOG_PROVIDER = "catalog_provider"
CONF_CATALOG_PROVIDERS = "catalog_providers"
CONF_DEV_MODE = "dev_mode"
PROVIDER_MEALIE = "mealie"
PROVIDER_GROCY = "grocy"
PROVIDER_KITCHENOWL = "kitchenowl"
PROVIDER_MOCKED = "mocked"
CATALOG_PROVIDERS = [PROVIDER_MEALIE, PROVIDER_GROCY]
SHOPPING_LIST_PROVIDER_AUTO = "auto"
SHOPPING_LIST_PROVIDERS = [SHOPPING_LIST_PROVIDER_AUTO, PROVIDER_GROCY, PROVIDER_KITCHENOWL]
# Releases before provider selection always used the built-in catalog.
DEFAULT_CATALOG_PROVIDER = PROVIDER_MOCKED

DEFAULT_UNIT = "items"
DEFAULT_M5DIAL_SERVICE_PREFIX = "m5dial_mise_en_place_assistant"
DEFAULT_M5DIAL_EVENT_SOURCE = "m5dial-mise-en-place-assistant"
DIAL_THEME_YOSHOKU_PANTRY = "yoshoku_pantry"
DIAL_THEMES = {DIAL_THEME_YOSHOKU_PANTRY: "Yoshoku Pantry"}
DEFAULT_DIAL_THEME = DIAL_THEME_YOSHOKU_PANTRY

EVENT_INVENTORY_CONFIRM = "esphome.inventory_confirm"
EVENT_MISE_EN_PLACE_ASSISTANT_SCAN = "esphome.mise_en_place_assistant_scan"
EVENT_MISE_EN_PLACE_ASSISTANT_CREATE_CONTAINER = "esphome.mise_en_place_assistant_create_container"
EVENT_MISE_EN_PLACE_ASSISTANT_UPDATE_CONTAINER = "esphome.mise_en_place_assistant_update_container"
EVENT_MISE_EN_PLACE_ASSISTANT_UPDATED = "mise_en_place_assistant.updated"

SERVICE_CREATE_CONTAINER = "create_container"
SERVICE_CREATE_RECIPE_CONTAINER = "create_recipe_container"
SERVICE_CLEAR_CONTAINER = "clear_container"
SERVICE_ARCHIVE_CONTAINER = "archive_container"
SERVICE_RESTORE_CONTAINER = "restore_container"
SERVICE_CREATE_LOCATION = "create_location"
SERVICE_UPDATE_LOCATION = "update_location"
SERVICE_DELETE_LOCATION = "delete_location"
SERVICE_MOVE_CONTAINER = "move_container"
SERVICE_FILL_CONTAINER = "fill_container"
SERVICE_REMOVE_ITEMS = "remove_items"
SERVICE_SCAN_CONTAINER = "scan_container"
SERVICE_UPDATE_CONTAINER = "update_container"
SERVICE_SIMULATE_CRUD = "simulate_crud"
SERVICE_ADD_TO_SHOPPING_LIST = "add_to_shopping_list"
SERVICE_ADD_EMPTY_CONTAINERS_TO_SHOPPING_LIST = "add_empty_containers_to_shopping_list"
SERVICE_ADD_MISSING_PRODUCTS_TO_SHOPPING_LIST = "add_missing_products_to_shopping_list"
SERVICE_UPDATE_PRODUCT_METADATA = "update_product_metadata"

SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED = "mise_en_place_assistant_entity_added"

STORAGE_KEY = DOMAIN
# Schema additions are normalized in place by `_ensure_schema`. Keep the
# established store version unless a Home Assistant migration callback is
# added; downgrading it would make records written by the previous release
# unreadable.
STORAGE_VERSION = 5

# A protected virtual location. It is deliberately not offered as a destination:
# it preserves containers when a real location is removed.
VOID_LOCATION_ID = "__void__"
VOID_LOCATION_NAME = "The Void"
LOCATION_TYPES = ["fridge", "freezer", "pantry", "dry_storage", "cellar", "counter", "other"]
PRODUCT_STORAGE_BEHAVIORS = ["fridge", "freezer", "pantry", "dry_storage", "cellar", "counter", "unknown"]
PRODUCT_CONTAINER_POLICIES = ["container", "original_packaging", "either", "no_container", "unknown"]
PRODUCT_MEAL_ROLES = ["ingredient", "staple", "condiment", "prepared_component", "ignore", "unknown"]
