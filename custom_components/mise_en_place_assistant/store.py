"""Persistent kitchen inventory model for Mise en Place Assistant."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4, uuid5

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

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
from .units import normalize_quantity, quantity_in_display_unit, units_are_compatible

_LOGGER = logging.getLogger(__name__)

# Product IDs belong to this integration, rather than to a catalog provider.
# UUID5 makes the one-time migration deterministic while UUID4 identifies new
# locally-created products that have no source identifier.
_PRODUCT_NAMESPACE = UUID("fe222126-260f-48dc-a4ae-9817f251e867")


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
            "products": {},
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
        for key, default in (("items", {}), ("products", {}), ("containers", {}), ("locations", {}), ("logbook", []), ("devices", {})):
            if key not in self.data:
                self.data[key] = default
                changed = True

        # `items` was the pre-catalog registry, keyed by an external/mock item
        # ID. Keep it untouched for migration compatibility, but move canonical
        # product identity into `products`.
        for key, item in self.items.items():
            _, product_changed = self._ensure_product(
                source_id=item.get("id") or key,
                label=item.get("label"),
                item_format=item.get("format"),
                unit=item.get("unit"),
                source_provider="mock" if self._is_mock_item_id(item.get("id")) else "legacy",
                legacy_key=key,
            )
            changed = product_changed or changed

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
                    if float(container.get("canonical_quantity", container.get("quantity", 0))) > 0
                    else CONTAINER_STATE_EMPTY
                )
                changed = True
            if "created_at" not in container:
                container["created_at"] = _utc_now()
                changed = True
            if "updated_at" not in container:
                container["updated_at"] = container["created_at"]
                changed = True
            normalized_quantity = normalize_quantity(
                container.get("display_quantity", container.get("quantity", 0)),
                container.get("display_unit", container.get("unit", DEFAULT_UNIT)),
            )
            # Earlier records had only literal quantity/unit fields. Retain
            # those display fields while adding integration-owned canonical data.
            if any(container.get(key) != value for key, value in normalized_quantity.items()):
                container.update(normalized_quantity)
                changed = True
            if container.get("item_id") or container.get("item_label"):
                product_id, product_changed = self._ensure_product(
                    container.get("item_id"),
                    container.get("item_label"),
                    container.get("item_format"),
                    container.get("unit"),
                    source_provider="mock" if self._is_mock_item_id(container.get("item_id")) else "legacy",
                )
                if container.get("product_id") != product_id:
                    container["product_id"] = product_id
                    changed = True
                changed = product_changed or changed
        for item in MOCK_ITEMS:
            _, product_changed = self._ensure_product(
                item["id"], item["label"], item.get("format"), item.get("unit"), source_provider="mock"
            )
            changed = product_changed or changed
        return changed

    @property
    def containers(self) -> dict[str, dict[str, Any]]:
        return self.data.setdefault("containers", {})

    @property
    def items(self) -> dict[str, dict[str, Any]]:
        """Return the legacy item registry retained for storage compatibility."""
        return self.data.setdefault("items", {})

    @property
    def products(self) -> dict[str, dict[str, Any]]:
        """Return locally-owned products, keyed by stable product ID."""
        return self.data.setdefault("products", {})

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
        quantity: int | float = 0,
        location: str | None = None,
        state: str | None = None,
        unit: str = DEFAULT_UNIT,
        item_id: str | None = None,
        item_label: str | None = None,
        item_format: str | None = None,
    ) -> None:
        tag_id = self._normalize_tag_id(tag_id)
        old = self.containers.get(tag_id, {})
        quantity_data = normalize_quantity(quantity, unit)
        location = self.ensure_location(location)
        now = _utc_now()
        is_new = not old
        chosen_state = (
            state
            if state and state != "unknown"
            else (CONTAINER_STATE_FILLED if quantity_data["canonical_quantity"] else CONTAINER_STATE_EMPTY)
        )
        product_id = self._resolve_product_id(item_id, item_label, item_format, unit)
        self.containers[tag_id] = {
            "tag_id": tag_id,
            "name": self._normalize_optional(name) or old.get("name") or self.default_container_name(tag_id),
            "item_id": item_id,
            "item_label": item_label,
            "item_format": item_format,
            "product_id": product_id,
            **quantity_data,
            "location": location,
            "state": chosen_state,
            "unit": unit or DEFAULT_UNIT,
            "created_at": old.get("created_at", now),
            "updated_at": now,
        }
        if is_new:
            async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "container", tag_id)
        if product_id:
            async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "product", product_id)
        self._add_log_entry(
            "Container created" if is_new else "Container refilled",
            f"{self.containers[tag_id]['name']} is {chosen_state} in {location or 'no location'}.",
            {"tag_id": tag_id, "quantity": quantity_data["quantity"], "unit": quantity_data["unit"], "canonical_quantity": quantity_data["canonical_quantity"], "canonical_unit": quantity_data["canonical_unit"], "location": location, "state": chosen_state,
             "product": self.product_snapshot(self.containers[tag_id])},
        )
        await self.async_save()

    async def async_update_container(
        self,
        *,
        tag_id: str,
        quantity: int | float | None = None,
        delta: int | float | None = None,
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
        display_unit = unit if unit is not None else container.get("display_unit", container.get("unit", DEFAULT_UNIT))
        if quantity is not None:
            container.update(normalize_quantity(quantity, display_unit))
        if delta is not None:
            # Deltas use the supplied unit, or the container's displayed unit.
            # A conversion is only performed inside that unit's own dimension.
            delta_data = normalize_quantity(abs(delta), display_unit)
            if not units_are_compatible(container.get("canonical_unit"), delta_data["canonical_unit"]):
                raise ValueError(
                    f"Cannot apply {display_unit} to a container measured in "
                    f"{container.get('canonical_unit', DEFAULT_UNIT)}"
                )
            canonical_quantity = max(
                0,
                float(container.get("canonical_quantity", container.get("quantity", 0)))
                + (-1 if delta < 0 else 1) * float(delta_data["canonical_quantity"]),
            )
            container.update(quantity_in_display_unit(canonical_quantity, display_unit))
        if unit is not None and quantity is None and delta is None:
            if not units_are_compatible(container.get("canonical_unit"), display_unit):
                raise ValueError(
                    f"Cannot change a container measured in {container.get('canonical_unit', DEFAULT_UNIT)} "
                    f"to {display_unit} without setting a new quantity"
                )
            container.update(
                quantity_in_display_unit(container.get("canonical_quantity", container.get("quantity", 0)), display_unit)
            )
        if location is not None:
            container["location"] = self.ensure_location(location)
        if state is not None:
            container["state"] = state
        elif quantity_changed:
            # A container that has just been consumed is physically empty and
            # needs washing before it can return to clean storage.
            container["state"] = (
                CONTAINER_STATE_FILLED
                if container["canonical_quantity"]
                else CONTAINER_STATE_DIRTY
            )
        if name is not None:
            container["name"] = self._normalize_optional(name) or self.default_container_name(tag_id)
        if item_id is not None:
            container["item_id"] = item_id
        if item_label is not None:
            container["item_label"] = item_label
        if item_format is not None:
            container["item_format"] = item_format
        if item_id is not None or item_label is not None or item_format is not None:
            container["product_id"] = self._resolve_product_id(
                container.get("item_id"), container.get("item_label"),
                container.get("item_format"), container.get("unit"),
            )
        container["updated_at"] = _utc_now()
        if container.get("product_id"):
            async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "product", container["product_id"])
        self._add_log_entry(
            "Container updated",
            f"{container['name']} changed from {before.get('state')} to {container.get('state')}.",
            {"tag_id": tag_id, "old_quantity": before.get("quantity"), "quantity": container.get("quantity"), "old_state": before.get("state"), "state": container.get("state"),
             "product": self.product_snapshot(container)},
        )
        await self.async_save()

    async def async_mark_container_clean(self, tag_id: str, *, location: str | None = None) -> None:
        """Record the post-wash NFC scan; the container no longer has contents."""
        tag_id = self._normalize_tag_id(tag_id)
        if tag_id not in self.containers:
            raise KeyError(tag_id)
        container = self.containers[tag_id]
        previous_product = self.product_snapshot(container)
        if location is not None:
            container["location"] = self.ensure_location(location)
        container.update({
            "item_id": None,
            "item_label": None,
            "item_format": None,
            "product_id": None,
            **normalize_quantity(0, container.get("display_unit", container.get("unit", DEFAULT_UNIT))),
            "state": CONTAINER_STATE_CLEAN,
            "updated_at": _utc_now(),
        })
        self._add_log_entry(
            "Container washed",
            f"{container['name']} was scanned clean and is ready for storage.",
            {"tag_id": tag_id, "previous_item": (previous_product or {}).get("label"), "previous_product": previous_product, "location": container.get("location")},
        )
        await self.async_save()

    async def async_scan_container(self, *, tag_id: str, quantity: int | float | None = None, mode: str = "set") -> None:
        delta = float(quantity) if quantity is not None and mode == "add" else None
        if quantity is not None and mode == "remove":
            delta = -float(quantity)
        set_quantity = float(quantity) if quantity is not None and mode == "set" else None
        await self.async_update_container(tag_id=tag_id, quantity=set_quantity, delta=delta, create_missing=True)

    async def async_save(self, *, notify: bool = True) -> None:
        await self._store.async_save(self.data)
        if notify:
            for listener in list(self._listeners):
                listener()
            self.hass.bus.async_fire(EVENT_MISE_EN_PLACE_ASSISTANT_UPDATED, {})

    def item_totals(self, *, include_empty: bool = True) -> dict[str, dict[str, Any]]:
        """Return totals for filled containers, grouped by stable local product ID."""
        totals: dict[str, dict[str, Any]] = {
            key: {
                "product_id": key, "item_id": item.get("source", {}).get("id"), "label": item.get("label") or key,
                "unit": item.get("unit") or DEFAULT_UNIT, "quantity": 0,
                "quantities": {},
                "containers": 0, "locations": {},
            }
            for key, item in self.products.items()
        } if include_empty else {}
        for container in self.containers.values():
            product_id = container.get("product_id")
            if not product_id:
                continue
            if float(container.get("canonical_quantity", container.get("quantity", 0))) <= 0:
                continue
            product = self.products.get(product_id, {})
            total = totals.setdefault(product_id, {"product_id": product_id, "item_id": product.get("source", {}).get("id"), "label": product.get("label") or container.get("item_label") or product_id, "unit": None, "quantity": None, "quantities": {}, "containers": 0, "locations": {}})
            unit = container.get("canonical_unit", container.get("unit")) or DEFAULT_UNIT
            amount = container.get("canonical_quantity", container.get("quantity", 0))
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

    def _resolve_product_id(self, item_id: str | None, label: str | None, item_format: str | None, unit: str | None) -> str | None:
        """Find or create the local product record for supplied catalog data."""
        if not item_id and not label:
            return None
        product_id, _ = self._ensure_product(
            item_id, label, item_format, unit,
            source_provider="mock" if self._is_mock_item_id(item_id) else "local",
        )
        return product_id

    def _ensure_product(self, source_id: str | None, label: str | None, item_format: str | None,
                        unit: str | None, *, source_provider: str, legacy_key: str | None = None) -> tuple[str, bool]:
        """Upsert catalog presentation without changing the product's local identity."""
        product_id = self._find_product(source_id, source_provider, label)
        if not product_id:
            seed = legacy_key or (f"{source_provider}:{source_id}" if source_id else None)
            product_id = f"product_{uuid5(_PRODUCT_NAMESPACE, seed).hex}" if seed else f"product_{uuid4().hex}"
        current = self.products.get(product_id, {})
        source = {"provider": source_provider, "id": source_id} if source_id else current.get("source")
        candidate = {
            "id": product_id,
            "label": label or current.get("label") or source_id or product_id,
            "format": item_format if item_format is not None else current.get("format"),
            "unit": unit or current.get("unit") or DEFAULT_UNIT,
            "source": source,
            "status": current.get("status", "active"),
            "created_at": current.get("created_at", _utc_now()),
            "updated_at": _utc_now(),
        }
        # Avoid a save merely because the load-time timestamp would differ.
        comparable = {key: value for key, value in candidate.items() if key != "updated_at"}
        previous = {key: value for key, value in current.items() if key != "updated_at"}
        if comparable == previous:
            return product_id, False
        self.products[product_id] = candidate
        return product_id, True

    def _find_product(self, source_id: str | None, source_provider: str, label: str | None) -> str | None:
        for product_id, product in self.products.items():
            source = product.get("source") or {}
            if source_id and source.get("provider") == source_provider and source.get("id") == source_id:
                return product_id
            # Stored inventories from before source adapters existed are
            # provider-neutral. Preserve that identity when a manual product
            # is subsequently edited instead of creating a duplicate.
            if (
                source_id
                and source.get("id") == source_id
                and {source.get("provider"), source_provider} <= {"legacy", "local"}
            ):
                return product_id
        if not source_id and label:
            for product_id, product in self.products.items():
                if product.get("label", "").casefold() == label.casefold():
                    return product_id
        return None

    def product_for_container(self, container: dict[str, Any]) -> dict[str, Any] | None:
        product_id = container.get("product_id")
        return self.products.get(product_id) if product_id else None

    def product_snapshot(self, container: dict[str, Any]) -> dict[str, Any] | None:
        """Return the immutable product attribution to embed in a log entry."""
        product = self.product_for_container(container)
        if not product:
            return None
        return {"product_id": product["id"], "label": product["label"], "source": dict(product.get("source") or {})}

    @staticmethod
    def _is_mock_item_id(item_id: str | None) -> bool:
        return any(item["id"] == item_id for item in MOCK_ITEMS)

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
