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
    CONF_CATALOG_PROVIDERS,
    CONF_DEV_MODE,
    CONF_GROCY_TOKEN,
    CONF_GROCY_URL,
    CONF_KITCHENOWL_SHOPPING_LIST_ID,
    CONF_KITCHENOWL_TOKEN,
    CONF_KITCHENOWL_URL,
    CONF_SHOPPING_LIST_PROVIDER,
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
    CATALOG_PROVIDERS,
    PROVIDER_GROCY,
    PROVIDER_KITCHENOWL,
    PROVIDER_MEALIE,
    PROVIDER_MOCKED,
    SHOPPING_LIST_PROVIDER_AUTO,
    LOCATION_TYPES,
    PRODUCT_CONTAINER_POLICIES,
    PRODUCT_MEAL_ROLES,
    PRODUCT_STORAGE_BEHAVIORS,
    VOID_LOCATION_ID,
    VOID_LOCATION_NAME,
)
from .grocy import GrocyCatalogClient, GrocyCatalogError
from .kitchenowl import KitchenOwlError, KitchenOwlShoppingClient
from .mealie import MealieCatalogClient, MealieCatalogError
from .mocked import MOCKED_FOODS, MOCKED_RECIPES, MOCKED_STOCK, MOCKED_STORAGE_LOCATIONS
from .units import normalize_quantity, quantity_in_display_unit, units_are_compatible

_LOGGER = logging.getLogger(__name__)

