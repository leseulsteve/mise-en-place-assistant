"""Config flow for the Mise en Place Assistant integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_INITIAL_LOCATIONS,
    CONF_M5DIAL_SERVICE_PREFIX,
    CONF_M5DIAL_DEVICE_ID,
    CONF_M5DIAL_EVENT_SOURCE,
    DEFAULT_M5DIAL_EVENT_SOURCE,
    DEFAULT_M5DIAL_SERVICE_PREFIX,
    DOMAIN,
    NAME,
)


def _locations_from_text(value: str) -> list[str]:
    """Convert a comma-separated text value to unique location names."""
    locations: list[str] = []
    seen: set[str] = set()
    for raw_location in value.split(","):
        location = raw_location.strip()
        key = location.casefold()
        if location and key not in seen:
            seen.add(key)
            locations.append(location)
    return locations


class MiseEnPlaceAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mise en Place Assistant."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Create the Mise en Place Assistant config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data={
                    CONF_INITIAL_LOCATIONS: _locations_from_text(
                        user_input.get(CONF_INITIAL_LOCATIONS, "")
                    ),
                    CONF_M5DIAL_SERVICE_PREFIX: user_input.get(
                        CONF_M5DIAL_SERVICE_PREFIX, DEFAULT_M5DIAL_SERVICE_PREFIX
                    ).strip(),
                    CONF_M5DIAL_DEVICE_ID: user_input.get(CONF_M5DIAL_DEVICE_ID),
                    CONF_M5DIAL_EVENT_SOURCE: user_input.get(
                        CONF_M5DIAL_EVENT_SOURCE, DEFAULT_M5DIAL_EVENT_SOURCE
                    ).strip(),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INITIAL_LOCATIONS,
                        default="Pantry, Freezer, Fridge",
                    ): str,
                    vol.Optional(
                        CONF_M5DIAL_SERVICE_PREFIX,
                        default=DEFAULT_M5DIAL_SERVICE_PREFIX,
                    ): str,
                    vol.Optional(CONF_M5DIAL_DEVICE_ID): selector.DeviceSelector(
                        selector.DeviceSelectorConfig(integration="esphome")
                    ),
                    vol.Optional(
                        CONF_M5DIAL_EVENT_SOURCE,
                        default=DEFAULT_M5DIAL_EVENT_SOURCE,
                    ): str,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Create the options flow."""
        return MiseEnPlaceAssistantOptionsFlow(config_entry)


class MiseEnPlaceAssistantOptionsFlow(config_entries.OptionsFlow):
    """Handle Mise en Place Assistant options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None):
        """Manage Mise en Place Assistant options."""
        current_locations = ", ".join(
            self.config_entry.options.get(
                CONF_INITIAL_LOCATIONS,
                self.config_entry.data.get(CONF_INITIAL_LOCATIONS, []),
            )
        )
        current_prefix = self.config_entry.options.get(
            CONF_M5DIAL_SERVICE_PREFIX,
            self.config_entry.data.get(
                CONF_M5DIAL_SERVICE_PREFIX, DEFAULT_M5DIAL_SERVICE_PREFIX
            ),
        )
        current_m5dial = self.config_entry.options.get(
            CONF_M5DIAL_DEVICE_ID,
            self.config_entry.data.get(CONF_M5DIAL_DEVICE_ID),
        )
        current_source = self.config_entry.options.get(
            CONF_M5DIAL_EVENT_SOURCE,
            self.config_entry.data.get(
                CONF_M5DIAL_EVENT_SOURCE, DEFAULT_M5DIAL_EVENT_SOURCE
            ),
        )

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_INITIAL_LOCATIONS: _locations_from_text(
                        user_input.get(CONF_INITIAL_LOCATIONS, "")
                    ),
                    CONF_M5DIAL_SERVICE_PREFIX: user_input.get(
                        CONF_M5DIAL_SERVICE_PREFIX, DEFAULT_M5DIAL_SERVICE_PREFIX
                    ).strip(),
                    CONF_M5DIAL_DEVICE_ID: user_input.get(CONF_M5DIAL_DEVICE_ID),
                    CONF_M5DIAL_EVENT_SOURCE: user_input.get(
                        CONF_M5DIAL_EVENT_SOURCE, DEFAULT_M5DIAL_EVENT_SOURCE
                    ).strip(),
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INITIAL_LOCATIONS,
                        default=current_locations,
                    ): str,
                    vol.Optional(
                        CONF_M5DIAL_SERVICE_PREFIX,
                        default=current_prefix,
                    ): str,
                    vol.Optional(
                        CONF_M5DIAL_DEVICE_ID,
                        default=current_m5dial,
                    ): selector.DeviceSelector(
                        selector.DeviceSelectorConfig(integration="esphome")
                    ),
                    vol.Optional(
                        CONF_M5DIAL_EVENT_SOURCE,
                        default=current_source,
                    ): str,
                }
            ),
        )
