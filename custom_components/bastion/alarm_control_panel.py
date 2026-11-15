"""Alarm control panel entity of the Bastion alarm system."""

from __future__ import annotations

from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .alarm.engine import SIGNAL_ALARM, AlarmError
from .entity import BastionEntity
from .texts import alarm_error_text


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    """Set up the alarm panel."""
    async_add_entities([BastionAlarmPanel(entry.runtime_data)])


class BastionAlarmPanel(BastionEntity, AlarmControlPanelEntity):
    """Home, night and away modes with rooms and per mode sensors."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(self, bastion) -> None:
        """Init."""
        super().__init__(bastion, "alarm")
        self.engine = bastion.alarm

    async def async_added_to_hass(self) -> None:
        """Follow the engine."""
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_ALARM, self._handle_update))

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Current state."""
        return AlarmControlPanelState(self.engine.state)

    @property
    def code_format(self) -> CodeFormat | None:
        """Keypad type."""
        if not self.engine.has_codes:
            return None
        return CodeFormat.NUMBER if self.engine.numeric_codes else CodeFormat.TEXT

    @property
    def code_arm_required(self) -> bool:
        """Code needed for arming."""
        return bool(self.engine.has_codes and self.engine.config["require_code_arm"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Mode, countdown and trigger information."""
        status = self.engine.status()
        triggered = status["triggered_by"] or {}
        return {
            "mode": status["mode"],
            "target_mode": status["target"],
            "until": status["until"],
            "triggered_sensor": triggered.get("sensor"),
            "triggered_room": triggered.get("room"),
            "bypassed": status["bypassed"],
        }

    async def _user(self) -> str | None:
        if self._context is not None and self._context.user_id:
            user = await self.hass.auth.async_get_user(self._context.user_id)
            return user.name if user else None
        return None

    async def _run(self, coro) -> None:
        try:
            await coro
        except AlarmError as err:
            raise HomeAssistantError(alarm_error_text(err.reason, self.hass.config.language, err.detail)) from err

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm."""
        await self._run(self.engine.async_disarm(code, user=await self._user()))

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm home."""
        await self._run(self.engine.async_arm("home", code, user=await self._user()))

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Arm night."""
        await self._run(self.engine.async_arm("night", code, user=await self._user()))

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm away."""
        await self._run(self.engine.async_arm("away", code, user=await self._user()))

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Panic / manual trigger."""
        await self.engine.async_trigger("manual", user=await self._user())

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
