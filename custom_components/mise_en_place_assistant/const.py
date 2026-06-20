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
CONF_MEALIE_URL = "mealie_url"
CONF_MEALIE_TOKEN = "mealie_token"
CONF_MEALIE_ENTRY_ID = "mealie_entry_id"
CONF_CATALOG_PROVIDER = "catalog_provider"
PROVIDER_MEALIE = "mealie"
PROVIDER_MOCKED = "mocked"
CATALOG_PROVIDERS = [PROVIDER_MEALIE, PROVIDER_MOCKED]
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
SERVICE_CREATE_LOCATION = "create_location"
SERVICE_FILL_CONTAINER = "fill_container"
SERVICE_REMOVE_ITEMS = "remove_items"
SERVICE_SCAN_CONTAINER = "scan_container"
SERVICE_UPDATE_CONTAINER = "update_container"

SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED = "mise_en_place_assistant_entity_added"

STORAGE_KEY = DOMAIN
# Schema additions are normalized in place by `_ensure_schema`. Keep the
# established store version unless a Home Assistant migration callback is
# added; downgrading it would make records written by the previous release
# unreadable.
STORAGE_VERSION = 5
