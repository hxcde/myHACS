"""Sidebar panel registration."""

from __future__ import annotations

import os

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PANEL_COMPONENT, PANEL_STATIC_URL, PANEL_URL

_STATIC_REGISTERED = f"{DOMAIN}_static_registered"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Serve the panel JS and add the sidebar entry (admins only)."""
    path = os.path.join(os.path.dirname(__file__), "frontend")
    if not hass.data.get(_STATIC_REGISTERED):
        await hass.http.async_register_static_paths([StaticPathConfig(PANEL_STATIC_URL, path, cache_headers=False)])
        hass.data[_STATIC_REGISTERED] = True
    version = await hass.async_add_executor_job(_mtime, os.path.join(path, "bastion-panel.js"))
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="Bastion",
        sidebar_icon="mdi:shield-lock",
        frontend_url_path=PANEL_URL,
        require_admin=True,
        config={
            "_panel_custom": {
                "name": PANEL_COMPONENT,
                "module_url": f"{PANEL_STATIC_URL}/bastion-panel.js?v={version}",
                "embed_iframe": False,
                "trust_external": False,
            }
        },
        update=True,
    )


def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar entry."""
    frontend.async_remove_panel(hass, PANEL_URL, warn_if_unknown=False)


def _mtime(path: str) -> int:
    try:
        return int(os.path.getmtime(path))
    except OSError:
        return 0
