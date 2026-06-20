"""Config flow for the Mise en Place Assistant integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_INITIAL_LOCATIONS,
    CONF_CATALOG_PROVIDER,
    CONF_M5DIAL_SERVICE_PREFIX,
    CONF_M5DIAL_DEVICE_ID,
    CONF_M5DIAL_EVENT_SOURCE,
    CONF_MEALIE_TOKEN,
    CONF_MEALIE_ENTRY_ID,
    CONF_MEALIE_URL,
    DEFAULT_M5DIAL_EVENT_SOURCE,
    DEFAULT_M5DIAL_SERVICE_PREFIX,
    DOMAIN,
    NAME,
    PROVIDER_MEALIE,
    PROVIDER_MOCKED,
)
from .mealie import validate_mealie_url

_MEALIE_DOMAIN = "mealie"


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


def _mealie_url(value: str) -> str:
    """Validate the required Mealie base URL."""
    value = str(value).strip()
    if not value:
        raise vol.Invalid("value is required")
    try:
        return validate_mealie_url(value)
    except ValueError as err:
        raise vol.Invalid(str(err)) from err


def _optional_mealie_url(value: str) -> str:
    """Allow unused credentials when Mocked is the selected provider."""
    value = str(value).strip()
    return _mealie_url(value) if value else ""


def _required_text(value: str) -> str:
    """Reject blank required config values."""
    value = str(value).strip()
    if not value:
        raise vol.Invalid("value is required")
    return value


class MiseEnPlaceAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mise en Place Assistant."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Create the Mise en Place Assistant config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            self._entry_data = {
                CONF_INITIAL_LOCATIONS: _locations_from_text(user_input.get(CONF_INITIAL_LOCATIONS, "")),
                CONF_M5DIAL_SERVICE_PREFIX: user_input.get(
                    CONF_M5DIAL_SERVICE_PREFIX, DEFAULT_M5DIAL_SERVICE_PREFIX
                ).strip(),
                CONF_M5DIAL_DEVICE_ID: user_input.get(CONF_M5DIAL_DEVICE_ID),
                CONF_M5DIAL_EVENT_SOURCE: user_input.get(
                    CONF_M5DIAL_EVENT_SOURCE, DEFAULT_M5DIAL_EVENT_SOURCE
                ).strip(),
                CONF_CATALOG_PROVIDER: user_input[CONF_CATALOG_PROVIDER],
            }
            if self._entry_data[CONF_CATALOG_PROVIDER] != PROVIDER_MEALIE:
                return self.async_create_entry(title=NAME, data=self._entry_data)
            return await self.async_step_mealie()

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
                    vol.Required(
                        CONF_CATALOG_PROVIDER,
                        default=PROVIDER_MOCKED,
                    ): vol.In([PROVIDER_MOCKED, PROVIDER_MEALIE]),
                }
            ),
        )

    async def async_step_mealie(self, user_input: dict | None = None):
        """Reuse a configured Home Assistant Mealie entry, if one exists."""
        entries = [
            entry
            for entry in self.hass.config_entries.async_entries(_MEALIE_DOMAIN)
            if entry.data.get(CONF_HOST) and entry.data.get(CONF_API_TOKEN)
        ]
        if entries:
            if len(entries) == 1:
                self._entry_data[CONF_MEALIE_ENTRY_ID] = entries[0].entry_id
                return self.async_create_entry(title=NAME, data=self._entry_data)
            self._mealie_entries = {entry.entry_id: entry for entry in entries}
            return await self.async_step_mealie_entry()
        return await self.async_step_mealie_manual(user_input)

    async def async_step_mealie_entry(self, user_input: dict | None = None):
        """Choose a Home Assistant Mealie entry when several are configured."""
        if user_input is not None:
            self._entry_data.update(
                {
                    CONF_MEALIE_ENTRY_ID: user_input[CONF_MEALIE_ENTRY_ID],
                }
            )
            return self.async_create_entry(title=NAME, data=self._entry_data)
        return self.async_show_form(
            step_id="mealie_entry",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MEALIE_ENTRY_ID): vol.In(
                        {entry_id: entry.title for entry_id, entry in self._mealie_entries.items()}
                    ),
                }
            ),
        )

    async def async_step_mealie_manual(self, user_input: dict | None = None):
        """Collect credentials when no Home Assistant Mealie entry exists."""
        if user_input is not None:
            self._entry_data.update(
                {
                    CONF_MEALIE_URL: user_input[CONF_MEALIE_URL],
                    CONF_MEALIE_TOKEN: user_input[CONF_MEALIE_TOKEN],
                }
            )
            return self.async_create_entry(title=NAME, data=self._entry_data)
        return self.async_show_form(
            step_id="mealie_manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MEALIE_URL): _mealie_url,
                    vol.Required(CONF_MEALIE_TOKEN): _required_text,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Create the options flow."""
        return MiseEnPlaceAssistantOptionsFlow()


class MiseEnPlaceAssistantOptionsFlow(config_entries.OptionsFlow):
    """Handle Mise en Place Assistant options."""

    async def async_step_init(self, user_input: dict | None = None):
        """Manage Mise en Place Assistant options."""
        errors: dict[str, str] = {}
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
        current_mealie_url = self.config_entry.options.get(
            CONF_MEALIE_URL, self.config_entry.data.get(CONF_MEALIE_URL, "")
        )
        current_mealie_token = self.config_entry.options.get(
            CONF_MEALIE_TOKEN, self.config_entry.data.get(CONF_MEALIE_TOKEN, "")
        )
        current_provider = self.config_entry.options.get(
            CONF_CATALOG_PROVIDER,
            self.config_entry.data.get(CONF_CATALOG_PROVIDER, DEFAULT_CATALOG_PROVIDER),
        )

        if user_input is not None:
            provider = user_input[CONF_CATALOG_PROVIDER]
            try:
                if provider == PROVIDER_MEALIE:
                    _mealie_url(user_input.get(CONF_MEALIE_URL, ""))
                    _required_text(user_input.get(CONF_MEALIE_TOKEN, ""))
            except vol.Invalid:
                errors["base"] = "invalid_mealie_connection"
            else:
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
                        CONF_MEALIE_URL: user_input.get(CONF_MEALIE_URL, ""),
                        CONF_MEALIE_TOKEN: user_input.get(CONF_MEALIE_TOKEN, "").strip(),
                        CONF_CATALOG_PROVIDER: provider,
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
                    vol.Required(CONF_CATALOG_PROVIDER, default=current_provider): vol.In(CATALOG_PROVIDERS),
                    vol.Optional(CONF_MEALIE_URL, default=current_mealie_url): _optional_mealie_url,
                    vol.Optional(CONF_MEALIE_TOKEN, default=current_mealie_token): str,
                }
            ),
            errors=errors,
        )
