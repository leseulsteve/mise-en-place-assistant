"""Sidebar panel for Mise en Place Assistant."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol
from aiohttp import web

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, PANEL_URL_PATH
from .store import MiseEnPlaceAssistantInventory

_LOGGER = logging.getLogger(__name__)

PANEL_COMPONENT_NAME = "mise_en_place_assistant-panel"
PANEL_MODULE_URL = "/api/mise_en_place_assistant/panel.js"
PANEL_FRONTEND_PATH = Path(__file__).with_name("panel_frontend.js")


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
@websocket_api.websocket_command({vol.Required("type"): "mise_en_place_assistant/overview"})
def websocket_overview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return Mise en Place Assistant overview data to the authenticated frontend."""
    _LOGGER.debug("Received sidebar overview WebSocket request")
    try:
        manager = _manager(hass)
        data = _overview_data(manager)
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


def _manager(hass: HomeAssistant) -> MiseEnPlaceAssistantInventory:
    """Return the first loaded Mise en Place Assistant manager."""
    return next(iter(hass.data[DOMAIN].values()))


def _overview_data(manager: MiseEnPlaceAssistantInventory) -> dict[str, Any]:
    """Build practical overview data for the panel."""
    containers = sorted(
        manager.containers.values(),
        key=lambda container: container.get("updated_at") or "",
        reverse=True,
    )
    locations = [
        {
            "name": location["name"],
            "containers": manager.location_count(location_key),
        }
        for location_key, location in sorted(
            manager.locations.items(), key=lambda item: item[1]["name"].casefold()
        )
    ]
    empty_containers = [
        _container_summary(container)
        for container in containers
        if container.get("state") == "empty"
    ]
    low_containers = [
        _container_summary(container)
        for container in containers
        if 0 < float(container.get("quantity", 0)) <= 2
    ]
    dirty_containers = [
        _container_summary(container)
        for container in containers
        if container.get("state") == "dirty"
    ]
    item_totals = sorted(
        manager.item_totals(include_empty=False).values(), key=lambda item: item["label"].casefold()
    )

    return {
        "summary": {
            "containers": len(containers),
            "locations": len(manager.locations),
            "items": len(item_totals),
            "empty": len(empty_containers),
            "dirty": len(dirty_containers),
            "low": len(low_containers),
        },
        "containers": [_container_summary(container) for container in containers],
        "items": item_totals,
        "locations": locations,
        "empty_containers": empty_containers[:8],
        "low_containers": low_containers[:8],
        "dirty_containers": dirty_containers[:8],
        "logbook": list(reversed(manager.logbook[-50:])),
    }


def _container_summary(container: dict[str, Any]) -> dict[str, Any]:
    """Return display-safe container data."""
    return {
        "tag_id": container.get("tag_id"),
        "name": container.get("name") or "Container",
        "product_id": container.get("product_id"),
        "item_label": container.get("item_label") or "No current item",
        "format": container.get("item_format") or "",
        "quantity": container.get("display_quantity", container.get("quantity", 0)),
        "unit": container.get("unit") or "items",
        "canonical_quantity": container.get("canonical_quantity", container.get("quantity", 0)),
        "canonical_unit": container.get("canonical_unit", container.get("unit")) or "items",
        "location": container.get("location") or "Unassigned",
        "state": container.get("state") or "unknown",
        "updated_at": container.get("updated_at") or "",
        "created_at": container.get("created_at") or "",
    }
