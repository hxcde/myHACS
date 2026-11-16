"""Binary sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .alarm.household import SIGNAL_HOUSEHOLD
from .const import CONF_ANOMALY_ENTITIES, Severity
from .entity import BastionEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    """Set up binary sensors."""
    bastion = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        CriticalSensor(bastion),
        SabotageSensor(bastion),
        CanarySensor(bastion),
        AnyoneHomeSensor(bastion),
    ]
    for entity_id in bastion.options.get(CONF_ANOMALY_ENTITIES) or []:
        entities.append(AnomalySensor(bastion, entity_id))
    async_add_entities(entities)

    # One presence sensor per person of the household, following the list.
    known: dict[str, PersonPresenceSensor] = {}

    @callback
    def sync() -> None:
        people = {p["id"]: p for p in bastion.household.people}
        new = [PersonPresenceSensor(bastion, pid) for pid in people if pid not in known]
        for sensor in new:
            known[sensor.person_id] = sensor
        if new:
            async_add_entities(new)
        registry = er.async_get(hass)
        for pid in [k for k in known if k not in people]:
            sensor = known.pop(pid)
            if sensor.entity_id and registry.async_get(sensor.entity_id):
                registry.async_remove(sensor.entity_id)
        for sensor in known.values():
            sensor.refresh_name()

    sync()
    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_HOUSEHOLD, sync))


class CriticalSensor(BastionEntity, BinarySensorEntity):
    """On while critical or high findings are open."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "critical_findings")

    @property
    def is_on(self) -> bool:
        counts = self.bastion.summary()["counts"]
        return bool(counts[Severity.CRITICAL.value] or counts[Severity.HIGH.value])


class SabotageSensor(BastionEntity, BinarySensorEntity):
    """On after several security devices went offline at once."""

    _attr_device_class = BinarySensorDeviceClass.TAMPER

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "sabotage")

    @property
    def is_on(self) -> bool:
        return self.bastion.anomaly.sabotage_active


class CanarySensor(BastionEntity, BinarySensorEntity):
    """On for 24 h after a decoy was used."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "canary")

    @property
    def is_on(self) -> bool:
        return self.bastion.canary.alarm_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        triggers = self.bastion.canary.state.get("triggers", [])
        return {"last_trigger": triggers[-1] if triggers else None}


class AnyoneHomeSensor(BastionEntity, BinarySensorEntity):
    """On while at least one phone of the household is in the home network."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "anyone_home")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_HOUSEHOLD, self._handle_update))

    @property
    def available(self) -> bool:
        return bool(self.bastion.household.people)

    @property
    def is_on(self) -> bool:
        return bool(self.bastion.household.anyone_home())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        household = self.bastion.household
        return {"home": household.names(True), "away": household.names(False)}


class PersonPresenceSensor(BastionEntity, BinarySensorEntity):
    """On while the person is home (phone in the home network or linked tracker)."""

    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    def __init__(self, bastion, person_id: str) -> None:
        super().__init__(bastion, f"presence_{person_id}")
        self._attr_translation_key = "presence"
        self.person_id = person_id
        self._attr_translation_placeholders = {"name": self._person.get("name") or person_id}

    @property
    def _person(self) -> dict[str, Any]:
        return next((p for p in self.bastion.household.people if p["id"] == self.person_id), {})

    @callback
    def refresh_name(self) -> None:
        """Follow a renamed person (the entity id stays)."""
        name = self._person.get("name")
        if name and name != self._attr_translation_placeholders.get("name"):
            self._attr_translation_placeholders = {"name": name}
            if self.hass is not None and self.entity_id:
                self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_HOUSEHOLD, self._handle_update))

    @property
    def available(self) -> bool:
        return bool(self._person)

    @property
    def is_on(self) -> bool:
        return self.bastion.household.is_home(self.person_id) is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.bastion.household.status.get(self.person_id) or {}
        return {"since": status.get("since"), "last_seen": status.get("last_seen"), "detected_by": status.get("method")}


class AnomalySensor(BastionEntity, BinarySensorEntity):
    """Anomaly state of one monitored sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "anomaly"

    def __init__(self, bastion, entity_id: str) -> None:
        super().__init__(bastion, f"anomaly_{entity_id}")
        self._attr_translation_key = "anomaly"
        self._source = entity_id
        self._attr_translation_placeholders = {"entity": entity_id}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (state := self.hass.states.get(self._source)) is not None:
            self._attr_translation_placeholders = {"entity": state.attributes.get("friendly_name") or self._source}

    @property
    def is_on(self) -> bool:
        return self.bastion.anomaly.entity_state(self._source)["active"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self.bastion.anomaly.entity_state(self._source)
        return {"source": self._source, **{k: v for k, v in info.items() if k != "active"}}
