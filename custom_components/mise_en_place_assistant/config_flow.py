"""Config flow for the Mise en Place Assistant integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CATALOG_PROVIDERS,
    CONF_INITIAL_LOCATIONS,
    CONF_CATALOG_PROVIDER,
    CONF_CATALOG_PROVIDERS,
    CONF_DEV_MODE,
    CONF_GROCY_TOKEN,
    CONF_GROCY_URL,
    CONF_KITCHENOWL_SHOPPING_LIST_ID,
    CONF_KITCHENOWL_TOKEN,
    CONF_KITCHENOWL_URL,
    CONF_M5DIAL_SERVICE_PREFIX,
    CONF_M5DIAL_DEVICE_ID,
    CONF_M5DIAL_EVENT_SOURCE,
    CONF_MEALIE_TOKEN,
    CONF_MEALIE_ENTRY_ID,
    CONF_MEALIE_URL,
    CONF_SHOPPING_LIST_PROVIDER,
    DEFAULT_CATALOG_PROVIDER,
    DEFAULT_M5DIAL_EVENT_SOURCE,
    DEFAULT_M5DIAL_SERVICE_PREFIX,
    DOMAIN,
    NAME,
    PROVIDER_GROCY,
    PROVIDER_KITCHENOWL,
    PROVIDER_MEALIE,
    PROVIDER_MOCKED,
    SHOPPING_LIST_PROVIDER_AUTO,
    SHOPPING_LIST_PROVIDERS,
)
from .grocy import validate_grocy_url
from .kitchenowl import validate_kitchenowl_url
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
    """Allow unused credentials when Mealie is not one of the selected providers."""
    value = str(value).strip()
    return _mealie_url(value) if value else ""


def _grocy_url(value: str) -> str:
    """Validate the required Grocy base URL."""
    value = str(value).strip()
    if not value:
        raise vol.Invalid("value is required")
    try:
        return validate_grocy_url(value)
    except ValueError as err:
        raise vol.Invalid(str(err)) from err


def _optional_grocy_url(value: str) -> str:
    """Allow unused credentials when Grocy is not one of the selected providers."""
    value = str(value).strip()
    return _grocy_url(value) if value else ""


def _kitchenowl_url(value: str) -> str:
    """Validate the required KitchenOwl base URL."""
    value = str(value).strip()
    if not value:
        raise vol.Invalid("value is required")
    try:
        return validate_kitchenowl_url(value)
    except ValueError as err:
        raise vol.Invalid(str(err)) from err


def _optional_kitchenowl_url(value: str) -> str:
    """Allow unused credentials only when DEV mode uses mock data."""
    value = str(value).strip()
    return _kitchenowl_url(value) if value else ""


def _positive_int(value) -> int:
    """Validate a positive integer config value."""
    try:
        number = int(value)
    except (TypeError, ValueError) as err:
        raise vol.Invalid("value must be a positive integer") from err
    if number <= 0:
        raise vol.Invalid("value must be a positive integer")
    return number


def _optional_positive_int(value) -> int | None:
    """Allow an omitted positive integer only in DEV mode."""
    if value in (None, ""):
        return None
    return _positive_int(value)


def _catalog_providers(value) -> list[str]:
    """Normalize live provider selection to a unique list."""
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    providers: list[str] = []
    for provider in values:
        if provider == PROVIDER_MOCKED:
            continue
        if provider not in CATALOG_PROVIDERS:
            raise vol.Invalid("unsupported catalog provider")
        if provider not in providers:
            providers.append(provider)
    return providers


def _dev_mode(value) -> bool:
    """Normalize the developer fallback switch."""
    return bool(value)


def _validate_provider_choice(providers: list[str], dev_mode: bool) -> None:
    """Require the complete live provider stack unless DEV mode allows mocks."""
    if dev_mode:
        return
    if set(providers) != set(CATALOG_PROVIDERS):
        raise vol.Invalid("all data providers are required outside DEV mode")


def _validate_kitchenowl_config(user_input: dict, dev_mode: bool) -> None:
    """Validate KitchenOwl settings when the user configures that shopping target."""
    if not any(
        user_input.get(key)
        for key in (CONF_KITCHENOWL_URL, CONF_KITCHENOWL_TOKEN, CONF_KITCHENOWL_SHOPPING_LIST_ID)
    ):
        if user_input.get(CONF_SHOPPING_LIST_PROVIDER, SHOPPING_LIST_PROVIDER_AUTO) == PROVIDER_KITCHENOWL:
            raise vol.Invalid("KitchenOwl settings are required when KitchenOwl owns shopping lists")
        return
    _kitchenowl_url(user_input.get(CONF_KITCHENOWL_URL, ""))
    _required_text(user_input.get(CONF_KITCHENOWL_TOKEN, ""))
    _positive_int(user_input.get(CONF_KITCHENOWL_SHOPPING_LIST_ID))


def _provider_selector():
    """Return a multi-provider selector for config and options flows."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=CATALOG_PROVIDERS,
            multiple=True,
        )
    )


