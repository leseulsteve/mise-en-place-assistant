"""Persistent kitchen inventory model for Mise en Place Assistant."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4, uuid5

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import (
    CONF_CATALOG_PROVIDER,
    DEFAULT_UNIT,
    DOMAIN,
    CONF_MEALIE_TOKEN,
    CONF_MEALIE_ENTRY_ID,
    CONF_MEALIE_URL,
    CONF_M5DIAL_SERVICE_PREFIX,
    DEFAULT_DIAL_THEME,
    DEFAULT_M5DIAL_SERVICE_PREFIX,
    DIAL_THEMES,
    DEFAULT_CATALOG_PROVIDER,
    EVENT_MISE_EN_PLACE_ASSISTANT_UPDATED,
    SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED,
    STORAGE_VERSION,
    PROVIDER_MEALIE,
    PROVIDER_MOCKED,
)
from .mealie import MealieCatalogClient, MealieCatalogError
from .mocked import MOCKED_FOODS, MOCKED_RECIPES
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
            "catalog": [],
            "recipes": [],
            "dial_theme": DEFAULT_DIAL_THEME,
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
        for key, default in (("items", {}), ("products", {}), ("containers", {}), ("locations", {}), ("logbook", []), ("devices", {}), ("catalog", []), ("recipes", []), ("dial_theme", DEFAULT_DIAL_THEME)):
            if key not in self.data:
                self.data[key] = default
                changed = True
        if "mealie_catalog" in self.data and not self.data.get("catalog"):
            self.data["catalog"] = self.data["mealie_catalog"]
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
                source_provider="legacy",
                legacy_key=key,
            )
            changed = product_changed or changed

        for tag_id, container in self.containers.items():
            if "content_kind" not in container:
                container["content_kind"] = "ingredient" if container.get("item_id") else None
                changed = True
            if not container.get("tag_id"):
                container["tag_id"] = tag_id
                changed = True
            if not container.get("name"):
                container["name"] = self.default_container_name(tag_id)
                changed = True
            if "state" in container:
                container.pop("state")
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
                    source_provider="legacy",
                )
                if container.get("product_id") != product_id:
                    container["product_id"] = product_id
                    changed = True
                changed = product_changed or changed
        return changed

    @property
    def dial_theme(self) -> str:
        """Return the selected Dial theme, falling back safely for old data."""
        theme = self.data.get("dial_theme", DEFAULT_DIAL_THEME)
        return theme if theme in DIAL_THEMES else DEFAULT_DIAL_THEME

    async def async_set_dial_theme(self, theme: str) -> None:
        """Persist and apply a Home Assistant-selected Dial theme."""
        if theme not in DIAL_THEMES:
            raise ValueError(f"Unsupported Dial theme: {theme}")
        service_prefix = self.entry.options.get(
            CONF_M5DIAL_SERVICE_PREFIX,
            self.entry.data.get(CONF_M5DIAL_SERVICE_PREFIX, DEFAULT_M5DIAL_SERVICE_PREFIX),
        )
        service = f"{service_prefix}_set_theme"
        if not self.hass.services.has_service("esphome", service):
            raise HomeAssistantError("The enrolled M5Dial does not support theme selection")
        await self.hass.services.async_call(
            "esphome",
            service,
            {"theme": theme},
            blocking=True,
        )
        if self.data.get("dial_theme") != theme:
            self.data["dial_theme"] = theme
            await self.async_save()

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

    async def async_catalog_payload(self) -> dict[str, Any]:
        """Return the selected provider's food catalog and local locations."""
        items = await self.async_refresh_catalog()
        locations = [location["name"] for location in self.locations.values()]
        return {"items": items, "recipes": self.recipe_items(), "locations": locations}

    def catalog_provider(self) -> str:
        """Return the configured catalog provider, preserving old entries as Mocked."""
        return self.entry.options.get(
            CONF_CATALOG_PROVIDER,
            self.entry.data.get(CONF_CATALOG_PROVIDER, DEFAULT_CATALOG_PROVIDER),
        )

    async def async_refresh_catalog(self) -> list[dict[str, str]]:
        """Fetch the selected catalog provider; do not silently switch providers."""
        provider = self.catalog_provider()
        if provider == PROVIDER_MOCKED:
            items = MOCKED_FOODS
            recipes = MOCKED_RECIPES
        elif provider == PROVIDER_MEALIE:
            items, recipes = await self._async_fetch_mealie_catalog()
        else:
            raise MealieCatalogError(f"Unsupported catalog provider: {provider}")
        changed = items != self.data.get("catalog") or recipes != self.data.get("recipes")
        if changed:
            self.data["catalog"] = items
            self.data["recipes"] = recipes
        foods_by_id = {item["id"]: item for item in items}
        for product in list(self.products.values()):
            source = product.get("source") or {}
            food = foods_by_id.get(source.get("id")) if source.get("provider") == provider else None
            if food:
                _, product_changed = self._ensure_product(
                    food["id"], food["label"], food["format"], food["unit"], source_provider=provider
                )
                changed = changed or product_changed
        if changed:
            await self.async_save(notify=False)
        return items

    async def _async_fetch_mealie_catalog(self) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        """Fetch Mealie foods and recipes for the Mealie provider."""
        source_entry_id = self.entry.options.get(
            CONF_MEALIE_ENTRY_ID, self.entry.data.get(CONF_MEALIE_ENTRY_ID)
        )
        source_entry = (
            self.hass.config_entries.async_get_entry(source_entry_id)
            if source_entry_id
            else None
        )
        if source_entry and source_entry.domain == PROVIDER_MEALIE:
            url = source_entry.data.get(CONF_HOST, "")
            token = source_entry.data.get(CONF_API_TOKEN, "")
        else:
            url = self.entry.options.get(CONF_MEALIE_URL, self.entry.data.get(CONF_MEALIE_URL, ""))
            token = self.entry.options.get(CONF_MEALIE_TOKEN, self.entry.data.get(CONF_MEALIE_TOKEN, ""))
        if url and "://" not in url:
            url = f"http://{url}"
        if not url or not token:
            raise MealieCatalogError("Mealie URL and API token must be configured")
        try:
            client = MealieCatalogClient(self.hass, url, token)
            items = await client.async_fetch_foods()
            recipes = await client.async_fetch_recipes()
        except (MealieCatalogError, ValueError) as err:
            raise MealieCatalogError("Mealie food catalog is unavailable") from err
        return items, recipes

    def catalog_items(self) -> list[dict[str, str]]:
        """Return the most recently verified selected-provider catalog."""
        items = self.data.get("catalog", [])
        return items if isinstance(items, list) else []

    def recipe_items(self) -> list[dict[str, Any]]:
        """Return the most recently verified recipe catalog."""
        recipes = self.data.get("recipes", [])
        return recipes if isinstance(recipes, list) else []

    async def async_catalog_item(self, item_id: str) -> dict[str, str]:
        """Resolve a selected food against the configured provider before saving."""
        for item in await self.async_refresh_catalog():
            if item["id"] == item_id:
                return item
        raise ValueError("Selected food no longer exists in the configured catalog")

    async def async_recipe_item(self, recipe_id: str) -> dict[str, Any]:
        """Resolve a recipe against the provider before saving a prepared batch."""
        await self.async_refresh_catalog()
        for recipe in self.recipe_items():
            if recipe["id"] == recipe_id:
                return recipe
        raise ValueError("Selected recipe no longer exists in the configured catalog")

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
        unit: str = DEFAULT_UNIT,
        item_id: str | None = None,
        item_label: str | None = None,
        item_format: str | None = None,
        source_provider: str = "local",
        content_kind: str = "ingredient",
        classification: dict[str, str] | None = None,
    ) -> None:
        tag_id = self._normalize_tag_id(tag_id)
        old = self.containers.get(tag_id, {})
        quantity_data = normalize_quantity(quantity, unit)
        location = self.ensure_location(location)
        now = _utc_now()
        is_new = not old
        if content_kind not in {"ingredient", "recipe", "meal"}:
            raise ValueError("content_kind must be ingredient, recipe, or meal")
        product_id = self._resolve_product_id(
            item_id, item_label, item_format, unit, source_provider, classification
        )
        self.containers[tag_id] = {
            "tag_id": tag_id,
            "name": self._normalize_optional(name) or old.get("name") or self.default_container_name(tag_id),
            "item_id": item_id,
            "item_label": item_label,
            "item_format": item_format,
            "product_id": product_id,
            "content_kind": content_kind,
            **quantity_data,
            "location": location,
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
            f"{self.containers[tag_id]['name']} now contains {self.containers[tag_id]['item_label'] or 'nothing'} in {location or 'no location'}.",
            {"tag_id": tag_id, "quantity": quantity_data["quantity"], "unit": quantity_data["unit"], "canonical_quantity": quantity_data["canonical_quantity"], "canonical_unit": quantity_data["canonical_unit"], "location": location,
             "product": self.product_snapshot(self.containers[tag_id])},
        )
        await self.async_save()

    @staticmethod
    def _recipe_classification(recipe: dict[str, Any]) -> dict[str, str]:
        tags = {str(tag).casefold() for tag in recipe.get("tags", [])}
        component = next((tag[14:] for tag in tags if tag.startswith("mpa:component:")), None)
        protein = next((tag[20:] for tag in tags if tag.startswith("mpa:primary-protein:")), None)
        return {key: value for key, value in {"component": component, "primary_protein": protein}.items() if value}

    async def async_create_recipe_container(
        self, *, recipe_id: str, content_kind: str, tag_id: str, name: str | None = None,
        quantity: int | float = 0, location: str | None = None,
    ) -> None:
        """Create a portion-counted recipe or ready-meal container."""
        recipe = await self.async_recipe_item(recipe_id)
        await self.async_create_container(
            tag_id=tag_id, name=name, quantity=quantity, location=location,
            unit=recipe["unit"], item_id=recipe["id"], item_label=recipe["label"],
            item_format=recipe["format"], source_provider="mealie_recipe",
            content_kind=content_kind, classification=self._recipe_classification(recipe),
        )

    async def async_update_container(
        self,
        *,
        tag_id: str,
        quantity: int | float | None = None,
        delta: int | float | None = None,
        location: str | None = None,
        name: str | None = None,
        unit: str | None = None,
        item_id: str | None = None,
        item_label: str | None = None,
        item_format: str | None = None,
        source_provider: str = "local",
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
                source_provider,
            )
        container["updated_at"] = _utc_now()
        if container.get("product_id"):
            async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "product", container["product_id"])
        self._add_log_entry(
            "Container updated",
            f"{container['name']} inventory was updated.",
            {"tag_id": tag_id, "old_quantity": before.get("quantity"), "quantity": container.get("quantity"),
             "product": self.product_snapshot(container)},
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

    def meal_inventory(self) -> dict[str, Any]:
        """Sum ready meals by Mealie's configured yield unit."""
        components: dict[str, dict[str, Any]] = {}
        for container in self.containers.values():
            if container.get("content_kind") != "meal":
                continue
            amount = float(container.get("canonical_quantity", container.get("quantity", 0)))
            unit = container.get("canonical_unit", container.get("unit")) or DEFAULT_UNIT
            if amount <= 0:
                continue
            product = self.product_for_container(container) or {}
            classification = product.get("classification") or {}
            component = classification.get("component")
            if not component:
                continue
            entry = components.setdefault(component, {"component": component, "quantities": {}, "proteins": {}, "recipes": {}})
            entry["quantities"][unit] = entry["quantities"].get(unit, 0) + amount
            protein = classification.get("primary_protein")
            if protein:
                protein_totals = entry["proteins"].setdefault(protein, {})
                protein_totals[unit] = protein_totals.get(unit, 0) + amount
            label = product.get("label") or container.get("item_label") or "Unknown recipe"
            recipe_totals = entry["recipes"].setdefault(label, {})
            recipe_totals[unit] = recipe_totals.get(unit, 0) + amount
        return {"components": sorted(components.values(), key=lambda entry: entry["component"])}

    def _resolve_product_id(self, item_id: str | None, label: str | None, item_format: str | None,
                            unit: str | None, source_provider: str = "local",
                            classification: dict[str, str] | None = None) -> str | None:
        """Find or create the local product record for supplied catalog data."""
        if not item_id and not label:
            return None
        product_id, _ = self._ensure_product(
            item_id, label, item_format, unit,
            source_provider=source_provider if item_id else "local", classification=classification,
        )
        return product_id

    def _ensure_product(self, source_id: str | None, label: str | None, item_format: str | None,
                        unit: str | None, *, source_provider: str, legacy_key: str | None = None,
                        classification: dict[str, str] | None = None) -> tuple[str, bool]:
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
            "classification": classification if classification is not None else current.get("classification", {}),
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

    def item_label_for_container(self, container: dict[str, Any]) -> str:
        """Prefer Mealie's current name for a catalog-linked container."""
        product = self.product_for_container(container)
        if product and (product.get("source") or {}).get("provider") in {PROVIDER_MEALIE, PROVIDER_MOCKED}:
            return product.get("label") or container.get("item_label") or "No current item"
        return container.get("item_label") or "No current item"

    def product_snapshot(self, container: dict[str, Any]) -> dict[str, Any] | None:
        """Return the immutable product attribution to embed in a log entry."""
        product = self.product_for_container(container)
        if not product:
            return None
        return {"product_id": product["id"], "label": product["label"], "source": dict(product.get("source") or {})}

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
