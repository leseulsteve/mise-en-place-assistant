"""Small, bounded Mealie food-catalog client."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    """Read foods from Mealie without changing its data."""

    def __init__(self, hass: HomeAssistant, base_url: str, token: str) -> None:
        self._session = async_get_clientsession(hass)
        self._base_url = validate_mealie_url(base_url)
        self._token = token.strip()

    async def async_fetch_foods(self) -> list[dict[str, str]]:
        """Return normalized food records from Mealie's documented foods endpoint."""
        if not self._token:
            raise MealieCatalogError("Mealie API token is missing")
        try:
            async with self._session.get(
                f"{self._base_url}/api/foods",
                params={"page": 1, "perPage": -1, "orderBy": "name", "orderDirection": "asc"},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                payload: Any = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise MealieCatalogError("Mealie food catalog is unavailable") from err

        records = payload.get("data", payload) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise MealieCatalogError("Mealie returned an invalid food catalog")

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
                    "unit": "items",
                }
            )
        if not foods:
            raise MealieCatalogError("Mealie has no usable foods")
        return foods
