"""Presence of the household members (phone in the home network)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .alarm.household import SIGNAL_HOUSEHOLD


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    """One tracker per person; follows changes of the household list."""
    bastion = entry.runtime_data
    known: dict[str, PersonTracker] = {}

    @callback
    def sync() -> None:
        people = {p["id"]: p for p in bastion.household.people}
        new = [PersonTracker(bastion, pid) for pid in people if pid not in known]
        for tracker in new:
            known[tracker.person_id] = tracker
        if new:
            async_add_entities(new)
        registry = er.async_get(hass)
        for pid in [k for k in known if k not in people]:
            tracker = known.pop(pid)
            if tracker.entity_id and registry.async_get(tracker.entity_id):
                registry.async_remove(tracker.entity_id)

    sync()
    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_HOUSEHOLD, sync))


class PersonTracker(ScannerEntity):
    """Home while the person's phone answers in the home network."""

    _attr_should_poll = False
    _attr_icon = "mdi:cellphone-marker"

    def __init__(self, bastion, person_id: str) -> None:
        """Init."""
        self.bastion = bastion
        self.person_id = person_id
        self._uid = f"{bastion.entry.entry_id}_person_{person_id}"

    @property
    def _person(self) -> dict[str, Any]:
        return next((p for p in self.bastion.household.people if p["id"] == self.person_id), {})

    @property
    def unique_id(self) -> str:
        return self._uid

    @property
    def name(self) -> str:
        return f"Bastion {self._person.get('name') or self.person_id}"

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        return self.bastion.household.is_home(self.person_id) is True

    @property
    def ip_address(self) -> str | None:
        return self._person.get("ip")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.bastion.household.status.get(self.person_id) or {}
        return {"last_seen": status.get("last_seen"), "since": status.get("since"), "detected_by": status.get("method")}

    async def async_added_to_hass(self) -> None:
        """Update with every scan result."""
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_HOUSEHOLD, self.async_write_ha_state))
