"""Pint-backed quantity normalization for local inventory.

Pint owns physical-unit parsing, dimensionality, and conversion. This module
only defines inventory policy: canonical storage units, familiar aliases, and
the deliberate boundary around product-specific package/count units.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pint import UnitRegistry
from pint.errors import DimensionalityError, UndefinedUnitError


class UnitNormalizationError(ValueError):
    """Raised when a supplied quantity cannot be represented safely."""


_UNITS = UnitRegistry(non_int_type=Decimal)
# These are real, interchangeable item counts. Packages, jars, and servings
# intentionally remain product-specific units and are not defined here.
_UNITS.define("each = [inventory_count]")
_UNITS.define("item = each")
_UNITS.define("items = each")
_UNITS.define("piece = each")
_UNITS.define("pieces = each")

_ALIASES = {
    "fl oz": "fluid_ounce",
    "fl. oz": "fluid_ounce",
    "fluid ounce": "fluid_ounce",
    "fluid ounces": "fluid_ounce",
}
_CANONICAL_UNITS = {
    "mass": "gram",
    "volume": "milliliter",
    "count": "each",
}


def normalize_quantity(quantity: Any, unit: str | None) -> dict[str, Any]:
    """Return JSON-safe display and canonical fields for a quantity input."""
    display_quantity = _decimal(quantity, "quantity")
    if not display_quantity.is_finite() or display_quantity < 0:
        raise UnitNormalizationError("quantity must be a finite non-negative number")

    display_unit = " ".join(str(unit or "items").strip().split()) or "items"
    try:
        parsed = _UNITS.Quantity(display_quantity, _ALIASES.get(display_unit.casefold(), display_unit))
        dimension, canonical_unit = _canonical_unit(parsed)
        canonical_quantity = parsed.to(canonical_unit).magnitude
    except UndefinedUnitError:
        # A provider's unknown unit is retained faithfully, but it only
        # reconciles with the same normalized spelling until catalog metadata
        # supplies a product-specific conversion.
        dimension = "custom"
        canonical_unit = display_unit.casefold()
        canonical_quantity = display_quantity

    return {
        "quantity": _json_number(display_quantity),
        "unit": display_unit,
        "display_quantity": _json_number(display_quantity),
        "display_unit": display_unit,
        "canonical_quantity": _json_number(canonical_quantity),
        "canonical_unit": canonical_unit,
        "unit_dimension": dimension,
    }


def quantity_in_display_unit(canonical_quantity: Any, display_unit: str | None) -> dict[str, Any]:
    """Represent a compatible canonical quantity in its chosen display unit."""
    target = normalize_quantity(0, display_unit)
    canonical = _decimal(canonical_quantity, "canonical quantity")
    if target["unit_dimension"] == "custom":
        return normalize_quantity(canonical, target["display_unit"])
    try:
        displayed = _UNITS.Quantity(canonical, target["canonical_unit"]).to(
            _ALIASES.get(target["display_unit"].casefold(), target["display_unit"])
        )
    except DimensionalityError as err:
        raise UnitNormalizationError("display unit is incompatible with canonical quantity") from err
    return normalize_quantity(displayed.magnitude, target["display_unit"])


def units_are_compatible(first_unit: str | None, second_unit: str | None) -> bool:
    """Return whether two units reconcile without product-specific knowledge."""
    first = normalize_quantity(0, first_unit)
    second = normalize_quantity(0, second_unit)
    return (
        first["unit_dimension"] == second["unit_dimension"]
        and first["canonical_unit"] == second["canonical_unit"]
    )


def _canonical_unit(quantity) -> tuple[str, str]:
    if quantity.check("[mass]"):
        return "mass", _CANONICAL_UNITS["mass"]
    if quantity.check("[length] ** 3"):
        return "volume", _CANONICAL_UNITS["volume"]
    if quantity.check("[inventory_count]"):
        return "count", _CANONICAL_UNITS["count"]
    # Pint handles many more physical dimensions than inventory totals should
    # silently combine. Preserve them as separate custom strings for now.
    raise UndefinedUnitError(str(quantity.units))


def _decimal(value: Any, label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as err:
        raise UnitNormalizationError(f"{label} must be a number") from err


def _json_number(value: Decimal) -> int | float:
    """Store exact whole values as ints and fractional values as JSON numbers."""
    if value == value.to_integral_value():
        return int(value)
    return float(value)
