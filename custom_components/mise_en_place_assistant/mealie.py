"""Small, bounded Mealie food-catalog client."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .units import normalized_inventory_unit

_LOGGER = logging.getLogger(__name__)
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class MealieCatalogError(Exception):
    """Raised when Mealie cannot provide a usable catalog."""


def validate_mealie_url(value: str) -> str:
    """Validate and normalize a user-configured Mealie base URL."""
    url = str(value).strip().rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Mealie URL must be an http(s) URL without embedded credentials")
    try:
        port = parsed.port
    except ValueError as err:
        raise ValueError("Mealie URL must include a valid port") from err
    return url


class MealieCatalogClient:
    """Read foods and recipes from Mealie without changing its data."""

    def __init__(self, hass: HomeAssistant, base_url: str, token: str) -> None:
        self._session = async_get_clientsession(hass)
        self._base_url = validate_mealie_url(base_url)
        self._token = token.strip()

    async def async_fetch_foods(self) -> list[dict[str, str]]:
        """Return food records with safe, provider-configured unit defaults.

        Mealie foods do not have a native default-unit field. A food can opt
        in via its API extras using ``mise_en_place_unit`` (a unit name or ID)
        or ``mise_en_place_unit_id`` (a unit ID).
        """
        if not self._token:
            raise MealieCatalogError("Mealie API token is missing")
        try:
            foods_payload = await self._async_get_all("foods")
            units_payload = await self._async_get_all("units")
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise MealieCatalogError("Mealie food catalog is unavailable") from err

        records = self._records(foods_payload)
        if not isinstance(records, list):
            raise MealieCatalogError("Mealie returned an invalid food catalog")
        units = self._records(units_payload)
        if not isinstance(units, list):
            raise MealieCatalogError("Mealie returned an invalid unit catalog")
        unit_lookup = self._unit_lookup(units)

        foods: list[dict[str, str]] = []
        for food in records:
            if not isinstance(food, dict):
                continue
            food_id = str(food.get("id") or "").strip()
            label = str(food.get("name") or food.get("label") or "").strip()
            if not food_id or not label:
                continue
            foods.append(
                {
                    "id": food_id,
                    "label": label,
                    "format": str(food.get("description") or "").strip(),
                    "unit": self._food_default_unit(food, unit_lookup),
                }
            )
        if not foods:
            raise MealieCatalogError("Mealie has no usable foods")
        return foods

    async def async_fetch_recipes(self) -> list[dict[str, Any]]:
        """Return recipes eligible for prepared-container inventory.

        Classification deliberately comes only from Mealie tags.  A recipe
        without an ``mpa:component:*`` tag remains usable as a recipe, but is
        excluded from prep totals until the household classifies it.
        """
        if not self._token:
            raise MealieCatalogError("Mealie API token is missing")
        try:
            payload = await self._async_get_all("recipes")
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise MealieCatalogError("Mealie recipe catalog is unavailable") from err
        records = self._records(payload)
        if not isinstance(records, list):
            raise MealieCatalogError("Mealie returned an invalid recipe catalog")

        recipes: list[dict[str, Any]] = []
        for recipe in records:
            if not isinstance(recipe, dict):
                continue
            recipe_id = str(recipe.get("id") or "").strip()
            label = str(recipe.get("name") or "").strip()
            if not recipe_id or not label:
                continue
            tags = sorted(
                {
                    str(tag.get("name") or "").strip()
                    for tag in recipe.get("tags", [])
                    if isinstance(tag, dict) and str(tag.get("name") or "").strip()
                },
                key=str.casefold,
            )
            categories = sorted(
                {
                    str(category.get("name") or "").strip()
                    for category in (recipe.get("recipeCategory") or recipe.get("categories") or [])
                    if isinstance(category, dict) and str(category.get("name") or "").strip()
                },
                key=str.casefold,
            )
            recipes.append(
                {
                    "id": recipe_id,
                    "label": label,
                    "format": str(recipe.get("description") or "").strip(),
                    "unit": self._recipe_yield_unit(recipe),
                    "tags": tags,
                    "categories": categories,
                }
            )
        return recipes

    @staticmethod
    def _recipe_yield_unit(recipe: dict[str, Any]) -> str:
        """Keep Mealie's yield wording instead of imposing a portion unit."""
        extras = recipe.get("extras")
        if isinstance(extras, dict):
            value = extras.get("mise_en_place_unit")
            if isinstance(value, str) and value.strip():
                return value.strip()
        yield_text = str(recipe.get("recipeYield") or "").strip()
        # Typical Mealie yields are e.g. "4 servings". Store the count unit,
        # while the complete original yield stays available as recipe metadata.
        if match := re.match(r"^\s*\d+(?:[.,]\d+)?\s+(.+?)\s*$", yield_text):
            return match.group(1)
        return "servings"

    async def _async_get_all(self, resource: str) -> Any:
        """Fetch one Mealie catalog resource with a bounded timeout."""
        async with self._session.get(
            f"{self._base_url}/api/{resource}",
            params={"page": 1, "perPage": -1, "orderBy": "name", "orderDirection": "asc"},
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=_REQUEST_TIMEOUT,
        ) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    @staticmethod
    def _records(payload: Any) -> Any:
        """Unwrap Mealie's paginated response without accepting malformed data."""
        return payload.get("data", payload) if isinstance(payload, dict) else payload

    @staticmethod
    def _unit_lookup(units: Iterable[Any]) -> dict[str, str]:
        """Map Mealie unit IDs and names to Pint-supported display units."""
        lookup: dict[str, str] = {}
        for unit in units:
            if not isinstance(unit, dict):
                continue
            candidates = (
                unit.get("abbreviation") if unit.get("useAbbreviation") else None,
                unit.get("name"),
                unit.get("abbreviation"),
                unit.get("standardUnit"),
            )
            display_unit = next(
                (normal for candidate in candidates if (normal := normalized_inventory_unit(candidate))),
                None,
            )
            if not display_unit:
                continue
            for key in (
                unit.get("id"), unit.get("name"), unit.get("pluralName"),
                unit.get("abbreviation"), unit.get("pluralAbbreviation"),
            ):
                if isinstance(key, str) and (key := key.strip()):
                    lookup[key.casefold()] = display_unit
        return lookup

    @staticmethod
    def _food_default_unit(food: dict[str, Any], unit_lookup: dict[str, str]) -> str:
        """Resolve an explicit Mealie food-extra unit, otherwise retain items."""
        extras = food.get("extras")
        if not isinstance(extras, dict):
            return "items"
        for key in ("mise_en_place_unit_id", "mise_en_place_unit"):
            value = extras.get(key)
            if not isinstance(value, str):
                continue
            if unit := unit_lookup.get(value.strip().casefold()):
                return unit
            if unit := normalized_inventory_unit(value):
                return unit
        return "items"
