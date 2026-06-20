"""Sensors that project Mise en Place Assistant workflow state into Home Assistant."""

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
    """Expose stable container and location workflow identities."""
    manager: MiseEnPlaceAssistantInventory = hass.data[DOMAIN][entry.entry_id]
    known_entities: set[str] = set()

    def container_entity(tag_id: str) -> list[MiseEnPlaceAssistantBaseSensor]:
        return [MiseEnPlaceAssistantContainerStatusSensor(manager, tag_id)]

    def location_entity(key: str) -> list[MiseEnPlaceAssistantBaseSensor]:
        return [MiseEnPlaceAssistantLocationSensor(manager, key)]

    @callback
    def add_entities(entities: list[MiseEnPlaceAssistantBaseSensor]) -> None:
        new_entities = [entity for entity in entities if entity.entity_key not in known_entities]
        if new_entities:
            known_entities.update(entity.entity_key for entity in new_entities)
            async_add_entities(new_entities)

    add_entities([MiseEnPlaceAssistantStorageAttentionSensor(manager, entry.entry_id)])
    add_entities([entity for tag_id, container in manager.containers.items() if not container.get("archived") for entity in container_entity(tag_id)])
    add_entities([entity for location in manager.storage_locations() for entity in location_entity(location["id"])])
    @callback
    def handle_entity_added(kind: str, key: str) -> None:
        if kind == "container":
            add_entities(container_entity(key))
        elif kind == "location":
            add_entities(location_entity(key))

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
        return self.manager.item_label_for_container(self.container)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        container = self.container
        return {
            "tag_id": self.tag_id,
            "product_id": container.get("product_id"),
            "item_id": container.get("item_id"),
            "item_label": container.get("item_label"),
            "item_format": container.get("item_format"),
            "content_kind": container.get("content_kind"),
            "archived": bool(container.get("archived")),
            "archived_at": container.get("archived_at"),
            "quantity": container.get("quantity", 0),
            "unit": container.get("unit"),
            "canonical_quantity": container.get("canonical_quantity", container.get("quantity", 0)),
            "canonical_unit": container.get("canonical_unit", container.get("unit")),
            "unit_dimension": container.get("unit_dimension"),
            "location": container.get("location"),
            "location_id": container.get("location_id"),
            "best_before_date": container.get("best_before_date"),
            "purchased_date": container.get("purchased_date"),
            "opened_date": container.get("opened_date"),
            "updated_at": container.get("updated_at"),
        }

    @property
    def container(self) -> dict[str, Any]:
        return self.manager.containers.get(self.tag_id, {})


class MiseEnPlaceAssistantStorageAttentionSensor(MiseEnPlaceAssistantBaseSensor):
    """Summary sensor for location and storage issues that automations can target."""

    _attr_icon = "mdi:fridge-alert"
    _attr_translation_key = "storage_attention"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: MiseEnPlaceAssistantInventory, entry_id: str) -> None:
        super().__init__(manager, "storage_attention")
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_storage_attention"

    @property
    def native_value(self) -> StateType:
        return self.summary["status"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        summary = self.summary
        return {
            "status_label": summary["status_label"],
            "attention_count": summary["attention_count"],
            "containers_needing_location_count": summary["containers_needing_location_count"],
            "unhealthy_locations_count": summary["unhealthy_locations_count"],
            "critical_locations_count": summary["critical_locations_count"],
            "warning_locations_count": summary["warning_locations_count"],
            "prepared_inventory_at_risk_count": summary["prepared_inventory_at_risk_count"],
            "containers_needing_location": summary["containers_needing_location"],
            "unhealthy_locations": summary["unhealthy_locations"],
            "critical_locations": summary["critical_locations"],
            "warning_locations": summary["warning_locations"],
            "prepared_inventory_at_risk": summary["prepared_inventory_at_risk"],
        }

    @property
    def summary(self) -> dict[str, Any]:
        return self.manager.storage_attention_summary()


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
        location = self.location
        return {
            "location_id": location.get("id"), "location": location.get("name"),
            "location_type": location.get("location_type"), "area_id": location.get("area_id"),
            "sensors": location.get("sensors", {}), "monitoring": location.get("monitoring", {}),
            "health": self.manager.location_health(location), "created_at": location.get("created_at"),
        }

    @property
    def location(self) -> dict[str, Any]:
        return self.manager.location_for_id(self.location_key) or {}
