"""Sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import BastionEntity

GIT_STATES = ["disabled", "ok", "pending", "error", "blocked"]


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    """Set up sensors."""
    bastion = entry.runtime_data
    async_add_entities(
        [
            ScoreSensor(bastion),
            OpenFindingsSensor(bastion),
            FailedLoginsSensor(bastion),
            GitStatusSensor(bastion),
            GitLastCommitSensor(bastion),
        ]
    )


class ScoreSensor(BastionEntity, SensorEntity):
    """Security score 0-100."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:shield-check"

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "security_score")

    @property
    def native_value(self) -> int | None:
        if self.bastion.data.get("last_audit") is None:
            return None
        return self.bastion.summary()["score"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        summary = self.bastion.summary()
        return {**summary["counts"], "last_audit": summary["last_audit"]}


class OpenFindingsSensor(BastionEntity, SensorEntity):
    """Number of open findings."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:shield-alert"

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "open_findings")

    @property
    def native_value(self) -> int:
        return self.bastion.summary()["open"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        active = [f for f in self.bastion.findings if not f.dismissed]
        return {"findings": [{"severity": f.severity.value, "title": f.title} for f in active[:20]]}


class FailedLoginsSensor(BastionEntity, SensorEntity):
    """Failed logins within 24 hours."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:account-lock"

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "failed_logins_24h")

    @property
    def native_value(self) -> int:
        return self.bastion.logins.failed_last_24h()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stats = self.bastion.logins.stats()
        return {"top_sources": [f"{ip} ({count})" for ip, count in stats["top_sources"]]}


class GitStatusSensor(BastionEntity, SensorEntity):
    """Git sync status."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = GIT_STATES
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:source-branch"

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "git_status")

    @property
    def native_value(self) -> str:
        return self.bastion.git.status()["status"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.bastion.git.status()
        return {k: status[k] for k in ("url", "branch", "last_error", "privacy", "encryption")}


class GitLastCommitSensor(BastionEntity, SensorEntity):
    """Time of the last commit."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:source-commit"

    def __init__(self, bastion) -> None:
        super().__init__(bastion, "git_last_commit")

    @property
    def native_value(self):
        value = self.bastion.git.status()["last_commit_time"]
        return dt_util.parse_datetime(value) if value else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.bastion.git.status()
        return {
            "sha": status["last_commit"],
            "summary": status["last_commit_summary"],
            "pushed": status["last_push_time"],
        }
