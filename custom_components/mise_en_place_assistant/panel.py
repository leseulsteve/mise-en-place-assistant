"""Sidebar panel for Mise en Place Assistant."""

from __future__ import annotations

from datetime import date, timedelta
import logging
from pathlib import Path
from typing import Any

import voluptuous as vol
from aiohttp import web

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar

from .const import CONF_PREP_CALENDAR_ENTITY_ID, DOMAIN, PANEL_URL_PATH, VOID_LOCATION_ID
from .planning import date_in_range, format_quantities, freshness_status, recipe_suggestions_data, word_tokens
from .store import MiseEnPlaceAssistantInventory

_LOGGER = logging.getLogger(__name__)

PANEL_COMPONENT_NAME = "mise_en_place_assistant-panel"
PANEL_MODULE_URL = "/api/mise_en_place_assistant/panel.js"
PANEL_FRONTEND_PATH = Path(__file__).with_name("panel_frontend.js")
MEAL_PREP_CONTAINER_TYPES = [
    "small square",
    "medium square",
    "large square",
    "small round",
    "medium round",
    "large round",
    "small bag",
    "medium bag",
    "large bag",
    "jar",
    "bottle",
]


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the Mise en Place Assistant sidebar panel, frontend module, and API views."""
    _LOGGER.debug(
        "Registering sidebar panel: path=%s component=%s module=%s",
        PANEL_URL_PATH,
        PANEL_COMPONENT_NAME,
        PANEL_MODULE_URL,
    )
    hass.http.register_view(MiseEnPlaceAssistantPanelModuleView())
    websocket_api.async_register_command(hass, websocket_overview)
    websocket_api.async_register_command(hass, websocket_tv_dinner_plan)
    try:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name=PANEL_COMPONENT_NAME,
            sidebar_title="Mise en Place Assistant",
            sidebar_icon="mdi:package-variant-closed",
            module_url=PANEL_MODULE_URL,
            config={"domain": DOMAIN},
            embed_iframe=False,
            trust_external=False,
            require_admin=False,
        )
    except (TypeError, ValueError):
        _LOGGER.exception(
            "Could not register sidebar panel: path=%s component=%s module=%s",
            PANEL_URL_PATH,
            PANEL_COMPONENT_NAME,
            PANEL_MODULE_URL,
        )
        raise
    _LOGGER.info("Registered Mise en Place Assistant sidebar panel: path=%s", PANEL_URL_PATH)


def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the Mise en Place Assistant sidebar panel."""
    _LOGGER.debug("Unregistering sidebar panel: path=%s", PANEL_URL_PATH)
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    _LOGGER.info("Unregistered Mise en Place Assistant sidebar panel: path=%s", PANEL_URL_PATH)


