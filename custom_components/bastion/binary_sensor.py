"""Binary sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ANOMALY_ENTITIES, Severity
from .entity import BastionEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    """Set up binary sensors."""
    bastion = entry.runtime_data
    entities: list[BinarySensorEntity] = [CriticalSensor(bastion), SabotageSensor(bastion), CanarySensor(bastion)]
    for entity_id in bastion.options.get(CONF_ANOMALY_ENTITIES) or []:
        entities.append(AnomalySensor(bastion, entity_id))
    async_add_entities(entities)


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
