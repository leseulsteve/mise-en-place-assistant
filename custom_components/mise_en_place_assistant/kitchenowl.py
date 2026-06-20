"""Small, bounded KitchenOwl shopping-list client."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class KitchenOwlError(Exception):
    """Raised when KitchenOwl cannot complete a shopping-list operation."""


def validate_kitchenowl_url(value: str) -> str:
    """Validate and normalize a user-configured KitchenOwl base URL."""
    url = str(value).strip().rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("KitchenOwl URL must be an http(s) URL without embedded credentials")
    try:
        parsed.port
    except ValueError as err:
        raise ValueError("KitchenOwl URL must include a valid port") from err
    return url


class KitchenOwlShoppingClient:
    """Write explicit shopping-list requests to KitchenOwl."""

    def __init__(self, hass: HomeAssistant, base_url: str, token: str, shopping_list_id: int) -> None:
        self._session = async_get_clientsession(hass)
        self._base_url = validate_kitchenowl_url(base_url)
        self._token = token.strip()
        self._shopping_list_id = int(shopping_list_id)

    async def async_test_connection(self) -> None:
        """Verify that KitchenOwl accepts the configured token."""
        if not self._token:
            raise KitchenOwlError("KitchenOwl token is missing")
        try:
            async with self._session.head(
                f"{self._base_url}/api/user",
                headers=self._headers,
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise KitchenOwlError("KitchenOwl is unavailable") from err

    async def async_add_item(self, name: str, description: str = "") -> dict[str, Any]:
        """Add one item to the configured KitchenOwl shopping list by name."""
        if not self._token:
            raise KitchenOwlError("KitchenOwl token is missing")
        item_name = str(name).strip()
        if not item_name:
            raise KitchenOwlError("KitchenOwl shopping item name is required")
        try:
            async with self._session.post(
                f"{self._base_url}/api/shoppinglist/{self._shopping_list_id}/add-item-by-name",
                headers=self._headers,
                json={"name": item_name, "description": str(description).strip()},
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise KitchenOwlError("KitchenOwl shopping list is unavailable") from err

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