class MiseEnPlaceAssistantPanelModuleView(HomeAssistantView):
    """Serve the Mise en Place Assistant panel frontend module."""

    url = PANEL_MODULE_URL
    name = "api:mise_en_place_assistant:panel:js"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Return the panel JavaScript module."""
        hass: HomeAssistant = request.app["hass"]
        _LOGGER.debug("Serving sidebar panel module: url=%s", PANEL_MODULE_URL)
        try:
            content = await hass.async_add_executor_job(
                PANEL_FRONTEND_PATH.read_text,
                "utf-8",
            )
        except OSError:
            _LOGGER.exception(
                "Could not read sidebar panel module: path=%s", PANEL_FRONTEND_PATH
            )
            raise web.HTTPServiceUnavailable(
                reason="Mise en Place Assistant panel module is unavailable"
            )
        _LOGGER.debug(
            "Served sidebar panel module: url=%s bytes=%d",
            PANEL_MODULE_URL,
            len(content.encode("utf-8")),
        )
        return web.Response(
            text=content,
            content_type="text/javascript",
            headers={"Cache-Control": "no-store"},
        )


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "mise_en_place_assistant/overview",
        vol.Optional("meal_count", default=1): vol.Coerce(int),
    }
)
def websocket_overview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return Mise en Place Assistant overview data to the authenticated frontend."""
    _LOGGER.debug("Received sidebar overview WebSocket request")
    try:
        manager = _manager(hass)
        data = _overview_data(manager, meal_count=msg.get("meal_count", 1))
    except (KeyError, StopIteration, TypeError, ValueError):
        _LOGGER.exception("Could not build sidebar overview response")
        connection.send_error(
            msg["id"],
            "overview_unavailable",
            "Mise en Place Assistant overview is unavailable",
        )
        return
    _LOGGER.debug(
        "Sending sidebar overview response: containers=%d locations=%d items=%d logbook=%d",
        data["summary"]["containers"],
        data["summary"]["locations"],
        data["summary"]["items"],
        len(data["logbook"]),
    )
    connection.send_result(msg["id"], data)


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "mise_en_place_assistant/tv_dinner_plan",
        vol.Optional("meal_count", default=1): vol.Coerce(int),
    }
)
def websocket_tv_dinner_plan(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return a random complete-meal assignment for the TV dinner tool."""
    try:
        plan = _manager(hass).tv_dinner_plan(msg.get("meal_count", 1))
    except (KeyError, StopIteration, TypeError, ValueError):
        _LOGGER.exception("Could not build TV dinner plan response")
        connection.send_error(
            msg["id"],
            "tv_dinner_plan_unavailable",
            "TV dinner planning is unavailable",
        )
        return
    connection.send_result(msg["id"], plan)


def _manager(hass: HomeAssistant) -> MiseEnPlaceAssistantInventory:
    """Return the first loaded Mise en Place Assistant manager."""
    return next(iter(hass.data[DOMAIN].values()))


def _overview_data(manager: MiseEnPlaceAssistantInventory, meal_count: int = 1) -> dict[str, Any]:
    """Build practical overview data for the panel."""
    active_containers = manager.active_containers()
    containers = sorted(
        active_containers,
        key=lambda container: container.get("updated_at") or "",
        reverse=True,
    )
    areas = ar.async_get(manager.hass)
    area_entries = (
        areas.async_list_areas()
        if hasattr(areas, "async_list_areas")
        else getattr(areas, "areas", {}).values()
    )
    area_options = [
        {"id": area.id, "name": area.name, "icon": getattr(area, "icon", None)}
        for area in sorted(area_entries, key=lambda area: area.name.casefold())
    ]
    entity_options = _entity_options(manager.hass)
    locations = []
    for location in manager.storage_locations():
        area = areas.async_get_area(location.get("area_id")) if location.get("area_id") else None
        locations.append(
            {
                **location,
                "containers": manager.location_count(location["id"]),
                "area_name": area.name if area else None,
                "area_icon": getattr(area, "icon", None) if area else None,
                "health": manager.location_health(location),
            }
        )
    void_count = manager.location_count(VOID_LOCATION_ID)
    if void_count:
        locations.append(
            {
                "id": VOID_LOCATION_ID,
                "name": "The Void",
                "location_type": "system",
                "editable": False,
                "containers": void_count,
                "health": {
                    "status": "warning",
                    "problems": ["Containers need a location"],
                    "readings": {},
                },
            }
        )
    empty_containers = [
        _container_summary(container, manager)
        for container in containers
        if float(container.get("canonical_quantity", container.get("quantity", 0))) == 0
    ]
    low_containers = [
        _container_summary(container, manager)
        for container in containers
        if 0 < float(container.get("canonical_quantity", container.get("quantity", 0))) <= 2
    ]
    item_totals = sorted(
        manager.item_totals(include_empty=False).values(), key=lambda item: item["label"].casefold()
    )
    item_totals = _enriched_item_totals(item_totals, containers, manager)
    foods = manager.catalog_items()
    recipes = manager.recipe_items()
    product_attention = manager.product_attention_items()
    storage_attention = manager.storage_attention_summary()
    health_counts: dict[str, int] = {"ok": 0, "warning": 0, "critical": 0, "unknown": 0}
    for location in locations:
        status = location.get("health", {}).get("status") or "unknown"
        health_counts[status if status in health_counts else "unknown"] += 1
    shopping_status = manager.shopping_workflow_status()
    readiness = _readiness_data(
        containers=containers,
        empty_containers=empty_containers,
        item_totals=item_totals,
        meal_inventory=manager.meal_inventory(),
        product_attention=product_attention,
        locations=locations,
        logbook=manager.logbook,
    )
    planning_comparison = _planning_comparison_data(
        containers=containers,
        products=manager.products,
        meal_inventory=manager.meal_inventory(),
        item_totals=item_totals,
        logbook=manager.logbook,
    )
    complete_meal_plan = manager.complete_meal_plan(meal_count)
    recipe_suggestions = recipe_suggestions_data(
        recipes=recipes,
        item_totals=item_totals,
        containers=containers,
        log_for=lambda recipe: _log_summary(
            _related_log(manager.logbook, recipe.get("label") or "", "recipe", "stock")
        ),
    )
    meal_prep = _meal_prep_data(
        hass=manager.hass,
        manager=manager,
        containers=containers,
        complete_meal_plan=complete_meal_plan,
        readiness=readiness,
        shopping=shopping_status,
    )
    suggested_actions = _suggested_actions_data(
        containers=containers,
        empty_containers=empty_containers,
        product_attention=product_attention,
        readiness=readiness,
        shopping=shopping_status,
        storage_attention=storage_attention,
        logbook=manager.logbook,
    )

    return {
        "summary": {
            "containers": len(containers),
            "locations": len(locations),
            "items": len(item_totals),
            "empty": len(empty_containers),
            "low": len(low_containers),
            "product_attention": len(product_attention),
            "foods": len(foods),
            "recipes": len(recipes),
            "recipe_suggestions": len(recipe_suggestions),
            "ready": len(readiness["ready"]),
            "missing": len(readiness["missing"]),
            "unassigned": len(readiness["unassigned"]),
            "stale": len(readiness["stale"]),
            "location_at_risk": len(readiness["location_at_risk"]),
        },
        "containers": [_container_summary(container, manager) for container in containers],
        "items": item_totals,
        "foods": foods,
        "product_attention": product_attention,
        "recipes": recipes,
        "meal_inventory": manager.meal_inventory(),
        "complete_meal_plan": complete_meal_plan,
        "recipe_suggestions": recipe_suggestions,
        "meal_prep": meal_prep,
        "readiness": readiness,
        "planning_comparison": planning_comparison,
        "suggested_actions": suggested_actions,
        "shopping": shopping_status,
        "storage_attention": storage_attention,
        "operations": {
            "catalog_providers": manager.effective_catalog_providers(),
            "shopping_provider": manager.shopping_list_provider(),
            "dev_mode": manager.mock_catalog_enabled(),
            "health": health_counts,
            "attention_total": len(product_attention) + len(empty_containers) + len(low_containers) + storage_attention["attention_count"],
        },
        "areas": area_options,
        "entities": entity_options,
        "locations": locations,
        "empty_containers": empty_containers[:8],
        "low_containers": low_containers[:8],
        "logbook": list(reversed(manager.logbook[-50:])),
    }


def _entity_options(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return entity choices the panel can use in storage monitoring forms."""
    options = []
    for state in hass.states.async_all():
        domain = state.entity_id.split(".", 1)[0]
        if domain not in {"binary_sensor", "sensor", "switch"}:
            continue
        name = state.attributes.get("friendly_name") or state.name or state.entity_id
        options.append(
            {
                "entity_id": state.entity_id,
                "domain": domain,
                "name": str(name),
            }
        )
    return sorted(options, key=lambda entity: (entity["domain"], entity["name"].casefold(), entity["entity_id"]))


def _calendar_options(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return Home Assistant calendar entities the panel can use for prep sessions."""
    calendars: list[dict[str, Any]] = []
    for state in hass.states.async_all("calendar"):
        attrs = state.attributes
        calendars.append(
            {
                "entity_id": state.entity_id,
                "name": str(attrs.get("friendly_name") or state.name or state.entity_id),
                "state": state.state,
                "message": attrs.get("message") or "",
                "start_date": attrs.get("start_date") or "",
                "end_date": attrs.get("end_date") or "",
                "start_time": attrs.get("start_time") or "",
                "end_time": attrs.get("end_time") or "",
            }
        )
    return sorted(calendars, key=lambda entity: (entity["name"].casefold(), entity["entity_id"]))


def _meal_prep_data(
    *,
    hass: HomeAssistant,
    manager: MiseEnPlaceAssistantInventory,
    containers: list[dict[str, Any]],
    complete_meal_plan: dict[str, Any],
    readiness: dict[str, Any],
    shopping: dict[str, Any],
) -> dict[str, Any]:
    """Build a provider-backed meal-prep session preview for the panel."""
    meal_count = max(1, int(complete_meal_plan.get("meal_count") or 1))
    calendar_options = _calendar_options(hass)
    prep_calendar_entity_id = manager.entry.options.get(
        CONF_PREP_CALENDAR_ENTITY_ID,
        manager.entry.data.get(CONF_PREP_CALENDAR_ENTITY_ID, ""),
    )
    calendar_events = [
        calendar
        for calendar in calendar_options
        if calendar.get("state") == "on" or calendar.get("message")
    ][:6]
    sessions = _prep_session_rows(manager.prep_sessions())
    storage_plan = _meal_prep_storage_plan(complete_meal_plan)
    required_containers: dict[str, int] = {}
    for row in storage_plan:
        container_type = row["container_type"]
        required_containers[container_type] = required_containers.get(container_type, 0) + int(row["count"])
    available_containers = _available_container_type_counts(containers)
    container_plan = []
    for container_type in MEAL_PREP_CONTAINER_TYPES:
        needed = required_containers.get(container_type, 0)
        available = available_containers.get(container_type, 0)
        container_plan.append(
            {
                "type": container_type,
                "needed": needed,
                "available": available,
                "missing": max(0, needed - available),
                "status": "ready" if needed <= available else "missing",
            }
        )
    for container_type in sorted(set(required_containers) - set(MEAL_PREP_CONTAINER_TYPES)):
        needed = required_containers[container_type]
        available = available_containers.get(container_type, 0)
        container_plan.append(
            {
                "type": container_type,
                "needed": needed,
                "available": available,
                "missing": max(0, needed - available),
                "status": "ready" if needed <= available else "missing",
            }
        )
    missing_containers = sum(row["missing"] for row in container_plan)
    missing_ingredients = len(readiness.get("missing") or [])
    status = "ready"
    if missing_containers or missing_ingredients or complete_meal_plan.get("status") == "short":
        status = "missing items"
    return {
        "status": status,
        "meal_count": meal_count,
        "calendar_entities": calendar_options,
        "prep_calendar_entity_id": prep_calendar_entity_id,
        "calendar_events": calendar_events,
        "sessions": sessions,
        "storage_plan": storage_plan,
        "container_plan": container_plan,
        "required_container_types": MEAL_PREP_CONTAINER_TYPES,
        "provider_roles": {
            "schedule": "Home Assistant calendar",
            "recipes": "Mealie",
            "stock": "Grocy",
            "shopping": _shopping_target_summary(shopping, "missing_products"),
            "storage": "Grocy storage locations + Mise container tags",
        },
        "clone_templates": [
            {
                "id": "current_complete_meals",
                "name": f"{meal_count} complete meals",
                "source": "Mealie complete-meal preview",
                "keeps": [
                    "recipes",
                    "servings",
                    "storage plan",
                    "container plan",
                    "checklist",
                    "notes",
                ],
            }
        ],
        "checklist": [
            "Schedule the prep block in the configured Home Assistant calendar",
            "Queue missing ingredients through Grocy or the configured shopping provider",
            "Pull storage containers by type",
            "Wash or free any missing containers",
            "Clear Grocy-backed fridge/freezer locations for finished portions",
            "Label containers with destination and eat-by date",
        ],
    }


def _prep_session_rows(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return recent and upcoming prep sessions for the mini calendar."""
    today = date.today().isoformat()
    rows = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        start = str(session.get("start_date_time") or "")
        rows.append(
            {
                "id": session.get("id") or "",
                "calendar_entity_id": session.get("calendar_entity_id") or "",
                "summary": session.get("summary") or "Meal prep session",
                "start_date_time": start,
                "end_date_time": session.get("end_date_time") or "",
                "description": session.get("description") or "",
                "recipes": session.get("recipes") if isinstance(session.get("recipes"), list) else [],
                "status": "past" if start[:10] and start[:10] < today else "upcoming",
            }
        )
    past = [row for row in rows if row["status"] == "past"]
    upcoming = [row for row in rows if row["status"] != "past"]
    past = sorted(past, key=lambda row: row["start_date_time"], reverse=True)[:4]
    upcoming = sorted(upcoming, key=lambda row: row["start_date_time"])[:8]
    return sorted(past + upcoming, key=lambda row: row["start_date_time"] or "")


def _meal_prep_storage_plan(complete_meal_plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Return container-oriented storage rows for a complete meal preview."""
    meal_count = max(1, int(complete_meal_plan.get("meal_count") or 1))
    rows = [
        {
            "label": "Complete meal portions",
            "count": meal_count,
            "container_type": "medium square",
            "destination": "fridge",
            "eat_by": "next 3-4 days",
            "note": "One assembled meal per container",
        }
    ]
    role_types = {
        "veggie": "small square",
        "starch": "small square",
        "protein": "medium square",
    }
    for role, items in (complete_meal_plan.get("uses") or {}).items():
        if not items:
            continue
        labels = ", ".join(str(item.get("label") or item.get("name") or role) for item in items[:2])
        remaining = len(items) - 2
        if remaining > 0:
            labels = f"{labels} + {remaining} more"
        rows.append(
            {
                "label": f"{role.title()} staging",
                "count": 1,
                "container_type": role_types.get(role, "medium square"),
                "destination": "fridge/freezer",
                "eat_by": "session dependent",
                "note": labels,
            }
        )
    return rows


def _available_container_type_counts(containers: list[dict[str, Any]]) -> dict[str, int]:
    """Count empty reusable containers by normalized storage type."""
    counts: dict[str, int] = {}
    for container in containers:
        if _as_float(container.get("canonical_quantity", container.get("quantity", 0))) != 0:
            continue
        container_type = _container_type(container)
        counts[container_type] = counts.get(container_type, 0) + 1
    return counts


def _container_type(container: dict[str, Any]) -> str:
    """Infer a stable container type from provider metadata or display names."""
    explicit = str(
        container.get("container_type")
        or container.get("storage_container_type")
        or container.get("format")
        or ""
    ).strip().casefold().replace("_", " ").replace("-", " ")
    haystack = " ".join(
        str(value or "")
        for value in (explicit, container.get("name"), container.get("item_label"))
    ).casefold().replace("_", " ").replace("-", " ")
    for container_type in MEAL_PREP_CONTAINER_TYPES:
        if container_type in haystack:
            return container_type
    if "bag" in haystack:
        if "large" in haystack:
            return "large bag"
        if "medium" in haystack:
            return "medium bag"
        return "small bag"
    if "jar" in haystack:
        return "jar"
    if "bottle" in haystack:
        return "bottle"
    if "round" in haystack:
        if "large" in haystack:
            return "large round"
        if "medium" in haystack:
            return "medium round"
        return "small round"
    if "square" in haystack or "container" in haystack or "tub" in haystack:
        if "large" in haystack:
            return "large square"
        if "small" in haystack:
            return "small square"
        return "medium square"
    return "unspecified"


def _container_summary(container: dict[str, Any], manager: MiseEnPlaceAssistantInventory | None = None) -> dict[str, Any]:
    """Return display-safe container data."""
    product = manager.product_for_container(container) if manager else None
    return {
        "tag_id": container.get("tag_id"),
        "name": container.get("name") or "Container",
        "product_id": container.get("product_id"),
        "state": container.get("state") or "active",
        "item_label": manager.item_label_for_container(container) if manager else container.get("item_label") or "No current item",
        "format": container.get("item_format") or "",
        "quantity": container.get("display_quantity", container.get("quantity", 0)),
        "unit": container.get("unit") or "items",
        "canonical_quantity": container.get("canonical_quantity", container.get("quantity", 0)),
        "canonical_unit": container.get("canonical_unit", container.get("unit")) or "items",
        "location_id": container.get("location_id") or "",
        "location": container.get("location") or "Unassigned",
        "sublocation": container.get("sublocation") or "",
        "content_kind": container.get("content_kind") or "empty",
        "best_before_date": container.get("best_before_date") or "",
        "purchased_date": container.get("purchased_date") or "",
        "opened_date": container.get("opened_date") or "",
        "updated_at": container.get("updated_at") or "",
        "created_at": container.get("created_at") or "",
        "deleted_at": container.get("deleted_at") or "",
        "recipe": _recipe_summary(container, product, manager),
    }


def _recipe_summary(
    container: dict[str, Any],
    product: dict[str, Any] | None,
    manager: MiseEnPlaceAssistantInventory | None,
) -> dict[str, Any] | None:
    """Return Mealie recipe metadata for recipe-backed containers."""
    if container.get("content_kind") not in {"recipe", "meal"} or not product:
        return None
    source = product.get("source") or {}
    source_id = source.get("id")
    recipe = next(
        (item for item in manager.recipe_items() if item.get("id") == source_id),
        {},
    ) if manager and source_id else {}
    classification = product.get("classification") or {}
    return {
        "id": source_id or "",
        "provider": source.get("provider") or "",
        "label": product.get("label") or container.get("item_label") or "",
        "yield_unit": recipe.get("unit") or product.get("unit") or container.get("unit") or "items",
        "tags": recipe.get("tags") or [],
        "categories": recipe.get("categories") or [],
        "component": classification.get("component") or "",
        "primary_protein": classification.get("primary_protein") or "",
        "meal_component_role": classification.get("meal_component_role") or "",
        "meal_component_family": classification.get("meal_component_family") or "",
        "meal_component_detail": classification.get("meal_component_detail") or "",
    }


def _enriched_item_totals(
    item_totals: list[dict[str, Any]],
    containers: list[dict[str, Any]],
    manager: MiseEnPlaceAssistantInventory,
) -> list[dict[str, Any]]:
    """Attach matching Mise containers, freshness dates, and recent stock writes to product rows."""
    by_product: dict[str, list[dict[str, Any]]] = {}
    for container in containers:
        if container.get("product_id"):
            by_product.setdefault(container["product_id"], []).append(container)
    enriched: list[dict[str, Any]] = []
    for item in item_totals:
        row = dict(item)
        related = by_product.get(item.get("product_id"), [])
        row["physical_containers"] = [_container_summary(container, manager) for container in related[:6]]
        row["freshness_dates"] = _product_freshness_dates(related)
        row["last_stock_log"] = _log_summary(
            _related_log(
                manager.logbook,
                item.get("label") or "",
                item.get("product_id") or "",
                item.get("item_id") or "",
                "Grocy stock",
                "stock",
            )
        )
        enriched.append(row)
    return enriched


def _product_freshness_dates(containers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return dated stock metadata already accepted by container services."""
    dates = []
    for container in containers:
        values = {
            "best_before_date": container.get("best_before_date"),
            "purchased_date": container.get("purchased_date"),
            "opened_date": container.get("opened_date"),
            "price": container.get("price"),
        }
        if any(value not in (None, "") for value in values.values()):
            dates.append({"container": container.get("name") or "Container", **values})
    return dates[:6]


def _readiness_data(
    *,
    containers: list[dict[str, Any]],
    empty_containers: list[dict[str, Any]],
    item_totals: list[dict[str, Any]],
    meal_inventory: dict[str, Any],
    product_attention: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    logbook: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return dashboard-ready recommendation groups from existing provider data."""
    recent_log = _recent_provider_log(logbook)
    ready_components = [
        _readiness_item(
            entry["component"],
            _format_quantities(entry.get("quantities", {})),
            "Prepared component exists in Mise inventory",
            status="ok",
            log=_related_log(logbook, entry["component"], *entry.get("recipes", {}).keys()),
        )
        for entry in (meal_inventory.get("components") or [])
    ]
    stocked_products = [
        _readiness_item(
            item["label"],
            f"{item.get('quantity')} {item.get('unit') or ''}".strip(),
            "Grocy-backed product has stock",
            status="ok",
            log=_related_log(logbook, item["label"], "stock", "Grocy"),
        )
        for item in item_totals
        if item.get("source") == "grocy" and _as_float(item.get("quantity")) > 0
    ]
    missing = [
        _readiness_item(
            item["label"],
            f"{item.get('quantity', 0)} {item.get('unit') or ''}".strip() if item.get("has_stock") else "No stock",
            ", ".join(item.get("reasons") or ["Needs review"]),
            status="warning",
            log=_related_log(logbook, item["label"], "review"),
        )
        for item in product_attention
        if not item.get("has_stock") or item.get("reasons")
    ]
    unassigned = [
        _readiness_item(
            container["name"],
            container.get("item_label") or "No current item",
            "Container needs a storage location",
            status="warning",
            log=_related_log(logbook, container["name"], container.get("item_label") or "", "location"),
        )
        for container in containers
        if not container.get("location_id") or container.get("location") in {"Unassigned", "The Void"}
    ]
    stale = [
        _readiness_item(
            container["name"],
            container.get("best_before_date") or container.get("opened_date") or container.get("purchased_date") or "",
            "Date needs attention",
            status="warning",
            log=_related_log(logbook, container["name"], container.get("item_label") or "", "date"),
        )
        for container in containers
        if freshness_status(container.get("best_before_date"))["status"] == "stale"
    ]
    location_at_risk = [
        _readiness_item(
            location["name"],
            location.get("health", {}).get("status", "unknown"),
            "; ".join(location.get("health", {}).get("problems") or ["Location needs attention"]),
            status="critical" if location.get("health", {}).get("status") == "critical" else "warning",
            log=_related_log(logbook, location["name"], "location"),
        )
        for location in locations
        if location.get("health", {}).get("status") in {"warning", "critical"}
    ]
    return {
        "ready": (ready_components + stocked_products)[:12],
        "missing": missing[:12],
        "empty": [
            _readiness_item(
                container["name"],
                container.get("item_label") or "No current item",
                "Empty container can be refilled or queued for shopping",
                status="empty",
                log=recent_log,
            )
            for container in empty_containers[:12]
        ],
        "unassigned": unassigned[:12],
        "stale": stale[:12],
        "location_at_risk": location_at_risk[:12],
        "recent_provider_action": recent_log,
    }


def _suggested_actions_data(
    *,
    containers: list[dict[str, Any]],
    empty_containers: list[dict[str, Any]],
    product_attention: list[dict[str, Any]],
    readiness: dict[str, Any],
    shopping: dict[str, Any],
    storage_attention: dict[str, Any],
    logbook: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return explainable next actions backed by existing services or views."""
    actions: list[dict[str, Any]] = []
    today = date.today()
    soon = today + timedelta(days=3)
    if empty_containers:
        empty_names = _sample_names(empty_containers, "name", fallback="empty container")
        actions.append(
            _suggested_action(
                "queue_empty_containers",
                "Queue empty containers",
                f"{empty_names} {'is' if len(empty_containers) == 1 else 'are'} empty and can become a shopping request.",
                service="add_empty_containers_to_shopping_list",
                payload={},
                status="warning",
                sources=["Mise container"],
                target=_shopping_target_summary(shopping, "empty_containers"),
                last_queued=_latest_shopping_log(logbook, reason="empty_container_refill"),
            )
        )
    if shopping.get("grocy_minimum_stock"):
        actions.append(
            _suggested_action(
                "queue_grocy_minimum_stock",
                "Queue Grocy minimum stock",
                _minimum_stock_reason(readiness),
                service="add_missing_products_to_shopping_list",
                payload={},
                status="warning" if readiness.get("missing") else "ok",
                sources=["Grocy stock"],
                target="Grocy minimum stock",
                last_queued=_latest_shopping_log(logbook, reason="grocy_minimum_stock"),
            )
        )
    for item in product_attention:
        if item.get("has_stock"):
            continue
        actions.append(
            _suggested_action(
                f"queue_product_{item.get('item_id')}",
                f"Queue {item.get('label') or 'missing product'}",
                _product_attention_reason(item),
                service="add_to_shopping_list",
                payload={
                    "item_id": item.get("item_id"),
                    "quantity": 1,
                    "description": "Queued from Mise suggested actions; reason=missing_prep_item",
                },
                status="warning",
                sources=["Grocy stock", "Mealie recipe"],
                target=_shopping_target_label(shopping.get("product_backed_target")),
                last_queued=_latest_shopping_log(logbook, reason="explicit_shopping_request", label=item.get("label")),
            )
        )
        if len(actions) >= 5:
            break
    for container in containers:
        if container.get("content_kind") not in {"recipe", "meal"}:
            continue
        if _as_float(container.get("canonical_quantity", container.get("quantity", 0))) != 0:
            continue
        label = container.get("item_label") or container.get("name") or "Prepared batch"
        actions.append(
            _suggested_action(
                f"queue_recipe_{container.get('tag_id')}",
                f"Queue {label}",
                f"{container.get('name') or container.get('tag_id') or label} is an empty {container.get('content_kind') or 'recipe'} container for {label}.",
                service="add_to_shopping_list",
                payload={
                    "name": label,
                    "quantity": 1,
                    "description": f"Queued from empty Mise recipe container {container.get('name') or container.get('tag_id')}; reason=zero_recipe_container",
                },
                status="empty",
                sources=["Mise container", "Mealie recipe"],
                target=_shopping_target_label(shopping.get("free_text_target")),
                last_queued=_latest_shopping_log(logbook, reason="explicit_shopping_request", label=label),
            )
        )
        if len(actions) >= 7:
            break
    expiring = [
        container
        for container in containers
        if _date_in_range(container.get("best_before_date"), today, soon)
    ]
    opened = [
        container
        for container in containers
        if container.get("opened_date") and not container.get("best_before_date")
    ]
    stale = readiness.get("stale") or []
    if stale or expiring or opened:
        actions.append(
            _suggested_action(
                "review_freshness",
                "Review freshness",
                _freshness_reason(stale, expiring, opened),
                open_tab="inventory",
                status="warning",
                sources=["Mise container"],
            )
        )
    if storage_attention.get("attention_count"):
        actions.append(
            _suggested_action(
                "review_storage_safety",
                "Review storage safety",
                _storage_attention_reason(storage_attention),
                open_tab="storage",
                status="critical" if storage_attention.get("status") == "critical" else "warning",
                sources=["Location health", "Mise container"],
            )
        )
    return sorted(actions, key=_suggested_action_sort_key)[:8]


def _suggested_action(
    action_id: str,
    title: str,
    because: str,
    *,
    status: str,
    service: str | None = None,
    payload: dict[str, Any] | None = None,
    open_tab: str | None = None,
    sources: list[str] | None = None,
    target: str | None = None,
    last_queued: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one panel action with an explicit reason and existing target."""
    return {
        "id": action_id,
        "title": title,
        "because": because,
        "status": status,
        "service": service or "",
        "payload": payload or {},
        "open_tab": open_tab or "",
        "sources": sources or [],
        "target": target or "",
        "last_queued": last_queued or None,
    }


def _shopping_target_label(provider: Any) -> str:
    """Return the shopping target label shown before queueing."""
    if provider == "kitchenowl":
        return "KitchenOwl shopping list"
    if provider == "grocy":
        return "Grocy shopping list"
    return "Configured shopping list"


def _shopping_target_summary(shopping: dict[str, Any], action_kind: str) -> str:
    """Explain the provider target used by a shopping action."""
    product_target = _shopping_target_label(shopping.get("product_backed_target"))
    text_target = _shopping_target_label(shopping.get("free_text_target"))
    if action_kind == "empty_containers" and product_target != text_target:
        return f"{product_target} for Grocy products; {text_target} fallback"
    return product_target if action_kind == "empty_containers" else text_target


def _latest_shopping_log(
    logbook: list[dict[str, Any]],
    *,
    reason: str,
    label: str | None = None,
) -> dict[str, Any] | None:
    """Return the newest matching shopping log entry for panel feedback."""
    wanted = str(label or "").casefold()
    for entry in reversed(logbook):
        details = entry.get("details") or {}
        if details.get("reason") != reason:
            continue
        labels = [str(value).casefold() for value in (details.get("labels") or []) if value]
        if not labels and details.get("item"):
            labels = [str(details.get("item")).casefold()]
        item_labels = [
            str(item.get("label")).casefold()
            for item in details.get("items", []) or []
            if isinstance(item, dict) and item.get("label")
        ]
        if wanted and labels and wanted not in labels and wanted not in item_labels:
            continue
        return {
            "action": entry.get("action"),
            "message": entry.get("message"),
            "created_at": entry.get("created_at"),
            "provider": details.get("provider"),
            "targets": details.get("targets", {}),
            "item_count": details.get("item_count"),
            "reason": reason,
        }
    return None


def _sample_names(rows: list[dict[str, Any]], key: str, *, fallback: str) -> str:
    """Return a compact human-readable sample from existing overview rows."""
    names = [str(row.get(key) or "").strip() for row in rows]
    names = [name for name in names if name]
    if not names:
        names = [fallback]
    sample = ", ".join(names[:2])
    remaining = len(rows) - len(names[:2])
    return f"{sample} + {remaining} more" if remaining > 0 else sample


def _minimum_stock_reason(readiness: dict[str, Any]) -> str:
    """Explain Grocy minimum-stock queueing using current missing rows."""
    missing = readiness.get("missing") or []
    if missing:
        return f"Grocy owns below-minimum-stock policy, and {missing[0].get('label') or 'one product'} currently needs review."
    return "Grocy owns below-minimum-stock policy, and Mise can ask Grocy to queue anything below par."


def _product_attention_reason(item: dict[str, Any]) -> str:
    """Explain a product queue recommendation with the product and review reason."""
    reasons = ", ".join(item.get("reasons") or ["Product needs prep or shopping"])
    return f"{item.get('label') or 'This product'} has no stock because {reasons}."


def _freshness_reason(
    stale: list[dict[str, Any]],
    expiring: list[dict[str, Any]],
    opened: list[dict[str, Any]],
) -> str:
    """Explain freshness review with specific dates and containers."""
    parts: list[str] = []
    if stale:
        first = stale[0]
        parts.append(f"{first.get('label') or 'one container'} is stale since {first.get('detail') or 'its stored date'}")
    if expiring:
        first = expiring[0]
        parts.append(f"{first.get('name') or 'one container'} expires {first.get('best_before_date')}")
    if opened:
        first = opened[0]
        parts.append(f"{first.get('name') or 'one container'} was opened {first.get('opened_date')} without a best-before date")
    return "; ".join(parts) + "."


def _storage_attention_reason(storage_attention: dict[str, Any]) -> str:
    """Explain storage review with the exact location or container type at risk."""
    locations = storage_attention.get("unhealthy_locations") or []
    unassigned = storage_attention.get("containers_needing_location") or []
    prepared = storage_attention.get("prepared_inventory_at_risk") or []
    parts: list[str] = []
    if locations:
        first = locations[0]
        problems = ", ".join(first.get("problems") or [first.get("status") or "needs attention"])
        parts.append(f"{first.get('name') or 'one location'} reports {problems}")
    if unassigned:
        parts.append(f"{_sample_names(unassigned, 'name', fallback='one container')} needs a location")
    if prepared:
        parts.append(f"{_sample_names(prepared, 'name', fallback='prepared inventory')} is stored in an unhealthy location")
    if not parts:
        parts.append("storage attention attributes report an issue")
    return "; ".join(parts) + "."


def _suggested_action_sort_key(action: dict[str, Any]) -> tuple[int, str]:
    """Keep safety and review work above lower-risk shopping prompts."""
    action_id = str(action.get("id") or "")
    if "storage_safety" in action_id:
        return (0, action_id)
    if "freshness" in action_id:
        return (1, action_id)
    if action.get("status") == "critical":
        return (2, action_id)
    if action.get("status") in {"warning", "empty"} and action.get("open_tab"):
        return (3, action_id)
    if action.get("status") in {"warning", "empty"}:
        return (4, action_id)
    return (5, action_id)


def _date_in_range(value: Any, start: date, end: date) -> bool:
    """Return whether an ISO date string falls in an inclusive range."""
    return date_in_range(value, start, end)


def _planning_comparison_data(
    *,
    containers: list[dict[str, Any]],
    products: dict[str, dict[str, Any]],
    meal_inventory: dict[str, Any],
    item_totals: list[dict[str, Any]],
    logbook: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compare prepared Mealie components with related Grocy stock rows."""
    grocy_stock = [item for item in item_totals if item.get("source") == "grocy"]
    rows: list[dict[str, Any]] = []
    for component in meal_inventory.get("components") or []:
        recipe_names = sorted((component.get("recipes") or {}).keys())
        terms = [component.get("component") or "", *recipe_names]
        rows.append(
            {
                "component": component.get("component") or "Prepared component",
                "prepared": _format_quantities(component.get("quantities", {})),
                "recipes": [
                    {"label": label, "quantity": _format_quantities(quantities)}
                    for label, quantities in sorted((component.get("recipes") or {}).items())
                ],
                "proteins": [
                    {"label": label, "quantity": _format_quantities(quantities)}
                    for label, quantities in sorted((component.get("proteins") or {}).items())
                ],
                "grocy_stock": _related_stock_rows(grocy_stock, terms),
                "log": _log_summary(_related_log(logbook, *terms, "recipe", "container")),
            }
        )
    for container in containers:
        if container.get("content_kind") != "recipe" or _as_float(container.get("canonical_quantity", container.get("quantity", 0))) <= 0:
            continue
        product = products.get(container.get("product_id") or "", {})
        classification = product.get("classification") or {}
        label = product.get("label") or container.get("item_label") or container.get("name") or "Recipe batch"
        component = classification.get("component") or label
        quantity = f"{container.get('canonical_quantity', container.get('quantity', 0))} {container.get('canonical_unit', container.get('unit')) or 'items'}"
        terms = [component, label]
        rows.append(
            {
                "component": component,
                "prepared": quantity,
                "recipes": [{"label": label, "quantity": quantity}],
                "proteins": [],
                "grocy_stock": _related_stock_rows(grocy_stock, terms),
                "log": _log_summary(_related_log(logbook, *terms, "recipe", "container")),
            }
        )
    return sorted(rows, key=lambda row: row["component"].casefold())


def _related_stock_rows(item_totals: list[dict[str, Any]], terms: list[str]) -> list[dict[str, Any]]:
    """Return Grocy stock rows whose labels overlap a prepared component."""
    term_tokens = {
        token
        for term in terms
        for token in _word_tokens(term)
        if len(token) > 2
    }
    if not term_tokens:
        return []
    rows = []
    for item in item_totals:
        label_tokens = set(_word_tokens(item.get("label") or ""))
        if not term_tokens & label_tokens:
            continue
        rows.append(
            {
                "label": item.get("label") or "Grocy product",
                "quantity": f"{item.get('quantity', 0)} {item.get('unit') or ''}".strip(),
                "locations": item.get("locations", {}),
                "containers": item.get("containers", 0),
            }
        )
    return rows[:4]


def _readiness_item(label: str, detail: str, reason: str, *, status: str, log: dict[str, Any] | None) -> dict[str, Any]:
    """Build one compact readiness row."""
    return {
        "label": label,
        "detail": detail,
        "reason": reason,
        "status": status,
        "log": _log_summary(log) if log else None,
    }


def _recent_provider_log(logbook: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the most recent log entry that explains provider-facing activity."""
    keywords = ("shopping", "Grocy", "KitchenOwl", "stock", "container", "Location")
    return next(
        (
            entry
            for entry in reversed(logbook)
            if any(keyword.casefold() in f"{entry.get('action', '')} {entry.get('message', '')}".casefold() for keyword in keywords)
        ),
        None,
    )


def _related_log(logbook: list[dict[str, Any]], *terms: str) -> dict[str, Any] | None:
    """Return the newest log entry related to a specific readiness row."""
    tokens = {token for term in terms for token in _word_tokens(term) if len(token) > 2}
    if not tokens:
        return _recent_provider_log(logbook)
    return next(
        (
            entry
            for entry in reversed(logbook)
            if tokens & set(_word_tokens(f"{entry.get('action', '')} {entry.get('message', '')} {entry.get('details', '')}"))
        ),
        _recent_provider_log(logbook),
    )


def _log_summary(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the log fields the panel needs for short explanations."""
    if not entry:
        return None
    return {
        "action": entry.get("action") or "",
        "message": entry.get("message") or "",
        "created_at": entry.get("created_at") or "",
    }


def _format_quantities(quantities: dict[str, Any]) -> str:
    """Format simple quantity maps for compact panel rows."""
    return format_quantities(quantities)


def _word_tokens(value: Any) -> list[str]:
    """Normalize labels and log text into comparable tokens."""
    return word_tokens(value)


def _as_float(value: Any) -> float:
    """Return a safe numeric value for provider summaries."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0
