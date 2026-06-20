"""Home Assistant configuration entities for the M5Dial."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DIAL_THEMES, DOMAIN
from .store import MiseEnPlaceAssistantInventory


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Expose the Dial's theme selector in Home Assistant."""
    manager: MiseEnPlaceAssistantInventory = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MiseEnPlaceAssistantDialThemeSelect(manager, entry)])


class MiseEnPlaceAssistantDialThemeSelect(SelectEntity):
    """Select the presentation applied by the enrolled M5Dial."""

    _attr_has_entity_name = True
    _attr_name = "Dial theme"
    _attr_icon = "mdi:palette-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(DIAL_THEMES.values())

    def __init__(self, manager: MiseEnPlaceAssistantInventory, entry: ConfigEntry) -> None:
        self.manager = manager
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_dial_theme"

    @property
    def current_option(self) -> str:
        return DIAL_THEMES[self.manager.dial_theme]

    async def async_select_option(self, option: str) -> None:
        for theme, label in DIAL_THEMES.items():
            if label == option:
                await self.manager.async_set_dial_theme(theme)
                self.async_write_ha_state()
                return
        raise ValueError(f"Unsupported Dial theme: {option}")