# Product IDs belong to this integration, rather than to a catalog provider.
# UUID5 makes the one-time migration deterministic while UUID4 identifies new
# locally-created products that have no source identifier.
_PRODUCT_NAMESPACE = UUID("fe222126-260f-48dc-a4ae-9817f251e867")
PROTEIN_GROUP_ALIASES = {
    "bean": "vegetarian",
    "beans": "vegetarian",
    "beef": "red meat",
    "chicken": "poultry",
    "cod": "fish",
    "duck": "poultry",
    "fish": "fish",
    "lamb": "red meat",
    "lentil": "vegetarian",
    "lentils": "vegetarian",
    "pork": "red meat",
    "poultry": "poultry",
    "red meat": "red meat",
    "red-meat": "red meat",
    "red_meat": "red meat",
    "salmon": "fish",
    "seafood": "fish",
    "tempeh": "vegetarian",
    "tofu": "vegetarian",
    "tuna": "fish",
    "turkey": "poultry",
    "vegan": "vegetarian",
    "veal": "red meat",
    "vegetarian": "vegetarian",
    "venison": "red meat",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_sublocations(value: Any) -> list[str]:
    """Return unique shelf/drawer names for a storage location."""
    if value in (None, ""):
        return []
    raw_values = value if isinstance(value, list) else [value]
    sublocations: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        name = str(raw_value or "").strip()
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            sublocations.append(name)
    return sublocations


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
            "stock": [],
            "storage_locations": [],
            "product_metadata": {},
            "dial_theme": DEFAULT_DIAL_THEME,
        }
        self._listeners: list[Callable[[], None]] = []

    async def async_load(self) -> None:
        """Load data and upgrade the former inventory shape in place."""
        stored = await self._store.async_load()
        if stored:
            self.data = stored
        changed = self._ensure_schema()

        if self.mock_catalog_enabled():
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
            len(self.storage_locations()),
        )

    def _ensure_schema(self) -> bool:
        """Ensure old Mise en Place Assistant data remains usable by the reusable-container model."""
        changed = False
        for key, default in (("items", {}), ("products", {}), ("containers", {}), ("locations", {}), ("logbook", []), ("devices", {}), ("catalog", []), ("recipes", []), ("stock", []), ("storage_locations", []), ("product_metadata", {}), ("dial_theme", DEFAULT_DIAL_THEME)):
            if key not in self.data:
                self.data[key] = default
                changed = True
        if "mealie_catalog" in self.data and not self.data.get("catalog"):
            self.data["catalog"] = self.data["mealie_catalog"]
            changed = True

        # Locations used to be keyed solely by their display name. Give each
        # one a permanent ID so a rename cannot orphan its containers or Home
        # Assistant sensor associations.
        for key, location in list(self.locations.items()):
            if not isinstance(location, dict):
                location = {"name": str(location)}
                self.locations[key] = location
                changed = True
            name = self._normalize_optional(location.get("name")) or key
            candidate = {
                "id": location.get("id") or f"location_{uuid5(_PRODUCT_NAMESPACE, f'location:{key}').hex}",
                "name": name,
                "location_type": location.get("location_type", "other"),
                "area_id": location.get("area_id"),
                "sensors": location.get("sensors") if isinstance(location.get("sensors"), dict) else {},
                "monitoring": location.get("monitoring") if isinstance(location.get("monitoring"), dict) else {},
                "created_at": location.get("created_at", _utc_now()),
                "updated_at": location.get("updated_at", location.get("created_at", _utc_now())),
            }
            if candidate["location_type"] not in LOCATION_TYPES:
                candidate["location_type"] = "other"
            if any(location.get(field) != value for field, value in candidate.items()):
                location.update(candidate)
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
            if "archived" not in container:
                container["archived"] = False
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
            if not container.get("location_id"):
                legacy_location = self._normalize_optional(container.get("location"))
                location = self.locations.get(legacy_location.casefold()) if legacy_location else None
                container["location_id"] = location["id"] if location else VOID_LOCATION_ID
                container["location"] = location["name"] if location else VOID_LOCATION_NAME
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

    def active_containers(self) -> list[dict[str, Any]]:
        """Return containers that remain in active rotation."""
        return [container for container in self.containers.values() if not container.get("archived")]

    @property
    def items(self) -> dict[str, dict[str, Any]]:
        """Return the legacy item registry retained for storage compatibility."""
        return self.data.setdefault("items", {})

    @property
    def products(self) -> dict[str, dict[str, Any]]:
        """Return locally-owned products, keyed by stable product ID."""
        return self.data.setdefault("products", {})

    @property
    def product_metadata(self) -> dict[str, dict[str, Any]]:
        """Return HA-owned Mise workflow metadata keyed by provider item ID."""
        return self.data.setdefault("product_metadata", {})

    @property
    def locations(self) -> dict[str, dict[str, Any]]:
        """Return HA-only annotations keyed by provider-owned location IDs."""
        return self.data.setdefault("locations", {})

    def storage_locations(self) -> list[dict[str, Any]]:
        """Return provider-owned storage locations, with local HA annotations merged in."""
        provider_locations = self.data.get("storage_locations", [])
        if not isinstance(provider_locations, list):
            provider_locations = []
        if not provider_locations and self.mock_catalog_enabled():
            provider_locations = [
                {"id": location["id"], "name": location["name"], "provider": PROVIDER_MOCKED, "active": True}
                for location in self.locations.values()
            ]
        merged: list[dict[str, Any]] = []
        for location in provider_locations:
            if not isinstance(location, dict) or not location.get("id"):
                continue
            annotation = self.locations.get(str(location["id"]), {})
            merged.append(
                {
                    **annotation,
                    **location,
                    "location_type": annotation.get("location_type", "other"),
                    "sublocations": annotation.get("sublocations", []),
                    "area_id": annotation.get("area_id"),
                    "sensors": annotation.get("sensors", {}),
                    "monitoring": annotation.get("monitoring", {}),
                    "editable": True,
                }
            )
        return sorted(merged, key=lambda item: str(item.get("name", "")).casefold())

    def _mocked_storage_locations(self) -> list[dict[str, Any]]:
        """Return default and user-created mocked storage locations."""
        locations = [dict(location) for location in MOCKED_STORAGE_LOCATIONS]
        seen_ids = {str(location["id"]) for location in locations}
        seen_names = {str(location["name"]).casefold() for location in locations}
        for location in self.data.get("storage_locations", []):
            if (
                isinstance(location, dict)
                and location.get("provider") == PROVIDER_MOCKED
                and location.get("id")
                and str(location["id"]) not in seen_ids
            ):
                locations.append({**location, "provider": PROVIDER_MOCKED, "active": location.get("active", True)})
                seen_ids.add(str(location["id"]))
                seen_names.add(str(location.get("name", "")).casefold())
        for location in self.locations.values():
            if not location.get("id") or not location.get("name"):
                continue
            if str(location["id"]) in seen_ids or str(location["name"]).casefold() in seen_names:
                continue
            locations.append(
                {
                    "id": location["id"],
                    "name": location["name"],
                    "provider": PROVIDER_MOCKED,
                    "active": True,
                    "local": True,
                }
            )
            seen_ids.add(str(location["id"]))
            seen_names.add(str(location["name"]).casefold())
        return locations

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

    def _ensure_write_mode(self, *, allow_dev_inventory: bool = False) -> None:
        """Reject live-provider writes while allowing local DEV inventory exercises."""
        if self.mock_catalog_enabled() and not allow_dev_inventory:
            raise ValueError("DEV mode blocks provider writes; use the CRUD simulator for local mock inventory")

    async def async_catalog_payload(self) -> dict[str, Any]:
        """Return configured providers' food catalogs and local locations."""
        items = await self.async_refresh_catalog()
        locations = self.location_choices()
        return {"items": items, "recipes": self.recipe_items(), "locations": locations}

    def catalog_provider(self) -> str:
        """Return the first configured catalog provider for legacy callers."""
        providers = self.effective_catalog_providers()
        return providers[0] if providers else ""

    def catalog_providers(self) -> list[str]:
        """Return configured live catalog providers."""
        configured = self.entry.options.get(
            CONF_CATALOG_PROVIDERS,
            self.entry.data.get(CONF_CATALOG_PROVIDERS),
        )
        if configured is None:
            configured = [
                self.entry.options.get(
                    CONF_CATALOG_PROVIDER,
                    self.entry.data.get(CONF_CATALOG_PROVIDER, DEFAULT_CATALOG_PROVIDER),
                )
            ]
        providers: list[str] = []
        for provider in configured if isinstance(configured, list) else [configured]:
            if provider in CATALOG_PROVIDERS and provider not in providers:
                providers.append(provider)
        return providers

    def mock_catalog_enabled(self) -> bool:
        """Return whether DEV fallback data is allowed."""
        if CONF_DEV_MODE in self.entry.options:
            return bool(self.entry.options.get(CONF_DEV_MODE))
        if CONF_DEV_MODE in self.entry.data:
            return bool(self.entry.data.get(CONF_DEV_MODE))
        configured = self.entry.options.get(CONF_CATALOG_PROVIDERS, self.entry.data.get(CONF_CATALOG_PROVIDERS))
        legacy_provider = self.entry.data.get(CONF_CATALOG_PROVIDER, DEFAULT_CATALOG_PROVIDER)
        return configured is None and legacy_provider == PROVIDER_MOCKED

    def _ensure_mock_product_metadata(self) -> bool:
        """Seed reviewed mock products so DEV attention stays focused."""
        now = _utc_now()
        changed = False
        reviewed = {
            "mocked:baby-spinach": ("original_packaging", "fridge", "ingredient", True),
            "mocked:eggs": ("original_packaging", "fridge", "staple", True),
            "mocked:basmati-rice": ("container", "pantry", "staple", True),
            "mocked:coffee": ("container", "pantry", "staple", False),
            "mocked:frozen-peas": ("original_packaging", "freezer", "ingredient", True),
            "mocked:olive-oil": ("original_packaging", "pantry", "condiment", True),
            "mocked:soy-sauce": ("original_packaging", "pantry", "condiment", True),
            "mocked:bananas": ("no_container", "counter", "ignore", False),
        }
        for item_id, (container_policy, storage_behavior, meal_role, available_in_mealie) in reviewed.items():
            if item_id in self.product_metadata:
                continue
            self.product_metadata[item_id] = {
                "item_id": item_id,
                "container_policy": container_policy,
                "storage_behavior": storage_behavior,
                "meal_role": meal_role,
                "available_in_mealie": available_in_mealie,
                "created_at": now,
                "updated_at": now,
                "reviewed_at": now,
            }
            changed = True
        return changed

    def effective_catalog_providers(self) -> list[str]:
        """Return live providers, or DEV mock data when no live provider is set up."""
        if self.mock_catalog_enabled():
            return [PROVIDER_MOCKED]
        providers = self.catalog_providers()
        if providers:
            return providers
        return []

    def live_stack_required(self) -> bool:
        """Return whether all external data/workflow providers must be usable."""
        return not self.mock_catalog_enabled()

    def kitchenowl_configured(self) -> bool:
        """Return whether KitchenOwl shopping-list settings are complete."""
        return bool(
            self.entry.options.get(CONF_KITCHENOWL_URL, self.entry.data.get(CONF_KITCHENOWL_URL, ""))
            and self.entry.options.get(CONF_KITCHENOWL_TOKEN, self.entry.data.get(CONF_KITCHENOWL_TOKEN, ""))
            and self.entry.options.get(
                CONF_KITCHENOWL_SHOPPING_LIST_ID,
                self.entry.data.get(CONF_KITCHENOWL_SHOPPING_LIST_ID),
            )
        )

    def shopping_list_provider(self) -> str:
        """Return the preferred shopping-list target."""
        provider = self.entry.options.get(
            CONF_SHOPPING_LIST_PROVIDER,
            self.entry.data.get(CONF_SHOPPING_LIST_PROVIDER, SHOPPING_LIST_PROVIDER_AUTO),
        )
        return provider if provider in {SHOPPING_LIST_PROVIDER_AUTO, PROVIDER_GROCY, PROVIDER_KITCHENOWL} else SHOPPING_LIST_PROVIDER_AUTO

    def grocy_configured(self) -> bool:
        """Return whether Grocy credentials are available."""
        return bool(
            self.entry.options.get(CONF_GROCY_URL, self.entry.data.get(CONF_GROCY_URL, ""))
            and self.entry.options.get(CONF_GROCY_TOKEN, self.entry.data.get(CONF_GROCY_TOKEN, ""))
        )

    async def async_validate_workflow_providers(self) -> None:
        """Validate required non-catalog workflow providers before startup completes."""
        if not self.live_stack_required():
            return
        if set(self.catalog_providers()) != set(CATALOG_PROVIDERS):
            raise MealieCatalogError("Mealie and Grocy must both be configured outside DEV mode")
        if self.shopping_list_provider() == PROVIDER_KITCHENOWL:
            if not self.kitchenowl_configured():
                raise MealieCatalogError("KitchenOwl must be configured when it owns shopping lists")
            try:
                await self._kitchenowl_client().async_test_connection()
            except (KitchenOwlError, ValueError) as err:
                raise MealieCatalogError("KitchenOwl shopping list is unavailable") from err

    @staticmethod
    def _with_provider(records: list[dict[str, Any]], provider: str) -> list[dict[str, Any]]:
        """Copy catalog records with explicit source attribution."""
        return [{**record, "provider": record.get("provider", provider)} for record in records]

    def recipe_provider_for_item(self, recipe: dict[str, Any]) -> str:
        """Return the product source provider for a recipe item."""
        return str(recipe.get("provider") or f"{self.catalog_provider()}_recipe")

    async def async_refresh_catalog(self) -> list[dict[str, str]]:
        """Fetch configured catalog providers; do not silently switch providers."""
        items: list[dict[str, Any]] = []
        recipes: list[dict[str, Any]] = []
        stock: list[dict[str, Any]] = []
        storage_locations: list[dict[str, Any]] = []
        mock_metadata_changed = False
        providers = self.effective_catalog_providers()
        if not providers:
            raise MealieCatalogError("At least one data provider must be configured")
        for provider in providers:
            if provider == PROVIDER_MOCKED:
                items.extend(self._with_provider(MOCKED_FOODS, PROVIDER_MOCKED))
                recipes.extend(self._with_provider(MOCKED_RECIPES, f"{PROVIDER_MOCKED}_recipe"))
                stock = list(MOCKED_STOCK)
                storage_locations = self._mocked_storage_locations()
                mock_metadata_changed = self._ensure_mock_product_metadata()
            elif provider == PROVIDER_MEALIE:
                _, provider_recipes = await self._async_fetch_mealie_catalog()
                recipes.extend(self._with_provider(provider_recipes, f"{PROVIDER_MEALIE}_recipe"))
            elif provider == PROVIDER_GROCY:
                grocy = self._grocy_client()
                try:
                    items.extend(await grocy.async_fetch_products())
                    stock = await grocy.async_fetch_stock()
                    storage_locations = await grocy.async_fetch_locations()
                except GrocyCatalogError as err:
                    raise MealieCatalogError("Grocy inventory is unavailable") from err
            else:
                raise MealieCatalogError(f"Unsupported catalog provider: {provider}")
        changed = (
            items != self.data.get("catalog")
            or recipes != self.data.get("recipes")
            or stock != self.data.get("stock", [])
            or storage_locations != self.data.get("storage_locations", [])
            or mock_metadata_changed
        )
        if changed:
            self.data["catalog"] = items
            self.data["recipes"] = recipes
            self.data["stock"] = stock
            self.data["storage_locations"] = storage_locations
            for location in storage_locations:
                async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "location", location["id"])
        foods_by_source = {
            (item.get("provider", self.catalog_provider()), item["id"]): item
            for item in items
        }
        for product in list(self.products.values()):
            source = product.get("source") or {}
            food = foods_by_source.get((source.get("provider"), source.get("id")))
            if food:
                _, product_changed = self._ensure_product(
                    food["id"], food["label"], food["format"], food["unit"],
                    source_provider=str(food.get("provider") or self.catalog_provider()),
                )
                changed = changed or product_changed
        if changed:
            await self.async_save(notify=False)
        return items

    async def _async_fetch_grocy_catalog(self) -> list[dict[str, str]]:
        """Fetch Grocy products for the Grocy provider."""
        try:
            return await self._grocy_client().async_fetch_products()
        except GrocyCatalogError as err:
            raise MealieCatalogError("Grocy product catalog is unavailable") from err

    def _grocy_client(self) -> GrocyCatalogClient:
        """Return a Grocy client from validated config-entry data."""
        url = self.entry.options.get(CONF_GROCY_URL, self.entry.data.get(CONF_GROCY_URL, ""))
        token = self.entry.options.get(CONF_GROCY_TOKEN, self.entry.data.get(CONF_GROCY_TOKEN, ""))
        if url and "://" not in url:
            url = f"http://{url}"
        if not url or not token:
            raise MealieCatalogError("Grocy URL and API key must be configured")
        try:
            return GrocyCatalogClient(self.hass, url, token)
        except ValueError as err:
            raise MealieCatalogError("Grocy product catalog is unavailable") from err

    async def _async_fetch_mealie_catalog(self) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        """Fetch Mealie foods and recipes for the Mealie provider."""
        client = self._mealie_client()
        try:
            items = await client.async_fetch_foods()
            recipes = await client.async_fetch_recipes()
        except (MealieCatalogError, ValueError) as err:
            raise MealieCatalogError("Mealie food catalog is unavailable") from err
        return items, recipes

    def _mealie_client(self) -> MealieCatalogClient:
        """Return a Mealie client from a linked HA entry or manual credentials."""
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
            return MealieCatalogClient(self.hass, url, token)
        except ValueError as err:
            raise MealieCatalogError("Mealie food catalog is unavailable") from err

    def catalog_items(self) -> list[dict[str, str]]:
        """Return the most recently verified selected-provider catalog."""
        items = self.data.get("catalog", [])
        return items if isinstance(items, list) else []

    def product_attention_items(self) -> list[dict[str, Any]]:
        """Return provider products whose Mise workflow metadata needs review."""
        stock_by_source = {
            str(row.get("id")): row
            for row in self.data.get("stock", [])
            if isinstance(row, dict) and row.get("id")
        }
        attention: list[dict[str, Any]] = []
        reviewable_providers = {PROVIDER_GROCY}
        if self.mock_catalog_enabled():
            reviewable_providers.add(PROVIDER_MOCKED)
        for item in self.catalog_items():
            if item.get("provider") not in reviewable_providers or not item.get("id"):
                continue
            item_id = str(item["id"])
            metadata = self.product_metadata.get(item_id, {})
            stock = stock_by_source.get(item_id, {})
            quantity = stock.get("quantity", 0) if stock else 0
            try:
                has_stock = float(quantity or 0) > 0
            except (TypeError, ValueError):
                has_stock = False
            if self.mock_catalog_enabled() and not has_stock:
                continue
            reasons: list[str] = []
            if not metadata.get("reviewed_at"):
                reasons.append("Needs Mise workflow review")
            if metadata.get("container_policy", "unknown") == "unknown":
                reasons.append("Container policy not selected")
            if metadata.get("storage_behavior", "unknown") == "unknown":
                reasons.append("Storage behavior not selected")
            if metadata.get("meal_role", "unknown") == "unknown":
                reasons.append("Meal role not selected")
            if "available_in_mealie" not in metadata:
                reasons.append("Mealie availability not selected")
            if not reasons:
                continue
            attention.append(
                {
                    "item_id": item_id,
                    "label": item.get("label") or item_id,
                    "format": item.get("format") or "",
                    "unit": item.get("unit") or DEFAULT_UNIT,
                    "quantity": quantity,
                    "has_stock": has_stock,
                    "metadata": {
                        "container_policy": metadata.get("container_policy", "unknown"),
                        "storage_behavior": metadata.get("storage_behavior", "unknown"),
                        "meal_role": metadata.get("meal_role", "unknown"),
                        "available_in_mealie": bool(metadata.get("available_in_mealie", False)),
                        "available_in_mealie_set": "available_in_mealie" in metadata,
                        "reviewed_at": metadata.get("reviewed_at", ""),
                    },
                    "reasons": reasons,
                }
            )
        return sorted(
            attention,
            key=lambda item: (not item["has_stock"], str(item["label"]).casefold()),
        )

    async def async_update_product_metadata(
        self,
        item_id: str,
        *,
        container_policy: str = "unknown",
        storage_behavior: str = "unknown",
        meal_role: str = "unknown",
        available_in_mealie: bool | None = None,
    ) -> dict[str, Any]:
        """Store HA-owned Mise workflow hints for a provider product."""
        item_id = str(item_id).strip()
        if not item_id:
            raise ValueError("item_id is required")
        item = await self.async_catalog_item(item_id)
        if item.get("provider") != PROVIDER_GROCY and not (
            self.mock_catalog_enabled() and item.get("provider") == PROVIDER_MOCKED
        ):
            raise ValueError("Only Grocy products can be annotated for Mise workflow review outside DEV mode")
        if container_policy not in PRODUCT_CONTAINER_POLICIES:
            raise ValueError("Unsupported container policy")
        if storage_behavior not in PRODUCT_STORAGE_BEHAVIORS:
            raise ValueError("Unsupported storage behavior")
        if meal_role not in PRODUCT_MEAL_ROLES:
            raise ValueError("Unsupported meal role")
        now = _utc_now()
        current = self.product_metadata.get(item_id, {})
        sync_result: dict[str, int] | None = None
        self.product_metadata[item_id] = {
            "item_id": item_id,
            "container_policy": container_policy,
            "storage_behavior": storage_behavior,
            "meal_role": meal_role,
            "available_in_mealie": bool(available_in_mealie),
            "created_at": current.get("created_at", now),
            "updated_at": now,
            "reviewed_at": now,
        }
        if (
            available_in_mealie
            and item.get("provider") == PROVIDER_GROCY
            and {PROVIDER_MEALIE, PROVIDER_GROCY} <= set(self.effective_catalog_providers())
        ):
            try:
                sync_result = await self._mealie_client().async_sync_grocy_products([item])
            except MealieCatalogError as err:
                raise ValueError("Mealie food sync is unavailable") from err
        self._add_log_entry(
            "Product metadata reviewed",
            f"{item['label']} Mise workflow metadata was updated.",
            {
                "item_id": item_id,
                "container_policy": container_policy,
                "storage_behavior": storage_behavior,
                "meal_role": meal_role,
                "available_in_mealie": bool(available_in_mealie),
                "mealie_sync": sync_result,
            },
        )
        await self.async_save()
        return self.product_metadata[item_id]

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
        now = _utc_now()
        self.locations[key] = {
            "id": f"location_{uuid4().hex}",
            "name": name,
            "location_type": "other",
            "area_id": None,
            "sensors": {},
            "monitoring": {},
            "created_at": now,
            "updated_at": now,
        }
        self._add_log_entry("Location created", f"{name} was added as an inventory location.", {"location": name})
        async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "location", key)
        if save:
            self.hass.async_create_task(self.async_save())
        return name

    async def async_create_location(self, name: str) -> None:
        await self.async_create_location_record(name=name)

    def location_for_id(self, location_id: str | None) -> dict[str, Any] | None:
        """Return a provider-owned storage location by stable ID, including The Void."""
        if location_id == VOID_LOCATION_ID:
            return {
                "id": VOID_LOCATION_ID,
                "name": VOID_LOCATION_NAME,
                "location_type": "system",
                "editable": False,
            }
        return next((location for location in self.storage_locations() if location.get("id") == location_id), None)

    def location_choices(self) -> list[dict[str, str]]:
        """Return selectable locations for the panel and M5Dial."""
        return [
            {"id": location["id"], "label": location["name"]}
            for location in self.storage_locations()
            if location.get("active", True)
        ]

    def location_health(self, location: dict[str, Any]) -> dict[str, Any]:
        """Summarize configured Home Assistant entities without controlling them."""
        sensors = location.get("sensors") or {}
        monitoring = location.get("monitoring") or {}
        readings: dict[str, Any] = {}
        problems: list[str] = []
        for role, entity_id in sensors.items():
            if not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            if state is None or state.state in {"unknown", "unavailable"}:
                readings[role] = {"entity_id": entity_id, "state": "unavailable"}
                problems.append(f"{role.replace('_', ' ')} unavailable")
            else:
                readings[role] = {"entity_id": entity_id, "state": state.state, "unit": state.attributes.get("unit_of_measurement")}
        temperature = readings.get("temperature", {}).get("state")
        if temperature not in (None, "unavailable"):
            try:
                value = float(temperature)
                minimum, maximum = monitoring.get("temperature_min"), monitoring.get("temperature_max")
                if minimum is not None and value < float(minimum):
                    problems.append("temperature below range")
                if maximum is not None and value > float(maximum):
                    problems.append("temperature above range")
            except (TypeError, ValueError):
                problems.append("temperature is not numeric")
        plug = readings.get("power_switch", {}).get("state")
        if monitoring.get("power_required") and plug not in (None, "on"):
            problems.append("appliance plug is off")
        status = "critical" if any("temperature" in issue or "plug" in issue for issue in problems) else "warning" if problems else ("not_configured" if not sensors else "ok")
        return {"status": status, "problems": problems, "readings": readings}

    def storage_attention_summary(self) -> dict[str, Any]:
        """Return automation-friendly storage and location health attention state."""
        active = self.active_containers()
        locations = self.storage_locations()
        health_by_id = {
            location["id"]: self.location_health(location)
            for location in locations
            if location.get("id")
        }
        containers_needing_location = [
            {
                "tag_id": container.get("tag_id"),
                "name": container.get("name") or self.default_container_name(container.get("tag_id", "")),
                "item_label": self.item_label_for_container(container),
                "location_id": container.get("location_id"),
                "location": container.get("location"),
            }
            for container in active
            if not container.get("location_id") or container.get("location_id") == VOID_LOCATION_ID
        ]
        unhealthy_locations = [
            {
                "location_id": location["id"],
                "name": location.get("name"),
                "location_type": location.get("location_type"),
                "status": health_by_id.get(location["id"], {}).get("status", "unknown"),
                "problems": health_by_id.get(location["id"], {}).get("problems", []),
            }
            for location in locations
            if health_by_id.get(location.get("id"), {}).get("status") in {"warning", "critical"}
        ]
        critical_locations = [
            {
                "location_id": location["location_id"],
                "name": location.get("name"),
                "problems": location.get("problems", []),
            }
            for location in unhealthy_locations
            if location.get("status") == "critical"
        ]
        warning_locations = [
            {
                "location_id": location["location_id"],
                "name": location.get("name"),
                "problems": location.get("problems", []),
            }
            for location in unhealthy_locations
            if location.get("status") == "warning"
        ]
        unhealthy_ids = {location["location_id"] for location in unhealthy_locations}
        prepared_inventory_at_risk = [
            {
                "tag_id": container.get("tag_id"),
                "name": container.get("name") or self.default_container_name(container.get("tag_id", "")),
                "item_label": self.item_label_for_container(container),
                "content_kind": container.get("content_kind"),
                "location_id": container.get("location_id"),
                "location": container.get("location"),
            }
            for container in active
            if container.get("content_kind") in {"recipe", "meal"}
            and (
                not container.get("location_id")
                or container.get("location_id") == VOID_LOCATION_ID
                or container.get("location_id") in unhealthy_ids
            )
        ]
        attention_count = (
            len(containers_needing_location)
            + len(unhealthy_locations)
            + len(prepared_inventory_at_risk)
        )
        worst_location = "critical" if any(item["status"] == "critical" for item in unhealthy_locations) else "warning" if unhealthy_locations else "ok"
        status = "critical" if worst_location == "critical" else "warning" if attention_count else "ok"
        return {
            "status": status,
            "status_label": self._storage_status_label(status, attention_count),
            "attention_count": attention_count,
            "containers_needing_location_count": len(containers_needing_location),
            "unhealthy_locations_count": len(unhealthy_locations),
            "critical_locations_count": len(critical_locations),
            "warning_locations_count": len(warning_locations),
            "prepared_inventory_at_risk_count": len(prepared_inventory_at_risk),
            "containers_needing_location": containers_needing_location[:12],
            "unhealthy_locations": unhealthy_locations[:12],
            "critical_locations": critical_locations[:12],
            "warning_locations": warning_locations[:12],
            "prepared_inventory_at_risk": prepared_inventory_at_risk[:12],
        }

    @staticmethod
    def _storage_status_label(status: str, attention_count: int) -> str:
        """Return the shared storage attention phrase used by sensors and panel."""
        if status == "critical":
            return "Storage attention critical"
        if attention_count:
            return "Storage attention needed"
        return "Storage automation clear"

    def resolve_location(self, location: str | None = None, location_id: str | None = None) -> dict[str, Any]:
        """Resolve a Grocy-owned user-selected location without allowing The Void as input."""
        if location_id:
            resolved = self.location_for_id(location_id)
            if not resolved or location_id == VOID_LOCATION_ID:
                raise ValueError("Unknown or protected location_id")
            return resolved
        if not (name := self._normalize_optional(location)):
            return self.location_for_id(VOID_LOCATION_ID)  # type: ignore[return-value]
        resolved = next(
            (candidate for candidate in self.storage_locations() if candidate.get("name", "").casefold() == name.casefold()),
            None,
        )
        if not resolved:
            raise ValueError("Unknown Grocy location")
        return resolved

    def resolve_sublocation(self, location: dict[str, Any], sublocation: str | None = None) -> str:
        """Return a valid shelf/drawer name for a resolved storage location."""
        name = self._normalize_optional(sublocation)
        if not name:
            return ""
        if location.get("id") == VOID_LOCATION_ID:
            raise ValueError("Choose a location before choosing a sublocation")
        configured = _normalize_sublocations(location.get("sublocations", []))
        if configured and name.casefold() not in {value.casefold() for value in configured}:
            raise ValueError("Unknown sublocation for selected location")
        return name

    async def async_create_location_record(
        self, *, name: str, location_type: str = "other", area_id: str | None = None,
        sublocations: list[str] | None = None,
        sensors: dict[str, str] | None = None, monitoring: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a local mocked storage location, or reject live provider-owned locations."""
        if not self.mock_catalog_enabled():
            self._ensure_write_mode()
            raise ValueError("Create storage locations in Grocy, then refresh Mise en Place Assistant")
        if not (name := self._normalize_optional(name)):
            raise ValueError("Location name is required")
        if location_type not in LOCATION_TYPES:
            raise ValueError("Unsupported location type")
        if any(location.get("name", "").casefold() == name.casefold() for location in self.storage_locations()):
            raise ValueError("Location already exists")

        now = _utc_now()
        location_id = f"mocked:location:{uuid4().hex}"
        self.data.setdefault("storage_locations", []).append(
            {"id": location_id, "name": name, "provider": PROVIDER_MOCKED, "active": True, "local": True}
        )
        self.locations[location_id] = {
            "id": location_id,
            "name": name,
            "location_type": location_type,
            "sublocations": _normalize_sublocations(sublocations),
            "area_id": self._normalize_optional(area_id),
            "sensors": dict(sensors or {}),
            "monitoring": dict(monitoring or {}),
            "created_at": now,
            "updated_at": now,
        }
        self._add_log_entry("Location created", f"{name} was added as an inventory location.", {"location_id": location_id})
        async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "location", location_id)
        await self.async_save()
        return self.location_for_id(location_id) or self.locations[location_id]

    async def async_update_location(self, location_id: str, **updates: Any) -> dict[str, Any]:
        if not self.mock_catalog_enabled():
            self._ensure_write_mode()
        location = self.location_for_id(location_id)
        if not location or location_id == VOID_LOCATION_ID:
            raise ValueError("Unknown or protected location_id")
        location_type = updates.get("location_type", location.get("location_type", "other"))
        if location_type not in LOCATION_TYPES:
            raise ValueError("Unsupported location type")
        if self.mock_catalog_enabled() and location.get("provider") == PROVIDER_MOCKED and location.get("local"):
            name = self._normalize_optional(updates.get("name"))
            if name and name != location.get("name"):
                if any(
                    candidate.get("id") != location_id and candidate.get("name", "").casefold() == name.casefold()
                    for candidate in self.storage_locations()
                ):
                    raise ValueError("Location already exists")
                for provider_location in self.data.get("storage_locations", []):
                    if isinstance(provider_location, dict) and provider_location.get("id") == location_id:
                        provider_location["name"] = name
                        break
        annotation = self.locations.get(location_id, {})
        now = _utc_now()
        self.locations[location_id] = {
            "id": location_id,
            **({"name": updates["name"]} if self.mock_catalog_enabled() and updates.get("name") else {}),
            "location_type": location_type,
            "sublocations": _normalize_sublocations(updates.get("sublocations", annotation.get("sublocations", []))),
            "area_id": self._normalize_optional(updates.get("area_id", annotation.get("area_id"))),
            "sensors": dict(updates.get("sensors", annotation.get("sensors", {}))),
            "monitoring": dict(updates.get("monitoring", annotation.get("monitoring", {}))),
            "created_at": annotation.get("created_at", now),
            "updated_at": now,
        }
        self._add_log_entry("Location annotated", f"{location['name']} monitoring metadata was updated.", {"location_id": location_id})
        await self.async_save()
        return self.location_for_id(location_id) or self.locations[location_id]

    async def async_delete_location(self, location_id: str) -> int:
        """Remove local HA annotations; Grocy owns storage-location deletion."""
        if not self.mock_catalog_enabled():
            self._ensure_write_mode()
        location = self.location_for_id(location_id)
        if not location or location_id == VOID_LOCATION_ID:
            raise ValueError("Unknown or protected location_id")
        if self.mock_catalog_enabled() and location.get("provider") == PROVIDER_MOCKED and location.get("local"):
            before = len(self.data.get("storage_locations", []))
            self.data["storage_locations"] = [
                provider_location
                for provider_location in self.data.get("storage_locations", [])
                if not (isinstance(provider_location, dict) and provider_location.get("id") == location_id)
            ]
            self.locations.pop(location_id, None)
            for container in self.containers.values():
                if container.get("location_id") == location_id:
                    container["location_id"] = VOID_LOCATION_ID
                    container["location"] = VOID_LOCATION_NAME
                    container["sublocation"] = ""
                    container["updated_at"] = _utc_now()
            removed = 1 if len(self.data["storage_locations"]) != before else 0
            self._add_log_entry("Location deleted", f"{location['name']} was removed as an inventory location.", {"location_id": location_id})
            await self.async_save()
            return removed
        removed = 1 if self.locations.pop(location_id, None) else 0
        self._add_log_entry("Location annotation removed", f"{location['name']} monitoring metadata was removed.", {"location_id": location_id})
        await self.async_save()
        return removed

    def enrolled_m5dial(self) -> dict[str, Any] | None:
        """Return the Home Assistant device selected as the M5Dial, if any."""
        return self.devices.get("m5dial")

    async def _async_apply_grocy_stock_replacement(
        self,
        before: dict[str, Any] | None,
        after: dict[str, Any],
    ) -> None:
        """Apply a staged container transaction to Grocy before local save."""
        if self.mock_catalog_enabled():
            return
        before_product = self.product_for_container(before or {})
        after_product = self.product_for_container(after)
        before_source = before_product.get("source") if before_product else {}
        after_source = after_product.get("source") if after_product else {}
        if before_source.get("provider") != PROVIDER_GROCY and after_source.get("provider") != PROVIDER_GROCY:
            return
        client = self._grocy_client()
        before_amount = float((before or {}).get("quantity", 0) or 0)
        after_amount = float(after.get("quantity", 0) or 0)
        before_location_id = (before or {}).get("location_id")
        after_location_id = after.get("location_id")
        note = f"Mise en Place Assistant container {after.get('tag_id') or ''}".strip()
        stock_changed = False
        stock_events: list[dict[str, Any]] = []
        if before_source != after_source and before_amount > 0 and after_amount > 0:
            raise ValueError("Empty a Grocy-backed container before changing its product")
        if before_source == after_source and before_location_id != after_location_id and before_amount > 0:
            raise ValueError("Empty a Grocy-backed container before moving it to another location")

        if before_source.get("provider") == PROVIDER_GROCY and before_amount > 0:
            attempted_quantity = before_amount
            try:
                if before_source != after_source:
                    await client.async_consume_stock(before_source["id"], before_amount, location_id=before_location_id, note=note)
                    stock_events.append(
                        {
                            "action": "consume",
                            "product_id": before_source["id"],
                            "label": (before_product or {}).get("label"),
                            "quantity": before_amount,
                            "location_id": before_location_id,
                        }
                    )
                    stock_changed = True
                elif after_amount < before_amount:
                    amount = before_amount - after_amount
                    attempted_quantity = amount
                    await client.async_consume_stock(before_source["id"], amount, location_id=before_location_id, note=note)
                    stock_events.append(
                        {
                            "action": "consume",
                            "product_id": before_source["id"],
                            "label": (before_product or {}).get("label"),
                            "quantity": amount,
                            "location_id": before_location_id,
                        }
                    )
                    stock_changed = True
            except GrocyCatalogError as err:
                self._add_log_entry(
                    "Grocy stock write failed",
                    f"Grocy rejected a stock decrease for {after.get('name') or after.get('tag_id') or 'container'}.",
                    {
                        "tag_id": after.get("tag_id"),
                        "operation": "consume",
                        "product": self.product_snapshot(before or {}),
                        "quantity": attempted_quantity,
                        "location_id": before_location_id,
                    },
                )
                await self.async_save(notify=False)
                raise ValueError("Grocy rejected the stock decrease") from err

        if after_source.get("provider") == PROVIDER_GROCY and after_amount > 0:
            attempted_quantity = after_amount
            try:
                if before_source != after_source:
                    await client.async_add_stock(
                        after_source["id"],
                        after_amount,
                        location_id=after_location_id,
                        note=note,
                        **self._grocy_stock_metadata(after),
                    )
                    stock_events.append(
                        {
                            "action": "add",
                            "product_id": after_source["id"],
                            "label": (after_product or {}).get("label"),
                            "quantity": after_amount,
                            "location_id": after_location_id,
                            "dates": self._grocy_stock_metadata(after),
                        }
                    )
                    stock_changed = True
                elif after_amount > before_amount:
                    amount = after_amount - before_amount
                    attempted_quantity = amount
                    await client.async_add_stock(
                        after_source["id"],
                        amount,
                        location_id=after_location_id,
                        note=note,
                        **self._grocy_stock_metadata(after),
                    )
                    stock_events.append(
                        {
                            "action": "add",
                            "product_id": after_source["id"],
                            "label": (after_product or {}).get("label"),
                            "quantity": amount,
                            "location_id": after_location_id,
                            "dates": self._grocy_stock_metadata(after),
                        }
                    )
                    stock_changed = True
            except GrocyCatalogError as err:
                self._add_log_entry(
                    "Grocy stock write failed",
                    f"Grocy rejected a stock increase for {after.get('name') or after.get('tag_id') or 'container'}.",
                    {
                        "tag_id": after.get("tag_id"),
                        "operation": "add",
                        "product": self.product_snapshot(after),
                        "quantity": attempted_quantity,
                        "location_id": after_location_id,
                        "dates": self._grocy_stock_metadata(after),
                    },
                )
                await self.async_save(notify=False)
                raise ValueError("Grocy rejected the stock increase") from err

        if stock_changed:
            try:
                self.data["stock"] = await client.async_fetch_stock()
            except GrocyCatalogError:
                _LOGGER.warning("Grocy accepted a stock mutation, but refreshed stock totals are unavailable")
            self._add_log_entry(
                "Grocy stock updated",
                f"Grocy stock was updated for {after.get('name') or after.get('tag_id') or 'container'}.",
                {
                    "tag_id": after.get("tag_id"),
                    "operations": stock_events,
                    "product": self.product_snapshot(after),
                    "dates": self._grocy_stock_metadata(after),
                },
            )

    @staticmethod
    def _grocy_stock_metadata(container: dict[str, Any]) -> dict[str, Any]:
        """Return optional Grocy stock fields that are meaningful on stock additions."""
        return {
            key: container[key]
            for key in ("best_before_date", "purchased_date", "opened_date", "price")
            if container.get(key) not in (None, "")
        }

    async def async_create_container(
        self,
        *,
        tag_id: str,
        name: str | None = None,
        quantity: int | float = 0,
        location: str | None = None,
        location_id: str | None = None,
        sublocation: str | None = None,
        unit: str = DEFAULT_UNIT,
        item_id: str | None = None,
        item_label: str | None = None,
        item_format: str | None = None,
        source_provider: str = "local",
        content_kind: str = "ingredient",
        classification: dict[str, str] | None = None,
        best_before_date: str | None = None,
        purchased_date: str | None = None,
        opened_date: str | None = None,
        price: int | float | None = None,
    ) -> None:
        self._ensure_write_mode(allow_dev_inventory=True)
        await self._async_create_container(
            tag_id=tag_id,
            name=name,
            quantity=quantity,
            location=location,
            location_id=location_id,
            sublocation=sublocation,
            unit=unit,
            item_id=item_id,
            item_label=item_label,
            item_format=item_format,
            source_provider=source_provider,
            content_kind=content_kind,
            classification=classification,
            best_before_date=best_before_date,
            purchased_date=purchased_date,
            opened_date=opened_date,
            price=price,
        )

    async def _async_create_container(
        self,
        *,
        tag_id: str,
        name: str | None = None,
        quantity: int | float = 0,
        location: str | None = None,
        location_id: str | None = None,
        sublocation: str | None = None,
        unit: str = DEFAULT_UNIT,
        item_id: str | None = None,
        item_label: str | None = None,
        item_format: str | None = None,
        source_provider: str = "local",
        content_kind: str = "ingredient",
        classification: dict[str, str] | None = None,
        best_before_date: str | None = None,
        purchased_date: str | None = None,
        opened_date: str | None = None,
        price: int | float | None = None,
    ) -> None:
        tag_id = self._normalize_tag_id(tag_id)
        old = self.containers.get(tag_id, {})
        quantity_data = normalize_quantity(quantity, unit)
        resolved_location = self.resolve_location(location, location_id)
        location = resolved_location["name"]
        sublocation = self.resolve_sublocation(resolved_location, sublocation)
        now = _utc_now()
        is_new = not old
        if content_kind not in {"ingredient", "recipe", "meal"}:
            raise ValueError("content_kind must be ingredient, recipe, or meal")
        product_id = self._resolve_product_id(
            item_id, item_label, item_format, unit, source_provider, classification
        )
        candidate = {
            "tag_id": tag_id,
            "name": self._normalize_optional(name) or old.get("name") or self.default_container_name(tag_id),
            "item_id": item_id,
            "item_label": item_label,
            "item_format": item_format,
            "product_id": product_id,
            "content_kind": content_kind,
            "archived": False,
            "archived_at": None,
            **quantity_data,
            "location": location,
            "location_id": resolved_location["id"],
            "sublocation": sublocation,
            "unit": unit or DEFAULT_UNIT,
            "created_at": old.get("created_at", now),
            "updated_at": now,
        }
        for key, value in (
            ("best_before_date", best_before_date),
            ("purchased_date", purchased_date),
            ("opened_date", opened_date),
            ("price", price),
        ):
            if value not in (None, ""):
                candidate[key] = value
            elif key in old:
                candidate[key] = old[key]
        await self._async_apply_grocy_stock_replacement(old, candidate)
        self.containers[tag_id] = candidate
        if is_new:
            async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "container", tag_id)
        if product_id:
            async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "product", product_id)
        self._add_log_entry(
            "Container created" if is_new else "Container refilled",
            f"{self.containers[tag_id]['name']} now contains {self.containers[tag_id]['item_label'] or 'nothing'} in {location or 'no location'}.",
            {"tag_id": tag_id, "quantity": quantity_data["quantity"], "unit": quantity_data["unit"], "canonical_quantity": quantity_data["canonical_quantity"], "canonical_unit": quantity_data["canonical_unit"], "location": location, "sublocation": sublocation,
             "product": self.product_snapshot(self.containers[tag_id])},
        )
        await self.async_save()

    @staticmethod
    def _recipe_classification(recipe: dict[str, Any]) -> dict[str, str]:
        tags = {str(tag).casefold() for tag in recipe.get("tags", [])}
        component = next((tag[14:] for tag in tags if tag.startswith("mpa:component:")), None)
        protein = next((tag[20:] for tag in tags if tag.startswith("mpa:primary-protein:")), None)
        if protein:
            protein = PROTEIN_GROUP_ALIASES.get(protein, protein)
        return {key: value for key, value in {"component": component, "primary_protein": protein}.items() if value}

    async def async_create_recipe_container(
        self, *, recipe_id: str, content_kind: str, tag_id: str, name: str | None = None,
        quantity: int | float = 0, location: str | None = None, location_id: str | None = None,
        sublocation: str | None = None,
    ) -> None:
        """Create a portion-counted recipe or ready-meal container."""
        self._ensure_write_mode(allow_dev_inventory=True)
        recipe = await self.async_recipe_item(recipe_id)
        await self._async_create_container(
            tag_id=tag_id, name=name, quantity=quantity, location=location, location_id=location_id,
            sublocation=sublocation,
            unit=recipe["unit"], item_id=recipe["id"], item_label=recipe["label"],
            item_format=recipe["format"], source_provider=self.recipe_provider_for_item(recipe),
            content_kind=content_kind, classification=self._recipe_classification(recipe),
        )

    async def async_seed_demo_data(self) -> int:
        """Add a bounded, repeatable set of containers for panel review.

        Demo tag IDs are deliberately stable, so a retried setup refreshes the
        same examples instead of accumulating duplicate stock.
        """
        foods = {item["id"]: item for item in self.catalog_items()}
        recipes = {item["id"]: item for item in self.recipe_items()}
        examples = (
            ("demo:spinach", "Produce bin", "mocked:baby-spinach", 180, "Fridge", "ingredient"),
            ("demo:eggs-low", "Egg carton", "mocked:eggs", 2, "Fridge", "ingredient"),
            ("demo:milk-empty", "Milk carton", "mocked:whole-milk", 0, "Fridge", "ingredient"),
            ("demo:rice", "Rice jar", "mocked:basmati-rice", 1200, "Pantry", "ingredient"),
            ("demo:coffee", "Coffee canister", "mocked:coffee", 350, "Pantry", "ingredient"),
            ("demo:peas", "Freezer peas", "mocked:frozen-peas", 600, "Freezer", "ingredient"),
            ("demo:curry", "Curry portions", "mocked:recipe:chicken-curry", 3, "Fridge", "meal"),
            ("demo:vegetables", "Roast vegetables", "mocked:recipe:roast-vegetables", 4, "Fridge", "meal"),
            ("demo:meal-rice", "Cooked rice", "mocked:recipe:rice", 1, "Fridge", "meal"),
            ("demo:lentil-loaf", "Lentil loaf", "mocked:recipe:lentil-loaf", 0, "Freezer", "recipe"),
        )
        created = 0
        for tag_id, name, item_id, quantity, location, content_kind in examples:
            item = foods.get(item_id) or recipes.get(item_id)
            if item is None:
                continue
            await self._async_create_container(
                tag_id=tag_id,
                name=name,
                quantity=quantity,
                location=location,
                unit=item["unit"],
                item_id=item["id"],
                item_label=item["label"],
                item_format=item["format"],
                source_provider=str(item.get("provider") or self.catalog_provider()),
                content_kind=content_kind,
                classification=self._recipe_classification(item) if item_id in recipes else None,
            )
            created += 1
        return created

    async def async_update_container(
        self,
        *,
        tag_id: str,
        quantity: int | float | None = None,
        delta: int | float | None = None,
        location: str | None = None,
        location_id: str | None = None,
        sublocation: str | None = None,
        name: str | None = None,
        unit: str | None = None,
        item_id: str | None = None,
        item_label: str | None = None,
        item_format: str | None = None,
        source_provider: str = "local",
        create_missing: bool = False,
        best_before_date: str | None = None,
        purchased_date: str | None = None,
        opened_date: str | None = None,
        price: int | float | None = None,
    ) -> None:
        self._ensure_write_mode(allow_dev_inventory=True)
        await self._async_update_container(
            tag_id=tag_id,
            quantity=quantity,
            delta=delta,
            location=location,
            location_id=location_id,
            sublocation=sublocation,
            name=name,
            unit=unit,
            item_id=item_id,
            item_label=item_label,
            item_format=item_format,
            source_provider=source_provider,
            create_missing=create_missing,
            best_before_date=best_before_date,
            purchased_date=purchased_date,
            opened_date=opened_date,
            price=price,
        )

    async def _async_update_container(
        self,
        *,
        tag_id: str,
        quantity: int | float | None = None,
        delta: int | float | None = None,
        location: str | None = None,
        location_id: str | None = None,
        sublocation: str | None = None,
        name: str | None = None,
        unit: str | None = None,
        item_id: str | None = None,
        item_label: str | None = None,
        item_format: str | None = None,
        source_provider: str = "local",
        create_missing: bool = False,
        best_before_date: str | None = None,
        purchased_date: str | None = None,
        opened_date: str | None = None,
        price: int | float | None = None,
    ) -> None:
        tag_id = self._normalize_tag_id(tag_id)
        if tag_id not in self.containers:
            if not create_missing:
                raise KeyError(tag_id)
            await self._async_create_container(tag_id=tag_id)

        container = self.containers[tag_id]
        if container.get("archived"):
            raise ValueError("Restore the container before updating it")
        before = dict(container)
        candidate = dict(container)
        display_unit = unit if unit is not None else candidate.get("display_unit", candidate.get("unit", DEFAULT_UNIT))
        if quantity is not None:
            candidate.update(normalize_quantity(quantity, display_unit))
        if delta is not None:
            # Deltas use the supplied unit, or the container's displayed unit.
            # A conversion is only performed inside that unit's own dimension.
            delta_data = normalize_quantity(abs(delta), display_unit)
            if not units_are_compatible(candidate.get("canonical_unit"), delta_data["canonical_unit"]):
                raise ValueError(
                    f"Cannot apply {display_unit} to a container measured in "
                    f"{candidate.get('canonical_unit', DEFAULT_UNIT)}"
                )
            canonical_quantity = max(
                0,
                float(candidate.get("canonical_quantity", candidate.get("quantity", 0)))
                + (-1 if delta < 0 else 1) * float(delta_data["canonical_quantity"]),
            )
            candidate.update(quantity_in_display_unit(canonical_quantity, display_unit))
        if unit is not None and quantity is None and delta is None:
            if not units_are_compatible(candidate.get("canonical_unit"), display_unit):
                raise ValueError(
                    f"Cannot change a container measured in {candidate.get('canonical_unit', DEFAULT_UNIT)} "
                    f"to {display_unit} without setting a new quantity"
                )
            candidate.update(
                quantity_in_display_unit(candidate.get("canonical_quantity", candidate.get("quantity", 0)), display_unit)
            )
        if location is not None or location_id is not None:
            resolved_location = self.resolve_location(location, location_id)
            candidate["location"] = resolved_location["name"]
            candidate["location_id"] = resolved_location["id"]
            candidate["sublocation"] = self.resolve_sublocation(resolved_location, sublocation)
        elif sublocation is not None:
            candidate["sublocation"] = self.resolve_sublocation(
                self.resolve_location(location_id=candidate.get("location_id")),
                sublocation,
            )
        if name is not None:
            candidate["name"] = self._normalize_optional(name) or self.default_container_name(tag_id)
        if item_id is not None:
            candidate["item_id"] = item_id
        if item_label is not None:
            candidate["item_label"] = item_label
        if item_format is not None:
            candidate["item_format"] = item_format
        if item_id is not None or item_label is not None or item_format is not None:
            candidate["product_id"] = self._resolve_product_id(
                candidate.get("item_id"), candidate.get("item_label"),
                candidate.get("item_format"), candidate.get("unit"),
                source_provider,
            )
        for key, value in (
            ("best_before_date", best_before_date),
            ("purchased_date", purchased_date),
            ("opened_date", opened_date),
            ("price", price),
        ):
            if value not in (None, ""):
                candidate[key] = value
        candidate["updated_at"] = _utc_now()
        await self._async_apply_grocy_stock_replacement(before, candidate)
        self.containers[tag_id] = candidate
        if candidate.get("product_id"):
            async_dispatcher_send(self.hass, SIGNAL_MISE_EN_PLACE_ASSISTANT_ENTITY_ADDED, "product", candidate["product_id"])
        self._add_log_entry(
            "Container updated",
            f"{candidate['name']} inventory was updated.",
            {"tag_id": tag_id, "old_quantity": before.get("quantity"), "quantity": candidate.get("quantity"),
             "product": self.product_snapshot(candidate)},
        )
        await self.async_save()


    async def async_scan_container(self, *, tag_id: str, quantity: int | float | None = None, mode: str = "set") -> None:
        delta = float(quantity) if quantity is not None and mode == "add" else None
        if quantity is not None and mode == "remove":
            delta = -float(quantity)
        set_quantity = float(quantity) if quantity is not None and mode == "set" else None
        await self.async_update_container(tag_id=tag_id, quantity=set_quantity, delta=delta)

    async def async_clear_container(self, tag_id: str) -> None:
        """Empty a known container without deleting its identity or product attribution."""
        self._ensure_write_mode(allow_dev_inventory=True)
        await self._async_update_container(tag_id=tag_id, quantity=0)

    async def async_archive_container(self, tag_id: str) -> None:
        """Retire an empty container from active inventory without deleting history."""
        self._ensure_write_mode(allow_dev_inventory=True)
        tag_id = self._normalize_tag_id(tag_id)
        if tag_id not in self.containers:
            raise KeyError(tag_id)
        container = self.containers[tag_id]
        if container.get("archived"):
            return
        if float(container.get("canonical_quantity", container.get("quantity", 0)) or 0) > 0:
            raise ValueError("Clear the container before archiving it")
        now = _utc_now()
        container["archived"] = True
        container["archived_at"] = now
        container["updated_at"] = now
        self._add_log_entry("Container archived", f"{container['name']} was removed from active rotation.", {"tag_id": tag_id})
        await self.async_save()

    async def async_restore_container(self, tag_id: str) -> None:
        """Return an archived container to active rotation."""
        self._ensure_write_mode(allow_dev_inventory=True)
        tag_id = self._normalize_tag_id(tag_id)
        if tag_id not in self.containers:
            raise KeyError(tag_id)
        container = self.containers[tag_id]
        if not container.get("archived"):
            return
        now = _utc_now()
        container["archived"] = False
        container["restored_at"] = now
        container["updated_at"] = now
        self._add_log_entry("Container restored", f"{container['name']} returned to active rotation.", {"tag_id": tag_id})
        await self.async_save()

    async def async_simulate_crud(self) -> dict[str, Any]:
        """Exercise local DEV-mode CRUD paths without touching live providers."""
        if not self.mock_catalog_enabled():
            raise ValueError("CRUD simulation is available only in DEV mode")
        base_location = next(
            (location for location in self.storage_locations() if location.get("id") != VOID_LOCATION_ID),
            None,
        )
        if base_location is None:
            raise ValueError("CRUD simulation needs at least one storage location")

        tag_id = "dev:crud-simulation"
        item = await self.async_catalog_item("mocked:baby-spinach")
        for location in list(self.storage_locations()):
            if (
                location.get("provider") == PROVIDER_MOCKED
                and location.get("local")
                and location.get("name") in {"DEV CRUD Simulation", "DEV CRUD Simulation Updated"}
            ):
                await self.async_delete_location(location["id"])
        created_location = await self.async_create_location_record(
            name="DEV CRUD Simulation",
            location_type="fridge",
            sublocations=["Top shelf", "Bottom drawer"],
        )
        location_id = created_location["id"]
        steps: list[str] = ["location.create"]
        await self.async_update_location(
            location_id,
            name="DEV CRUD Simulation Updated",
            location_type="fridge",
            sublocations=["Top shelf", "Bottom drawer", "Door bin"],
        )
        steps.append("location.update")
        if not self.location_for_id(location_id):
            raise ValueError("CRUD simulation failed to read created location")
        steps.append("location.read")

        await self.async_create_container(
            tag_id=tag_id,
            name="DEV CRUD Tub",
            quantity=1,
            location_id=location_id,
            sublocation="Top shelf",
            unit=item["unit"],
            item_id=item["id"],
            item_label=item["label"],
            item_format=item["format"],
            source_provider=item.get("provider", PROVIDER_MOCKED),
        )
        steps.append("container.create")
        if tag_id not in self.containers:
            raise ValueError("CRUD simulation failed to read created container")
        steps.append("container.read")
        await self.async_update_container(
            tag_id=tag_id,
            quantity=2,
            name="DEV CRUD Tub Updated",
            location_id=location_id,
            sublocation="Bottom drawer",
        )
        steps.append("container.update")
        await self.async_clear_container(tag_id)
        steps.append("container.clear")
        await self.async_archive_container(tag_id)
        steps.append("container.archive")
        await self.async_restore_container(tag_id)
        steps.append("container.restore")
        await self.async_update_container(
            tag_id=tag_id,
            location_id=base_location["id"],
            sublocation="",
        )
        steps.append("container.move")
        await self.async_delete_location(location_id)
        steps.append("location.delete")

        self._add_log_entry(
            "DEV CRUD simulation completed",
            "Local mock location and container CRUD paths completed.",
            {"steps": steps, "tag_id": tag_id},
        )
        await self.async_save()
        return {"steps": steps, "tag_id": tag_id}

    def _kitchenowl_client(self) -> KitchenOwlShoppingClient:
        """Return a KitchenOwl client from validated config-entry data."""
        url = self.entry.options.get(CONF_KITCHENOWL_URL, self.entry.data.get(CONF_KITCHENOWL_URL, ""))
        token = self.entry.options.get(CONF_KITCHENOWL_TOKEN, self.entry.data.get(CONF_KITCHENOWL_TOKEN, ""))
        list_id = self.entry.options.get(
            CONF_KITCHENOWL_SHOPPING_LIST_ID,
            self.entry.data.get(CONF_KITCHENOWL_SHOPPING_LIST_ID),
        )
        if url and "://" not in url:
            url = f"http://{url}"
        if not url or not token or not list_id:
            raise KitchenOwlError("KitchenOwl URL, token, and shopping list ID must be configured")
        return KitchenOwlShoppingClient(self.hass, url, token, int(list_id))

    async def async_add_to_shopping_list(
        self,
        name: str,
        description: str = "",
        *,
        item_id: str | None = None,
        quantity: int | float = 1,
    ) -> dict[str, Any]:
        """Send one explicit item request to the configured shopping-list target."""
        item_name = self._normalize_optional(name)
        item = await self.async_catalog_item(item_id) if item_id else None
        item_name = item_name or (item or {}).get("label")
        if not item_name:
            raise ValueError("Shopping item name is required")
        self._ensure_write_mode()
        source_provider = (item or {}).get("provider")
        target = self._shopping_target_for_product(source_provider)
        if target == PROVIDER_GROCY and not item:
            raise ValueError("Choose a Grocy catalog product before sending an item to Grocy shopping")
        if target == PROVIDER_GROCY and source_provider != PROVIDER_GROCY:
            raise ValueError("Only Grocy catalog products can be sent to Grocy shopping")
        if target == PROVIDER_GROCY and item:
            try:
                result = await self._grocy_client().async_add_product_to_shopping_list(
                    item["id"],
                    quantity,
                    note=description,
                )
            except GrocyCatalogError as err:
                raise ValueError("Grocy shopping list is unavailable") from err
            provider = PROVIDER_GROCY
        else:
            try:
                result = await self._kitchenowl_client().async_add_item(item_name, description)
            except KitchenOwlError:
                raise
            provider = PROVIDER_KITCHENOWL
        self._add_log_entry(
            "Shopping item added",
            f"{item_name} was sent to {provider}.",
            {
                "provider": provider,
                "item_count": 1,
                "labels": [item_name],
                "item": item_name,
                "item_id": item_id,
                "quantity": quantity,
                "description": description,
                "reason": "explicit_shopping_request",
            },
        )
        await self.async_save()
        return result

    async def async_add_empty_containers_to_shopping_list(self) -> int:
        """Send unique product labels from empty containers to the configured shopping target."""
        requests: dict[tuple[str, str | None], dict[str, Any]] = {}
        for container in self.active_containers():
            if float(container.get("canonical_quantity", container.get("quantity", 0))) != 0:
                continue
            product = self.product_for_container(container) or {}
            source = product.get("source") or {}
            label = self.item_label_for_container(container)
            if not label:
                continue
            key = (label.casefold(), source.get("id"))
            request = requests.setdefault(
                key,
                {
                    "label": label,
                    "source_provider": source.get("provider"),
                    "source_id": source.get("id"),
                    "containers": [],
                    "locations": set(),
                    "unit": container.get("unit") or DEFAULT_UNIT,
                    "reason": "empty_container_refill",
                },
            )
            request["containers"].append(container.get("name") or "Container")
            if container.get("location"):
                request["locations"].add(container["location"])
        if not requests:
            return 0
        self._ensure_write_mode()
        sent = 0
        queued: list[dict[str, Any]] = []
        kitchenowl_client: KitchenOwlShoppingClient | None = None
        grocy_client: GrocyCatalogClient | None = None
        for request in requests.values():
            label = request["label"]
            source_provider = request["source_provider"]
            source_id = request["source_id"]
            target = self._shopping_target_for_product(source_provider)
            description = self._empty_container_shopping_description(request)
            if target == PROVIDER_GROCY and source_provider == PROVIDER_GROCY and source_id:
                grocy_client = grocy_client or self._grocy_client()
                await grocy_client.async_add_product_to_shopping_list(
                    source_id,
                    note=description,
                )
                provider = PROVIDER_GROCY
            else:
                kitchenowl_client = kitchenowl_client or self._kitchenowl_client()
                await kitchenowl_client.async_add_item(label, description)
                provider = PROVIDER_KITCHENOWL
            sent += 1
            queued.append(
                {
                    "label": label,
                    "provider": provider,
                    "source_provider": source_provider,
                    "source_id": source_id,
                    "containers": list(request["containers"]),
                    "locations": sorted(request["locations"]),
                    "reason": request["reason"],
                    "description": description,
                }
            )
        self._add_log_entry(
            "Empty containers queued",
            f"{sent} empty-container refill items were sent to shopping providers.",
            {
                "provider": self.shopping_list_provider(),
                "item_count": sent,
                "labels": [item["label"] for item in queued],
                "targets": {provider: sum(1 for item in queued if item["provider"] == provider) for provider in {item["provider"] for item in queued}},
                "reason": "empty_container_refill",
                "items": queued,
            },
        )
        await self.async_save()
        return sent

    @staticmethod
    def _empty_container_shopping_description(request: dict[str, Any]) -> str:
        """Return a provider note explaining why an empty container was queued."""
        containers = ", ".join(request.get("containers") or ["container"])
        locations = ", ".join(request.get("locations") or ["unknown location"])
        unit = request.get("unit") or DEFAULT_UNIT
        return (
            "Refill empty Mise container"
            f"; product={request['label']}"
            f"; containers={containers}"
            f"; unit={unit}"
            f"; locations={locations}"
            "; reason=empty_container_refill"
        )

    async def async_add_missing_products_to_shopping_list(self) -> dict[str, Any]:
        """Ask Grocy to add products below minimum stock to its shopping list."""
        self._ensure_write_mode()
        if self.shopping_list_provider() == PROVIDER_KITCHENOWL:
            raise ValueError("Grocy minimum-stock shopping requires Grocy or automatic shopping-list mode")
        try:
            result = await self._grocy_client().async_add_missing_products_to_shopping_list()
        except GrocyCatalogError as err:
            raise ValueError("Grocy shopping list is unavailable") from err
        self._add_log_entry(
            "Missing products queued",
            "Grocy added products below minimum stock to its shopping list.",
            {
                "provider": PROVIDER_GROCY,
                "item_count": result.get("count") if isinstance(result, dict) else None,
                "reason": "grocy_minimum_stock",
            },
        )
        await self.async_save()
        return result

    def _shopping_target_for_product(self, source_provider: str | None) -> str:
        """Choose the shopping target for a product-backed or free-text request."""
        preference = self.shopping_list_provider()
        if preference != SHOPPING_LIST_PROVIDER_AUTO:
            return preference
        if source_provider == PROVIDER_GROCY:
            return PROVIDER_GROCY
        if self.kitchenowl_configured():
            return PROVIDER_KITCHENOWL
        return PROVIDER_GROCY

    def shopping_workflow_status(self) -> dict[str, Any]:
        """Return dashboard-facing shopping workflow ownership and capability status."""
        preference = self.shopping_list_provider()
        return {
            "provider": preference,
            "grocy_configured": self.grocy_configured(),
            "kitchenowl_configured": self.kitchenowl_configured(),
            "product_backed_target": self._shopping_target_for_product(PROVIDER_GROCY),
            "free_text_target": self._shopping_target_for_product(None),
            "grocy_minimum_stock": preference in {SHOPPING_LIST_PROVIDER_AUTO, PROVIDER_GROCY},
        }

    async def async_save(self, *, notify: bool = True) -> None:
        await self._store.async_save(self.data)
        if notify:
            for listener in list(self._listeners):
                listener()
            self.hass.bus.async_fire(EVENT_MISE_EN_PLACE_ASSISTANT_UPDATED, {})

    def item_totals(self, *, include_empty: bool = True) -> dict[str, dict[str, Any]]:
        """Return product totals from Grocy stock when Grocy owns the product."""
        totals: dict[str, dict[str, Any]] = {
            key: {
                "product_id": key, "item_id": item.get("source", {}).get("id"), "label": item.get("label") or key,
                "unit": item.get("unit") or DEFAULT_UNIT, "quantity": 0,
                "quantities": {},
                "containers": 0, "locations": {},
            }
            for key, item in self.products.items()
        } if include_empty else {}
        stock_by_source = {row.get("id"): row for row in self.data.get("stock", []) if isinstance(row, dict)}
        for product_id, product in self.products.items():
            source = product.get("source") or {}
            if source.get("provider") != PROVIDER_GROCY:
                continue
            stock = stock_by_source.get(source.get("id"))
            if not stock and not include_empty:
                continue
            total = totals.setdefault(
                product_id,
                {
                    "product_id": product_id,
                    "item_id": source.get("id"),
                    "label": product.get("label") or product_id,
                    "unit": product.get("unit") or DEFAULT_UNIT,
                    "quantity": 0,
                    "quantities": {},
                    "containers": 0,
                    "locations": {},
                },
            )
            quantity = stock.get("quantity", 0) if stock else 0
            total.update(
                {
                    "unit": product.get("unit") or DEFAULT_UNIT,
                    "quantity": quantity,
                    "quantities": {product.get("unit") or DEFAULT_UNIT: quantity},
                    "source": "grocy",
                }
            )
        for container in self.active_containers():
            product_id = container.get("product_id")
            if not product_id:
                continue
            product = self.products.get(product_id, {})
            if (product.get("source") or {}).get("provider") == PROVIDER_GROCY:
                if product_id in totals:
                    totals[product_id]["containers"] = totals[product_id].get("containers", 0) + 1
                continue
            if float(container.get("canonical_quantity", container.get("quantity", 0))) <= 0:
                continue
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
        for container in self.active_containers():
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
        if product and (product.get("source") or {}).get("provider") in {PROVIDER_GROCY, PROVIDER_MEALIE, PROVIDER_MOCKED}:
            return product.get("label") or container.get("item_label") or "No current item"
        return container.get("item_label") or "No current item"

    def product_snapshot(self, container: dict[str, Any]) -> dict[str, Any] | None:
        """Return the immutable product attribution to embed in a log entry."""
        product = self.product_for_container(container)
        if not product:
            return None
        return {"product_id": product["id"], "label": product["label"], "source": dict(product.get("source") or {})}

    def location_count(self, location_key: str) -> int:
        location = self.locations.get(location_key) or self.location_for_id(location_key)
        if not location:
            return 0
        return sum(1 for container in self.active_containers() if container.get("location_id") == location["id"])

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