def _shopping_provider_selector():
    """Return shopping-list target selector."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=SHOPPING_LIST_PROVIDERS,
        )
    )


def _optional_device_field(default: str | None = None):
    """Return a device selector field without serializing a None default."""
    kwargs = {"default": default} if default else {}
    return vol.Optional(CONF_M5DIAL_DEVICE_ID, **kwargs)


def _optional_kitchenowl_list_field(default: int | None = None):
    """Return the KitchenOwl list field without serializing a None default."""
    kwargs = {"default": default} if default is not None else {}
    return vol.Optional(CONF_KITCHENOWL_SHOPPING_LIST_ID, **kwargs)


def _needs_mealie(providers: list[str]) -> bool:
    return PROVIDER_MEALIE in providers


def _needs_grocy(providers: list[str]) -> bool:
    return PROVIDER_GROCY in providers


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
            dev_mode = _dev_mode(user_input.get(CONF_DEV_MODE, False))
            providers = [] if dev_mode else _catalog_providers(user_input[CONF_CATALOG_PROVIDERS])
            try:
                _validate_provider_choice(providers, dev_mode)
                _validate_kitchenowl_config(user_input, dev_mode)
            except vol.Invalid:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_schema(user_input),
                    errors={"base": "provider_required" if not dev_mode and set(providers) != set(CATALOG_PROVIDERS) else "invalid_provider_connection"},
                )
            self._entry_data = {
                CONF_INITIAL_LOCATIONS: _locations_from_text(user_input.get(CONF_INITIAL_LOCATIONS, "")),
                CONF_M5DIAL_SERVICE_PREFIX: user_input.get(
                    CONF_M5DIAL_SERVICE_PREFIX, DEFAULT_M5DIAL_SERVICE_PREFIX
                ).strip(),
                CONF_M5DIAL_DEVICE_ID: user_input.get(CONF_M5DIAL_DEVICE_ID),
                CONF_M5DIAL_EVENT_SOURCE: user_input.get(
                    CONF_M5DIAL_EVENT_SOURCE, DEFAULT_M5DIAL_EVENT_SOURCE
                ).strip(),
                CONF_CATALOG_PROVIDERS: providers,
                CONF_DEV_MODE: dev_mode,
                CONF_SHOPPING_LIST_PROVIDER: user_input.get(
                    CONF_SHOPPING_LIST_PROVIDER, SHOPPING_LIST_PROVIDER_AUTO
                ),
                CONF_KITCHENOWL_URL: user_input.get(CONF_KITCHENOWL_URL, ""),
                CONF_KITCHENOWL_TOKEN: user_input.get(CONF_KITCHENOWL_TOKEN, "").strip(),
                CONF_KITCHENOWL_SHOPPING_LIST_ID: user_input.get(CONF_KITCHENOWL_SHOPPING_LIST_ID),
            }
            self._entry_data[CONF_CATALOG_PROVIDER] = providers[0] if providers else ""
            if _needs_mealie(self._entry_data[CONF_CATALOG_PROVIDERS]):
                return await self.async_step_mealie()
            if _needs_grocy(self._entry_data[CONF_CATALOG_PROVIDERS]):
                return await self.async_step_grocy_manual()
            else:
                return self.async_create_entry(title=NAME, data=self._entry_data)

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_schema(),
        )

    def _user_schema(self, user_input: dict | None = None) -> vol.Schema:
        """Return the setup form schema."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_INITIAL_LOCATIONS,
                    default=(user_input or {}).get(CONF_INITIAL_LOCATIONS, "Pantry, Freezer, Fridge"),
                ): str,
                vol.Optional(
                    CONF_M5DIAL_SERVICE_PREFIX,
                    default=(user_input or {}).get(CONF_M5DIAL_SERVICE_PREFIX, DEFAULT_M5DIAL_SERVICE_PREFIX),
                ): str,
                _optional_device_field((user_input or {}).get(CONF_M5DIAL_DEVICE_ID)): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(integration="esphome")
                ),
                vol.Optional(
                    CONF_M5DIAL_EVENT_SOURCE,
                    default=(user_input or {}).get(CONF_M5DIAL_EVENT_SOURCE, DEFAULT_M5DIAL_EVENT_SOURCE),
                ): str,
                vol.Required(
                    CONF_CATALOG_PROVIDERS,
                    default=(user_input or {}).get(CONF_CATALOG_PROVIDERS, CATALOG_PROVIDERS),
                ): _provider_selector(),
                vol.Optional(CONF_DEV_MODE, default=(user_input or {}).get(CONF_DEV_MODE, False)): selector.BooleanSelector(),
                vol.Optional(
                    CONF_SHOPPING_LIST_PROVIDER,
                    default=(user_input or {}).get(CONF_SHOPPING_LIST_PROVIDER, SHOPPING_LIST_PROVIDER_AUTO),
                ): _shopping_provider_selector(),
                vol.Optional(
                    CONF_KITCHENOWL_URL,
                    default=(user_input or {}).get(CONF_KITCHENOWL_URL, ""),
                ): _optional_kitchenowl_url,
                vol.Optional(
                    CONF_KITCHENOWL_TOKEN,
                    default=(user_input or {}).get(CONF_KITCHENOWL_TOKEN, ""),
                ): str,
                _optional_kitchenowl_list_field(
                    (user_input or {}).get(CONF_KITCHENOWL_SHOPPING_LIST_ID)
                ): _optional_positive_int,
            }
        )

    def _finish_or_continue_provider_setup(self):
        """Continue provider credential collection or create the entry."""
        if _needs_grocy(self._entry_data[CONF_CATALOG_PROVIDERS]) and CONF_GROCY_URL not in self._entry_data:
            return self.async_show_form(
                step_id="grocy_manual",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_GROCY_URL): _grocy_url,
                        vol.Required(CONF_GROCY_TOKEN): _required_text,
                    }
                ),
            )
        return self.async_create_entry(title=NAME, data=self._entry_data)

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
                return self._finish_or_continue_provider_setup()
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
            return self._finish_or_continue_provider_setup()
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
            return self._finish_or_continue_provider_setup()
        return self.async_show_form(
            step_id="mealie_manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MEALIE_URL): _mealie_url,
                    vol.Required(CONF_MEALIE_TOKEN): _required_text,
                }
            ),
        )

    async def async_step_grocy_manual(self, user_input: dict | None = None):
        """Collect Grocy API credentials."""
        if user_input is not None:
            self._entry_data.update(
                {
                    CONF_GROCY_URL: user_input[CONF_GROCY_URL],
                    CONF_GROCY_TOKEN: user_input[CONF_GROCY_TOKEN],
                }
            )
            return self.async_create_entry(title=NAME, data=self._entry_data)
        return self._finish_or_continue_provider_setup()

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
        current_grocy_url = self.config_entry.options.get(
            CONF_GROCY_URL, self.config_entry.data.get(CONF_GROCY_URL, "")
        )
        current_grocy_token = self.config_entry.options.get(
            CONF_GROCY_TOKEN, self.config_entry.data.get(CONF_GROCY_TOKEN, "")
        )
        current_kitchenowl_url = self.config_entry.options.get(
            CONF_KITCHENOWL_URL, self.config_entry.data.get(CONF_KITCHENOWL_URL, "")
        )
        current_kitchenowl_token = self.config_entry.options.get(
            CONF_KITCHENOWL_TOKEN, self.config_entry.data.get(CONF_KITCHENOWL_TOKEN, "")
        )
        current_kitchenowl_list_id = self.config_entry.options.get(
            CONF_KITCHENOWL_SHOPPING_LIST_ID,
            self.config_entry.data.get(CONF_KITCHENOWL_SHOPPING_LIST_ID),
        )
        current_shopping_provider = self.config_entry.options.get(
            CONF_SHOPPING_LIST_PROVIDER,
            self.config_entry.data.get(CONF_SHOPPING_LIST_PROVIDER, SHOPPING_LIST_PROVIDER_AUTO),
        )
        current_dev_mode = self.config_entry.options.get(
            CONF_DEV_MODE,
            self.config_entry.data.get(CONF_DEV_MODE, False)
            or self.config_entry.data.get(CONF_CATALOG_PROVIDER) == PROVIDER_MOCKED,
        )
        current_providers = self.config_entry.options.get(
            CONF_CATALOG_PROVIDERS,
            self.config_entry.data.get(
                CONF_CATALOG_PROVIDERS,
                [self.config_entry.data.get(CONF_CATALOG_PROVIDER, DEFAULT_CATALOG_PROVIDER)],
            ),
        )
        current_providers = [] if current_dev_mode else _catalog_providers(current_providers)

        if user_input is not None:
            dev_mode = _dev_mode(user_input.get(CONF_DEV_MODE, False))
            providers = [] if dev_mode else _catalog_providers(user_input[CONF_CATALOG_PROVIDERS])
            try:
                _validate_provider_choice(providers, dev_mode)
                if _needs_mealie(providers):
                    _mealie_url(user_input.get(CONF_MEALIE_URL, ""))
                    _required_text(user_input.get(CONF_MEALIE_TOKEN, ""))
                if _needs_grocy(providers):
                    _grocy_url(user_input.get(CONF_GROCY_URL, ""))
                    _required_text(user_input.get(CONF_GROCY_TOKEN, ""))
                _validate_kitchenowl_config(user_input, dev_mode)
            except vol.Invalid:
                errors["base"] = "provider_required" if not dev_mode and set(providers) != set(CATALOG_PROVIDERS) else "invalid_provider_connection"
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
                        CONF_GROCY_URL: user_input.get(CONF_GROCY_URL, ""),
                        CONF_GROCY_TOKEN: user_input.get(CONF_GROCY_TOKEN, "").strip(),
                        CONF_SHOPPING_LIST_PROVIDER: user_input.get(
                            CONF_SHOPPING_LIST_PROVIDER, SHOPPING_LIST_PROVIDER_AUTO
                        ),
                        CONF_KITCHENOWL_URL: user_input.get(CONF_KITCHENOWL_URL, ""),
                        CONF_KITCHENOWL_TOKEN: user_input.get(CONF_KITCHENOWL_TOKEN, "").strip(),
                        CONF_KITCHENOWL_SHOPPING_LIST_ID: user_input.get(CONF_KITCHENOWL_SHOPPING_LIST_ID),
                        CONF_CATALOG_PROVIDERS: providers,
                        CONF_CATALOG_PROVIDER: providers[0] if providers else "",
                        CONF_DEV_MODE: dev_mode,
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
                    _optional_device_field(current_m5dial): selector.DeviceSelector(
                        selector.DeviceSelectorConfig(integration="esphome")
                    ),
                    vol.Optional(
                        CONF_M5DIAL_EVENT_SOURCE,
                        default=current_source,
                    ): str,
                    vol.Required(CONF_CATALOG_PROVIDERS, default=current_providers): _provider_selector(),
                    vol.Optional(CONF_DEV_MODE, default=current_dev_mode): selector.BooleanSelector(),
                    vol.Optional(CONF_MEALIE_URL, default=current_mealie_url): _optional_mealie_url,
                    vol.Optional(CONF_MEALIE_TOKEN, default=current_mealie_token): str,
                    vol.Optional(CONF_GROCY_URL, default=current_grocy_url): _optional_grocy_url,
                    vol.Optional(CONF_GROCY_TOKEN, default=current_grocy_token): str,
                    vol.Optional(CONF_SHOPPING_LIST_PROVIDER, default=current_shopping_provider): _shopping_provider_selector(),
                    vol.Optional(CONF_KITCHENOWL_URL, default=current_kitchenowl_url): _optional_kitchenowl_url,
                    vol.Optional(CONF_KITCHENOWL_TOKEN, default=current_kitchenowl_token): str,
                    _optional_kitchenowl_list_field(current_kitchenowl_list_id): _optional_positive_int,
                }
            ),
            errors=errors,
        )
