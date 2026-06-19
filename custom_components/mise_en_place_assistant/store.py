"""Persistent kitchen inventory model for Mise en Place Assistant."""

from __future__ import annotations

import logging

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

from .const import (
    CONTAINER_STATE_CLEAN,
    CONTAINER_STATE_DIRTY,
    CONTAINER_STATE_EMPTY,
    CONTAINER_STATE_FILLED,
    DEFAULT_UNIT,
    DOMAIN,
    EVENT_MISE_EN_PLACE_ASSISTANT_UPDATED,
    MOCK_ITEMS,
    MOCK_LOCATIONS,
    SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class MiseEnPlaceAssistantInventory:
    """Manage the local, authoritative Mise en Place inventory."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.data: dict[str, Any] = {
            "items": {},
            "containers": {},
            "locations": {},
            "logbook": [],
            "devices": {},
        }
        self._listeners: list[Callable[[], None]] = []

    async def async_load(self) -> None:
        """Load data and upgrade the former inventory shape in place."""
        stored = await self._store.async_load()
        if stored:
            self.data = stored
        changed = self._ensure_schema()

        configured_locations = self.entry.options.get(
            "initial_locations", self.entry.data.get("initial_locations", [])
        )
        for location in configured_locations:
            location_count = len(self.locations)
            self.ensure_location(location, save=False)
            changed = len(self.locations) != location_count or changed

        m5dial_device_id = self.entry.options.get(
            "m5dial_device_id", self.entry.data.get("m5dial_device_id")
        )
        if m5dial_device_id and self.devices.get("m5dial", {}).get("device_id") != m5dial_device_id:
            self.devices["m5dial"] = {
                "device_id": m5dial_device_id,
                "role": "primary_inventory_controller",
                "enrolled_at": _utc_now(),
            }
            changed = True

        if changed:
            await self.async_save(notify=False)
        _LOGGER.info(
            "Loaded Mise en Place inventory: containers=%d locations=%d",
            len(self.containers),
            len(self.locations),
        )

    def _ensure_schema(self) -> bool:
        """Ensure old Mise en Place Assistant data remains usable by the reusable-container model."""
        changed = False
        for key, default in (("items", {}), ("containers", {}), ("locations", {}), ("logbook", []), ("devices", {})):
            if key not in self.data:
                self.data[key] = default
                changed = True

        for tag_id, container in self.containers.items():
            if not container.get("tag_id"):
                container["tag_id"] = tag_id
                changed = True
            if not container.get("name"):
                container["name"] = self.default_container_name(tag_id)
                changed = True
            if not container.get("state") or container.get("state") == "unknown":
                container["state"] = (
                    CONTAINER_STATE_FILLED
                    if int(container.get("quantity", 0)) > 0
                    else CONTAINER_STATE_EMPTY
                )
                changed = True
            if "created_at" not in container:
                container["created_at"] = _utc_now()
                changed = True
            if "updated_at" not in container:
                container["updated_at"] = container["created_at"]
                changed = True
            if container.get("item_id") or container.get("item_label"):
                changed = self._remember_item(
                    container.get("item_id"),
                    container.get("item_label"),
                    container.get("item_format"),
                    container.get("unit"),
                ) or changed
        for item in MOCK_ITEMS:
            changed = self._remember_item(
                item["id"], item["label"], item.get("format"), item.get("unit")
            ) or changed
        return changed

    @property
    def containers(self) -> dict[str, dict[str, Any]]:
        return self.data.setdefault("containers", {})

    @property
    def items(self) -> dict[str, dict[str, Any]]:
        return self.data.setdefault("items", {})

    @property
    def locations(self) -> dict[str, dict[str, Any]]:
        return self.data.setdefault("locations", {})

    @property
    def logbook(self) -> list[dict[str, Any]]:
        return self.data.setdefault("logbook", [])

    @property
    def devices(self) -> dict[str, dict[str, Any]]:
        return self.data.setdefault("devices", {})

    def default_container_name(self, tag_id: str) -> str:
        """Return a stable, contents-independent container label."""
        compact = "".join(character for character in tag_id if character.isalnum())
        return f"Container {compact[-6:].upper() or 'untagged'}"

    def mock_api_payload(self) -> dict[str, Any]:
        locations = [location["name"] for location in self.locations.values()] or MOCK_LOCATIONS
        return {"items": MOCK_ITEMS, "locations": locations}

    def get_container(self, tag_id: str) -> dict[str, Any] | None:
        return self.containers.get(self._normalize_tag_id(tag_id))

    @callback
    def async_listen(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            self._listeners.remove(listener)

        return unsubscribe

    def ensure_location(self, name: str | None, *, save: bool = False) -> str | None:
        if not (name := self._normalize_optional(name)):
            return None
        key = name.casefold()
        if key in self.locations:
            return self.locations[key]["name"]
        self.locations[key] = {"name": name, "created_at": _utc_now()}
        self._add_log_entry("Location created", f"{name} was added as an inventory location.", {"location": name})
        async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "location", key)
        if save:
            self.hass.async_create_task(self.async_save())
        return name

    async def async_create_location(self, name: str) -> None:
        before = len(self.locations)
        self.ensure_location(name)
        if len(self.locations) != before:
            await self.async_save()

    def enrolled_m5dial(self) -> dict[str, Any] | None:
        """Return the Home Assistant device selected as the M5Dial, if any."""
        return self.devices.get("m5dial")

    async def async_create_container(
        self,
        *,
        tag_id: str,
        name: str | None = None,
        quantity: int = 0,
        location: str | None = None,
        state: str | None = None,
        unit: str = DEFAULT_UNIT,
        item_id: str | None = None,
        item_label: str | None = None,
        item_format: str | None = None,
    ) -> None:
        tag_id = self._normalize_tag_id(tag_id)
        old = self.containers.get(tag_id, {})
        quantity = max(0, int(quantity))
        location = self.ensure_location(location)
        now = _utc_now()
        is_new = not old
        chosen_state = (
            state
            if state and state != "unknown"
            else (CONTAINER_STATE_FILLED if quantity else CONTAINER_STATE_EMPTY)
        )
        self.containers[tag_id] = {
            "tag_id": tag_id,
            "name": self._normalize_optional(name) or old.get("name") or self.default_container_name(tag_id),
            "item_id": item_id,
            "item_label": item_label,
            "item_format": item_format,
            "quantity": quantity,
            "location": location,
            "state": chosen_state,
            "unit": unit or DEFAULT_UNIT,
            "created_at": old.get("created_at", now),
            "updated_at": now,
        }
        if is_new:
            async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "container", tag_id)
        if item_id or item_label:
            self._remember_item(item_id, item_label, item_format, unit)
            async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "item", self.item_key(item_id, item_label))
        self._add_log_entry(
            "Container created" if is_new else "Container refilled",
            f"{self.containers[tag_id]['name']} is {chosen_state} in {location or 'no location'}.",
            {"tag_id": tag_id, "quantity": quantity, "location": location, "state": chosen_state},
        )
        await self.async_save()

    async def async_update_container(
        self,
        *,
        tag_id: str,
        quantity: int | None = None,
        delta: int | None = None,
        location: str | None = None,
        state: str | None = None,
        name: str | None = None,
        unit: str | None = None,
        item_id: str | None = None,
        item_label: str | None = None,
        item_format: str | None = None,
        create_missing: bool = False,
    ) -> None:
        tag_id = self._normalize_tag_id(tag_id)
        if tag_id not in self.containers:
            if not create_missing:
                raise KeyError(tag_id)
            await self.async_create_container(tag_id=tag_id)

        container = self.containers[tag_id]
        before = dict(container)
        quantity_changed = quantity is not None or delta is not None
        if quantity is not None:
            container["quantity"] = max(0, int(quantity))
        if delta is not None:
            container["quantity"] = max(0, int(container.get("quantity", 0)) + int(delta))
        if location is not None:
            container["location"] = self.ensure_location(location)
        if state is not None:
            container["state"] = state
        elif quantity_changed:
            # A container that has just been consumed is physically empty and
            # needs washing before it can return to clean storage.
            container["state"] = (
                CONTAINER_STATE_FILLED
                if container["quantity"]
                else CONTAINER_STATE_DIRTY
            )
        if name is not None:
            container["name"] = self._normalize_optional(name) or self.default_container_name(tag_id)
        if unit is not None:
            container["unit"] = unit or DEFAULT_UNIT
        if item_id is not None:
            container["item_id"] = item_id
        if item_label is not None:
            container["item_label"] = item_label
        if item_format is not None:
            container["item_format"] = item_format
        container["updated_at"] = _utc_now()
        if container.get("item_id") or container.get("item_label"):
            self._remember_item(
                container.get("item_id"), container.get("item_label"),
                container.get("item_format"), container.get("unit"),
            )
            async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "item", self.item_key(container.get("item_id"), container.get("item_label")))
        self._add_log_entry(
            "Container updated",
            f"{container['name']} changed from {before.get('state')} to {container.get('state')}.",
            {"tag_id": tag_id, "old_quantity": before.get("quantity"), "quantity": container.get("quantity"), "old_state": before.get("state"), "state": container.get("state")},
        )
        await self.async_save()

    async def async_mark_container_clean(self, tag_id: str, *, location: str | None = None) -> None:
        """Record the post-wash NFC scan; the container no longer has contents."""
        tag_id = self._normalize_tag_id(tag_id)
        if tag_id not in self.containers:
            raise KeyError(tag_id)
        container = self.containers[tag_id]
        previous_item = container.get("item_label")
        if location is not None:
            container["location"] = self.ensure_location(location)
        container.update({
            "item_id": None,
            "item_label": None,
            "item_format": None,
            "quantity": 0,
            "state": CONTAINER_STATE_CLEAN,
            "updated_at": _utc_now(),
        })
        self._add_log_entry(
            "Container washed",
            f"{container['name']} was scanned clean and is ready for storage.",
            {"tag_id": tag_id, "previous_item": previous_item, "location": container.get("location")},
        )
        await self.async_save()

    async def async_scan_container(self, *, tag_id: str, quantity: int | None = None, mode: str = "set") -> None:
        delta = int(quantity) if quantity is not None and mode == "add" else None
        if quantity is not None and mode == "remove":
            delta = -int(quantity)
        set_quantity = int(quantity) if quantity is not None and mode == "set" else None
        await self.async_update_container(tag_id=tag_id, quantity=set_quantity, delta=delta, create_missing=True)

    async def async_save(self, *, notify: bool = True) -> None:
        await self._store.async_save(self.data)
        if notify:
            for listener in list(self._listeners):
                listener()
            self.hass.bus.async_fire(EVENT_MISE_EN_PLACE_ASSISTANT_UPDATED, {})

    def item_key(self, item_id: str | None, item_label: str | None) -> str:
        return item_id or slugify(item_label or "unassigned")

    def item_totals(self, *, include_empty: bool = True) -> dict[str, dict[str, Any]]:
        """Return totals for filled containers, grouped by stable item identity."""
        totals: dict[str, dict[str, Any]] = {
            key: {
                "item_id": item.get("id"), "label": item.get("label") or key,
                "unit": item.get("unit") or DEFAULT_UNIT, "quantity": 0,
                "quantities": {},
                "containers": 0, "locations": {},
            }
            for key, item in self.items.items()
        } if include_empty else {}
        for container in self.containers.values():
            if not container.get("item_id") and not container.get("item_label"):
                continue
            if int(container.get("quantity", 0)) <= 0:
                continue
            key = self.item_key(container.get("item_id"), container.get("item_label"))
            total = totals.setdefault(key, {"item_id": container.get("item_id"), "label": container.get("item_label") or key, "unit": None, "quantity": None, "quantities": {}, "containers": 0, "locations": {}})
            unit = container.get("unit") or DEFAULT_UNIT
            amount = int(container.get("quantity", 0))
            total["quantities"][unit] = total["quantities"].get(unit, 0) + amount
            total["containers"] += 1
            location = container.get("location") or "Unassigned"
            location_totals = total["locations"].setdefault(location, {})
            location_totals[unit] = location_totals.get(unit, 0) + amount
        for total in totals.values():
            if len(total["quantities"]) == 1:
                total["unit"], total["quantity"] = next(iter(total["quantities"].items()))
            elif len(total["quantities"]) > 1:
                total["unit"] = None
                total["quantity"] = None
        return totals

    def _remember_item(self, item_id: str | None, label: str | None, item_format: str | None, unit: str | None) -> bool:
        """Store a product definition independently from any reusable container."""
        if not item_id and not label:
            return False
        key = self.item_key(item_id, label)
        candidate = {
            "id": item_id,
            "label": label or key,
            "format": item_format,
            "unit": unit or DEFAULT_UNIT,
        }
        if self.items.get(key) == candidate:
            return False
        self.items[key] = candidate
        return True

    def location_count(self, location_key: str) -> int:
        location = self.locations.get(location_key)
        if not location:
            return 0
        return sum(1 for container in self.containers.values() if container.get("location") == location["name"])

    @staticmethod
    def _normalize_tag_id(tag_id: str) -> str:
        tag_id = str(tag_id).strip()
        if not tag_id:
            raise ValueError("tag_id is required")
        return tag_id

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip() or None

    def _add_log_entry(self, action: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.logbook.append({"created_at": _utc_now(), "action": action, "message": message, "details": details or {}})
        if len(self.logbook) > 200:
            del self.logbook[:-200]
