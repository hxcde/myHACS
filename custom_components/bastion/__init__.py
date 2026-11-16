"""Bastion: security audit, config versioning in git and anomaly detection."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_OPTIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type BastionConfigEntry = ConfigEntry


def get_options(entry: ConfigEntry) -> dict[str, Any]:
    """Options merged with defaults."""
    return {**DEFAULT_OPTIONS, **(entry.options or {})}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services, websocket commands and the shutdown hook once."""
    from .coordinator import register_close_listener  # noqa: PLC0415
    from .services import async_register_services  # noqa: PLC0415
    from .websocket import async_register_websocket  # noqa: PLC0415

    async_register_services(hass)
    async_register_websocket(hass)
    register_close_listener(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bastion from a config entry."""
    from .coordinator import Bastion  # noqa: PLC0415
    from .panel import async_register_panel  # noqa: PLC0415

    bastion = Bastion(hass, entry)
    await bastion.async_setup()
    entry.runtime_data = bastion
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_register_panel(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload."""
    from .panel import async_unregister_panel  # noqa: PLC0415

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_unload()
        async_unregister_panel(hass)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def get_bastion(hass: HomeAssistant):
    """Return the running Bastion instance or None."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None
