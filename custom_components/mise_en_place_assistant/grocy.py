"""Small, bounded Grocy product-catalog and stock client."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .units import normalized_inventory_unit

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class GrocyCatalogError(Exception):
    """Raised when Grocy cannot provide a usable catalog or stock operation."""


def validate_grocy_url(value: str) -> str:
    """Validate and normalize a user-configured Grocy base URL."""
    url = str(value).strip().rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Grocy URL must be an http(s) URL without embedded credentials")
    try:
        parsed.port
    except ValueError as err:
        raise ValueError("Grocy URL must include a valid port") from err
    return url


class GrocyCatalogClient:
    """Read products from Grocy and write inventory mutations to Grocy."""

    def __init__(self, hass: HomeAssistant, base_url: str, token: str) -> None:
        self._session = async_get_clientsession(hass)
        self._base_url = validate_grocy_url(base_url)
        self._token = token.strip()

    async def async_fetch_products(self) -> list[dict[str, str]]:
        """Return Grocy products as Mise en Place ingredient catalog records."""
        if not self._token:
            raise GrocyCatalogError("Grocy API key is missing")
        try:
            products_payload, units_payload = await self._async_get("objects/products"), await self._async_get(
                "objects/quantity_units"
            )
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise GrocyCatalogError("Grocy product catalog is unavailable") from err
        products = self._records(products_payload)
        units = self._records(units_payload)
        if not isinstance(products, list) or not isinstance(units, list):
            raise GrocyCatalogError("Grocy returned an invalid product catalog")
        unit_lookup = self._unit_lookup(units)
        records: list[dict[str, str]] = []
        for product in products:
            if not isinstance(product, dict):
                continue
            product_id = str(product.get("id") or "").strip()
            label = str(product.get("name") or "").strip()
            if not product_id or not label:
                continue
            records.append(
                {
                    "id": f"grocy:{product_id}",
                    "label": label,
                    "format": str(product.get("description") or "").strip(),
                    "unit": self._product_unit(product, unit_lookup),
                    "provider": "grocy",
                }
            )
        if not records:
            raise GrocyCatalogError("Grocy has no usable products")
        return records

    async def async_fetch_stock(self) -> list[dict[str, Any]]:
        """Return Grocy stock amounts keyed by Grocy product id."""
        if not self._token:
            raise GrocyCatalogError("Grocy API key is missing")
        try:
            stock_payload = await self._async_get("stock")
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise GrocyCatalogError("Grocy stock is unavailable") from err
        stock_rows = self._records(stock_payload)
        if not isinstance(stock_rows, list):
            raise GrocyCatalogError("Grocy returned invalid stock data")
        records: list[dict[str, Any]] = []
        for row in stock_rows:
            if not isinstance(row, dict):
                continue
            product_id = str(row.get("product_id") or row.get("id") or "").strip()
            if not product_id:
                product = row.get("product")
                if isinstance(product, dict):
                    product_id = str(product.get("id") or "").strip()
            if not product_id:
                continue
            amount = row.get("amount")
            if amount is None:
                amount = row.get("stock_amount")
            try:
                amount = float(amount or 0)
            except (TypeError, ValueError):
                continue
            record: dict[str, Any] = {
                "id": f"grocy:{product_id}",
                "quantity": int(amount) if amount.is_integer() else amount,
            }
            for key in ("best_before_date", "next_best_before_date", "due_date", "next_due_date"):
                if row.get(key):
                    record[key] = row[key]
            records.append(record)
        return records

    async def async_fetch_locations(self) -> list[dict[str, Any]]:
        """Return Grocy storage locations as inventory-location records."""
        if not self._token:
            raise GrocyCatalogError("Grocy API key is missing")
        try:
            locations_payload = await self._async_get("objects/locations")
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise GrocyCatalogError("Grocy locations are unavailable") from err
        locations = self._records(locations_payload)
        if not isinstance(locations, list):
            raise GrocyCatalogError("Grocy returned invalid locations")
        records: list[dict[str, Any]] = []
        for location in locations:
            if not isinstance(location, dict):
                continue
            location_id = str(location.get("id") or "").strip()
            name = str(location.get("name") or "").strip()
            if not location_id or not name:
                continue
            records.append(
                {
                    "id": f"grocy:{location_id}",
                    "name": name,
                    "provider": "grocy",
                    "active": str(location.get("active", "1")) not in {"0", "false", "False"},
                }
            )
        return records

    async def async_add_stock(
        self,
        product_id: str,
        amount: int | float,
        *,
        location_id: str | None = None,
        note: str = "",
        best_before_date: str | None = None,
        purchased_date: str | None = None,
        opened_date: str | None = None,
        price: int | float | None = None,
    ) -> dict[str, Any]:
        """Increase Grocy stock for a product."""
        grocy_id = self._grocy_product_id(product_id)
        payload = {
            "amount": amount,
            "transaction_type": "purchase",
            "note": note,
        }
        if location_id:
            payload["location_id"] = self._grocy_location_id(location_id)
        for key, value in (
            ("best_before_date", best_before_date),
            ("purchased_date", purchased_date),
            ("opened_date", opened_date),
            ("price", price),
        ):
            if value not in (None, ""):
                payload[key] = value
        return await self._async_post(f"stock/products/{grocy_id}/add", payload)

    async def async_consume_stock(
        self,
        product_id: str,
        amount: int | float,
        *,
        location_id: str | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        """Decrease Grocy stock for a product."""
        grocy_id = self._grocy_product_id(product_id)
        payload = {
            "amount": amount,
            "transaction_type": "consume",
            "spoiled": False,
            "note": note,
        }
        if location_id:
            payload["location_id"] = self._grocy_location_id(location_id)
        return await self._async_post(f"stock/products/{grocy_id}/consume", payload)

    async def async_inventory_stock(self, product_id: str, amount: int | float, *, note: str = "") -> dict[str, Any]:
        """Set Grocy's inventory amount for a product."""
        grocy_id = self._grocy_product_id(product_id)
        return await self._async_post(
            f"stock/products/{grocy_id}/inventory",
            {
                "new_amount": amount,
                "note": note,
            },
        )

    async def async_add_product_to_shopping_list(
        self,
        product_id: str,
        amount: int | float = 1,
        *,
        note: str = "",
    ) -> dict[str, Any]:
        """Add one Grocy product to Grocy's shopping list."""
        grocy_id = self._grocy_product_id(product_id)
        payload = {
            "product_id": int(grocy_id) if grocy_id.isdecimal() else grocy_id,
            "amount": amount,
            "note": note,
        }
        try:
            return await self._async_post("stock/shoppinglist/add-product", payload)
        except GrocyCatalogError:
            return await self._async_post("objects/shopping_list", payload)

    async def async_add_missing_products_to_shopping_list(self) -> dict[str, Any]:
        """Ask Grocy to queue products below their configured minimum stock."""
        return await self._async_post("stock/shoppinglist/add-missing-products", {})

    async def _async_get(self, resource: str) -> Any:
        """Fetch one Grocy API resource with a bounded timeout."""
        async with self._session.get(
            f"{self._base_url}/api/{resource}",
            headers={"GROCY-API-KEY": self._token},
            timeout=_REQUEST_TIMEOUT,
        ) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    async def _async_post(self, resource: str, payload: dict[str, Any]) -> Any:
        """Write one Grocy API resource with a bounded timeout."""
        if not self._token:
            raise GrocyCatalogError("Grocy API key is missing")
        try:
            async with self._session.post(
                f"{self._base_url}/api/{resource}",
                headers={"GROCY-API-KEY": self._token},
                json=payload,
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                if response.status == 204:
                    return {}
                return await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise GrocyCatalogError("Grocy stock is unavailable") from err

    @staticmethod
    def _records(payload: Any) -> Any:
        return payload.get("data", payload) if isinstance(payload, dict) else payload

    @staticmethod
    def _unit_lookup(units: Iterable[Any]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for unit in units:
            if not isinstance(unit, dict):
                continue
            display_unit = next(
                (
                    normal
                    for candidate in (unit.get("name"), unit.get("name_plural"))
                    if (normal := normalized_inventory_unit(candidate))
                ),
                None,
            )
            if not display_unit:
                continue
            for key in (unit.get("id"), unit.get("name"), unit.get("name_plural")):
                key = str(key or "").strip()
                if key:
                    lookup[key.casefold()] = display_unit
        return lookup

    @staticmethod
    def _product_unit(product: dict[str, Any], unit_lookup: dict[str, str]) -> str:
        for key in ("qu_id_stock", "qu_id_purchase"):
            value = str(product.get(key) or "").strip()
            if value and (unit := unit_lookup.get(value.casefold())):
                return unit
        return "items"

    @staticmethod
    def _grocy_product_id(product_id: str) -> str:
        product_id = str(product_id or "").strip()
        if product_id.startswith("grocy:"):
            product_id = product_id.removeprefix("grocy:")
        if not product_id:
            raise GrocyCatalogError("Grocy product id is required")
        return product_id

    @staticmethod
    def _grocy_location_id(location_id: str) -> str:
        location_id = str(location_id or "").strip()
        if location_id.startswith("grocy:"):
            location_id = location_id.removeprefix("grocy:")
        if not location_id:
            raise GrocyCatalogError("Grocy location id is required")
        return location_id
