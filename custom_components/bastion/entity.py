"""Base entity."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NAME, SIGNAL_UPDATE


class BastionEntity(Entity):
    """Common entity behaviour: one service device, updates via dispatcher."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, bastion, key: str) -> None:
        """Init."""
        self.bastion = bastion
        self._attr_unique_id = f"{bastion.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bastion.entry.entry_id)},
            name=NAME,
            manufacturer="Bastion",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="homeassistant://bastion",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
