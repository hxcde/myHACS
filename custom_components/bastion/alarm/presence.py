"""Reminder: everybody left, but the alarm is still disarmed.

Watches the chosen person entities (all persons if none are chosen). When none
of them is home for the configured time while the alarm is disarmed, the alarm
log gets an "unarmed" entry: it is pushed to the phones and via the worker,
with a link that arms the alarm from the dashboard (passkey) when remote
control is on. One reminder per absence; it resets when someone comes home.
"""

from __future__ import annotations

from datetime import datetime

from homeassistant.const import STATE_HOME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .engine import DISARMED, SIGNAL_ALARM


class PresenceReminder:
    """Fires engine.record_unarmed once per absence."""

    def __init__(self, hass: HomeAssistant, engine) -> None:
        """Init."""
        self.hass = hass
        self.engine = engine
        self._persons: list[str] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._timer: CALLBACK_TYPE | None = None
        self.reminded = False

    @property
    def cfg(self) -> dict:
        """Reminder settings (part of the remote settings)."""
        return self.engine.config.get("remote") or {}

    @property
    def minutes(self) -> int:
        """Delay after the last person left."""
        return max(1, int(self.cfg.get("reminder_minutes") or 20))

    def persons(self) -> list[str]:
        """Chosen person entities, else all persons."""
        chosen = [p for p in self.cfg.get("persons") or [] if p.startswith("person.")]
        return chosen or sorted(s.entity_id for s in self.hass.states.async_all("person"))

    def setup(self) -> None:
        """(Re)start watching according to the settings."""
        self.unload()
        if not self.cfg.get("reminder"):
            return
        self._persons = self.persons()
        if not self._persons:
            return
        self._unsubs.append(async_track_state_change_event(self.hass, self._persons, self._check))
        self._unsubs.append(async_dispatcher_connect(self.hass, SIGNAL_ALARM, self._check))
        self._check()

    def unload(self) -> None:
        """Stop watching."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []
        self._cancel()

    def _cancel(self) -> None:
        if self._timer is not None:
            self._timer()
            self._timer = None

    def all_away(self) -> bool:
        """True if every watched person is known and not home."""
        states = [self.hass.states.get(p) for p in self._persons]
        return bool(states) and all(
            s is not None and s.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE, STATE_HOME) for s in states
        )

    @callback
    def _check(self, *_args) -> None:
        away = self.all_away()
        if not away:
            self.reminded = False
        if away and self.engine.state == DISARMED and not self.reminded:
            if self._timer is None:
                self._timer = async_call_later(self.hass, self.minutes * 60, self._fire)
        else:
            self._cancel()

    @callback
    def _fire(self, _now: datetime | None = None) -> None:
        self._timer = None
        if self.reminded or not self.all_away() or self.engine.state != DISARMED:
            return
        self.reminded = True
        names = []
        for entity_id in self._persons:
            state = self.hass.states.get(entity_id)
            names.append((state.attributes.get("friendly_name") if state else None) or entity_id)
        self.engine.record_unarmed(self.minutes, names)
