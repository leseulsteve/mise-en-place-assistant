"""Sensors that project the local kitchen model into Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .const import DOMAIN, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED
from .store import MiseEnPlaceAssistantInventory


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Expose stable container identities and useful aggregate totals."""
    manager: MiseEnPlaceAssistantInventory = hass.data[DOMAIN][entry.entry_id]
    known_entities: set[str] = set()

    def container_entity(tag_id: str) -> list[MiseEnPlaceAssistantBaseSensor]:
        return [MiseEnPlaceAssistantContainerStatusSensor(manager, tag_id)]

    def location_entity(key: str) -> list[MiseEnPlaceAssistantBaseSensor]:
        return [MiseEnPlaceAssistantLocationSensor(manager, key)]

    def product_entity(product_id: str) -> list[MiseEnPlaceAssistantBaseSensor]:
        return [MiseEnPlaceAssistantItemTotalSensor(manager, product_id)]

    @callback
    def add_entities(entities: list[MiseEnPlaceAssistantBaseSensor]) -> None:
        new_entities = [entity for entity in entities if entity.entity_key not in known_entities]
        if new_entities:
            known_entities.update(entity.entity_key for entity in new_entities)
            async_add_entities(new_entities)

    add_entities([entity for tag_id in manager.containers for entity in container_entity(tag_id)])
    add_entities([entity for key in manager.locations for entity in location_entity(key)])
    add_entities([entity for product_id in manager.products for entity in product_entity(product_id)])

    @callback
    def handle_entity_added(kind: str, key: str) -> None:
        if kind == "container":
            add_entities(container_entity(key))
        elif kind == "location":
            add_entities(location_entity(key))
        elif kind == "product":
            add_entities(product_entity(key))

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, handle_entity_added))


class MiseEnPlaceAssistantBaseSensor(SensorEntity):
    """Base sensor that refreshes whenever local inventory changes."""

    _attr_has_entity_name = True

    def __init__(self, manager: MiseEnPlaceAssistantInventory, entity_key: str) -> None:
        self.manager = manager
        self.entity_key = entity_key
        self._unsub: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        @callback
        def update() -> None:
            self.async_write_ha_state()

        self._unsub = self.manager.async_listen(update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None


class MiseEnPlaceAssistantContainerStatusSensor(MiseEnPlaceAssistantBaseSensor):
    """A reusable container, identified permanently by its NFC tag."""

    _attr_icon = "mdi:package-variant-closed"
    _attr_translation_key = "container"

    def __init__(self, manager: MiseEnPlaceAssistantInventory, tag_id: str) -> None:
        super().__init__(manager, f"container_{tag_id}")
        self.tag_id = tag_id
        self._attr_unique_id = f"{DOMAIN}_container_{slugify(tag_id)}"

    @property
    def name(self) -> str:
        return self.container.get("name") or self.manager.default_container_name(self.tag_id)

    @property
    def native_value(self) -> StateType:
        return self.container.get("state") or "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        container = self.container
        return {
            "tag_id": self.tag_id,
            "product_id": container.get("product_id"),
            "item_id": container.get("item_id"),
            "item_label": container.get("item_label"),
            "item_format": container.get("item_format"),
            "quantity": container.get("quantity", 0),
            "unit": container.get("unit"),
            "canonical_quantity": container.get("canonical_quantity", container.get("quantity", 0)),
            "canonical_unit": container.get("canonical_unit", container.get("unit")),
            "unit_dimension": container.get("unit_dimension"),
            "location": container.get("location"),
            "updated_at": container.get("updated_at"),
        }

    @property
    def container(self) -> dict[str, Any]:
        return self.manager.containers.get(self.tag_id, {})


class MiseEnPlaceAssistantItemTotalSensor(MiseEnPlaceAssistantBaseSensor):
    """Total of an item across currently filled containers and locations."""

    _attr_icon = "mdi:food-apple"
    _attr_translation_key = "item_total"

    def __init__(self, manager: MiseEnPlaceAssistantInventory, product_id: str) -> None:
        super().__init__(manager, f"product_{product_id}_total")
        self.product_id = product_id
        self._attr_unique_id = f"{DOMAIN}_product_{slugify(product_id)}_total"

    @property
    def item(self) -> dict[str, Any]:
        return self.manager.item_totals().get(self.product_id, {})

    @property
    def name(self) -> str:
        return f"{self.item.get('label', self.product_id)} total"

    @property
    def native_value(self) -> StateType:
        return self.item.get("quantity") if self.item.get("quantity") is not None else "mixed"

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.item.get("unit")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "item_id": self.item.get("item_id"),
            "containers": self.item.get("containers", 0),
            "locations": self.item.get("locations", {}),
            "quantities_by_unit": self.item.get("quantities", {}),
        }


class MiseEnPlaceAssistantLocationSensor(MiseEnPlaceAssistantBaseSensor):
    """Number of reusable containers currently at an inventory location."""

    _attr_icon = "mdi:warehouse"
    _attr_translation_key = "location"

    def __init__(self, manager: MiseEnPlaceAssistantInventory, location_key: str) -> None:
        super().__init__(manager, f"location_{location_key}")
        self.location_key = location_key
        self._attr_unique_id = f"{DOMAIN}_location_{slugify(location_key)}"

    @property
    def name(self) -> str:
        return self.location.get("name", self.location_key)

    @property
    def native_value(self) -> StateType:
        return self.manager.location_count(self.location_key)

    @property
    def native_unit_of_measurement(self) -> str:
        return "containers"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"location": self.location.get("name"), "created_at": self.location.get("created_at")}

    @property
    def location(self) -> dict[str, Any]:
        return self.manager.locations.get(self.location_key, {})
