"""Constants for the Mise en Place Assistant integration."""

from __future__ import annotations

DOMAIN = "mise_en_place_assistant"
NAME = "Mise en Place Assistant"

PLATFORMS = ["sensor"]
PANEL_URL_PATH = "mise_en_place_assistant"

CONF_INITIAL_LOCATIONS = "initial_locations"
CONF_M5DIAL_SERVICE_PREFIX = "m5dial_service_prefix"
CONF_M5DIAL_DEVICE_ID = "m5dial_device_id"
CONF_M5DIAL_EVENT_SOURCE = "m5dial_event_source"

CONTAINER_STATE_FILLED = "filled"
CONTAINER_STATE_EMPTY = "empty"
CONTAINER_STATE_DIRTY = "dirty"
CONTAINER_STATE_CLEAN = "clean"
CONTAINER_STATE_STORED = "stored"
DEFAULT_STATES = [
    CONTAINER_STATE_FILLED,
    CONTAINER_STATE_EMPTY,
    CONTAINER_STATE_DIRTY,
    CONTAINER_STATE_CLEAN,
    CONTAINER_STATE_STORED,
]
DEFAULT_UNIT = "items"
DEFAULT_M5DIAL_SERVICE_PREFIX = "m5dial_mise_en_place_assistant"
DEFAULT_M5DIAL_EVENT_SOURCE = "m5dial-mise-en-place-assistant"

MOCK_ITEMS = [
    {
        "id": "chicken_breast",
        "label": "Chicken breast",
        "format": "Vacuum pack",
        "unit": "pieces",
    },
    {
        "id": "beef_stew",
        "label": "Beef stew",
        "format": "1 L container",
        "unit": "servings",
    },
    {
        "id": "tomato_sauce",
        "label": "Tomato sauce",
        "format": "500 ml jar",
        "unit": "jars",
    },
    {
        "id": "berries",
        "label": "Mixed berries",
        "format": "Freezer bag",
        "unit": "cups",
    },
]

MOCK_LOCATIONS = ["Freezer", "Fridge", "Pantry", "Prep shelf"]

EVENT_INVENTORY_CONFIRM = "esphome.inventory_confirm"
EVENT_MISE_EN_PLACE_ASSISTANT_SCAN = "esphome.mise_en_place_assistant_scan"
EVENT_MISE_EN_PLACE_ASSISTANT_CREATE_CONTAINER = "esphome.mise_en_place_assistant_create_container"
EVENT_MISE_EN_PLACE_ASSISTANT_UPDATE_CONTAINER = "esphome.mise_en_place_assistant_update_container"
EVENT_MISE_EN_PLACE_ASSISTANT_MARK_CLEAN = "esphome.mise_en_place_assistant_mark_clean"
EVENT_MISE_EN_PLACE_ASSISTANT_UPDATED = "mise_en_place_assistant.updated"

SERVICE_CREATE_CONTAINER = "create_container"
SERVICE_CREATE_LOCATION = "create_location"
SERVICE_FILL_CONTAINER = "fill_container"
SERVICE_MOCK_API = "mock_api"
SERVICE_REMOVE_ITEMS = "remove_items"
SERVICE_SCAN_CONTAINER = "scan_container"
SERVICE_UPDATE_CONTAINER = "update_container"
SERVICE_MARK_CONTAINER_CLEAN = "mark_container_clean"

SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED = "mise_en_place_assistant_entity_added"

STORAGE_KEY = DOMAIN
# New fields are additive and normalized on load; keep existing inventory readable.
STORAGE_VERSION = 1
