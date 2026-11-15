"""Alarm sounds on media players.

Bastion ships its own synthesized sounds (frontend/sounds). Own files come from
Home Assistant's media sources, e.g. an MP3 uploaded to "My media". Countdown
and siren sounds repeat while their state lasts, armed/disarmed play once.
The previous volume of each player is restored afterwards.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
import time
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from ..const import PANEL_STATIC_URL

_LOGGER = logging.getLogger(__name__)

# Built-in sounds and their length in seconds.
BUILTIN = {"siren": 6, "entry": 10, "exit": 10, "armed": 2, "disarmed": 2}
LOOPS = ("triggered", "pending", "arming")
ONCE = ("armed", "disarmed")
SOUND_KEYS = LOOPS + ONCE
FEATURE_VOLUME_SET = 4
FEATURE_ANNOUNCE = 1048576
FINISHED = {"idle", "paused", "off", "on", "standby"}
CALL_TIMEOUT = 10


def default_sounds() -> dict[str, Any]:
    """Factory defaults (inactive until players are chosen)."""
    return {
        "players": [],
        "volume": 0.9,
        "notice_volume": 0.5,
        "triggered": "bastion:siren",
        "pending": "bastion:entry",
        "arming": "bastion:exit",
        "armed": "",
        "disarmed": "",
    }


def builtin_path(name: str) -> str:
    """URL path of a built-in sound."""
    return f"{PANEL_STATIC_URL}/sounds/{name}.mp3"


class AlarmSounds:
    """Plays alarm sounds on media players."""

    def __init__(self, hass: HomeAssistant, config_getter: Callable[[], dict[str, Any]]) -> None:
        """Init."""
        self.hass = hass
        self._config = config_getter
        self._loop: str | None = None
        self._loop_url: str | None = None
        self._volumes: dict[str, float | None] = {}
        self._unsub_players: CALLBACK_TYPE | None = None
        self._restore_timer: CALLBACK_TYPE | None = None
        self._last_start: dict[str, float] = {}
        self._test_players: list[str] = []
        self._lock = asyncio.Lock()

    @property
    def cfg(self) -> dict[str, Any]:
        """Sound settings with defaults."""
        return {**default_sounds(), **(self._config() or {})}

    @property
    def players(self) -> list[str]:
        """Configured players that exist."""
        return [p for p in self.cfg["players"] if self.hass.states.get(p) is not None]

    @property
    def active(self) -> str | None:
        """Running loop (state key) or None."""
        return self._loop

    # ------------------------------------------------------------- events
    @callback
    def on_event(self, kind: str, state: str) -> None:
        """Alarm event from the engine."""
        if not self.cfg["players"] and self._loop is None:
            return
        self.hass.async_create_task(self._async_on_event(kind, state), eager_start=False)

    @callback
    def sirens_off(self) -> None:
        """The siren time is over: stop the siren sound as well."""
        if self._loop == "triggered":
            self.hass.async_create_task(self._async_stop_siren(), eager_start=False)

    async def _async_stop_siren(self) -> None:
        async with self._lock:
            if self._loop == "triggered":
                await self._async_stop_loop(restore=True)

    async def _async_on_event(self, kind: str, state: str) -> None:
        async with self._lock:
            loop = state if state in LOOPS else None
            if loop != self._loop:
                await self._async_stop_loop(restore=loop is None)
                if loop and (src := self.cfg.get(loop)):
                    await self._async_start_loop(loop, src)
            if loop is None and kind in ONCE and (src := self.cfg.get(kind)):
                await self._async_play_once(src)

    async def async_unload(self) -> None:
        """Stop everything and restore volumes."""
        if self._restore_timer is not None:
            self._restore_timer()
            self._restore_timer = None
        async with self._lock:
            await self._async_stop_loop(restore=True)
            await self._async_restore_volume()

    # ------------------------------------------------------------ helpers
    async def async_url(self, src: str) -> str | None:
        """Playable URL for a configured sound."""
        from homeassistant.components.media_player.browse_media import (  # noqa: PLC0415
            async_process_play_media_url,
        )

        try:
            if src.startswith("bastion:"):
                name = src.split(":", 1)[1]
                return async_process_play_media_url(self.hass, builtin_path(name)) if name in BUILTIN else None
            if src.startswith("media-source://"):
                from homeassistant.components import media_source  # noqa: PLC0415

                item = await media_source.async_resolve_media(self.hass, src, None)
                return async_process_play_media_url(self.hass, item.url)
            if src.startswith(("http://", "https://")):
                return src
        except (HomeAssistantError, ValueError) as err:
            _LOGGER.warning("Bastion cannot play %s: %s", src, err)
        return None

    def _supports(self, player: str, feature: int) -> bool:
        state = self.hass.states.get(player)
        return bool(state and int(state.attributes.get("supported_features") or 0) & feature)

    async def _call(self, service: str, data: dict[str, Any]) -> None:
        # A broken speaker must never stop the alarm logic.
        try:
            async with asyncio.timeout(CALL_TIMEOUT):
                await self.hass.services.async_call("media_player", service, data, blocking=True)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Bastion media_player.%s for %s failed: %s", service, data.get("entity_id"), err)

    async def _async_set_volume(self, players: list[str], volume: float) -> None:
        calls = []
        for player in players:
            state = self.hass.states.get(player)
            if state is None or not self._supports(player, FEATURE_VOLUME_SET):
                continue
            self._volumes.setdefault(player, state.attributes.get("volume_level"))
            calls.append(self._call("volume_set", {"entity_id": player, "volume_level": round(float(volume), 2)}))
        await asyncio.gather(*calls)

    async def _async_restore_volume(self) -> None:
        volumes, self._volumes = self._volumes, {}
        await asyncio.gather(
            *(
                self._call("volume_set", {"entity_id": p, "volume_level": v})
                for p, v in volumes.items()
                if isinstance(v, (int, float))
            )
        )

    async def _async_play(self, players: list[str], url: str, *, announce: bool = False) -> None:
        calls = []
        for player in players:
            data: dict[str, Any] = {"entity_id": player, "media_content_id": url, "media_content_type": "music"}
            if announce:
                data["announce"] = True
            self._last_start[player] = time.monotonic()
            calls.append(self._call("play_media", data))
        await asyncio.gather(*calls)

    # -------------------------------------------------------------- loops
    async def _async_start_loop(self, key: str, src: str) -> None:
        players = self.players
        if not players or (url := await self.async_url(src)) is None:
            return
        if self._restore_timer is not None:
            self._restore_timer()
            self._restore_timer = None
        volume = self.cfg["volume"] if key == "triggered" else self.cfg["notice_volume"]
        await self._async_set_volume(players, volume)
        self._loop, self._loop_url = key, url
        await self._async_play(players, url)
        self._unsub_players = async_track_state_change_event(self.hass, players, self._on_player)

    @callback
    def _on_player(self, event: Event) -> None:
        """Replay when a player finished (or was stopped) while the loop runs."""
        if self._loop is None or self._loop_url is None:
            return
        new, old = event.data.get("new_state"), event.data.get("old_state")
        if new is None or new.state not in FINISHED or (old is not None and old.state != "playing"):
            return
        player = event.data["entity_id"]
        if time.monotonic() - self._last_start.get(player, 0) < 2:
            return
        self.hass.async_create_task(self._async_replay(player, self._loop), eager_start=False)

    async def _async_replay(self, player: str, loop: str) -> None:
        async with self._lock:
            if self._loop == loop and self._loop_url:
                await self._async_play([player], self._loop_url)

    async def _async_stop_loop(self, *, restore: bool) -> None:
        if self._unsub_players is not None:
            self._unsub_players()
            self._unsub_players = None
        if self._loop is None:
            return
        self._loop = self._loop_url = None
        await asyncio.gather(*(self._call("media_stop", {"entity_id": p}) for p in self.players))
        if restore:
            await self._async_restore_volume()

    # ----------------------------------------------------------- one shot
    async def _async_play_once(
        self, src: str, *, test: bool = False, players: list[str] | None = None, volume: float | None = None
    ) -> bool:
        players = [p for p in players if self.hass.states.get(p) is not None] if players is not None else self.players
        if not players or (url := await self.async_url(src)) is None:
            return False
        announce = [] if test else [p for p in players if self._supports(p, FEATURE_ANNOUNCE)]
        plain = [p for p in players if p not in announce]
        await self._async_play(announce, url, announce=True)
        if plain:
            if volume is None:
                volume = self.cfg["volume"] if src == "bastion:siren" else self.cfg["notice_volume"]
            await self._async_set_volume(plain, volume)
            await self._async_play(plain, url)
            name = src.split(":", 1)[1] if src.startswith("bastion:") else ""
            self._schedule_restore(BUILTIN.get(name, 20) + 2)
        return True

    def _schedule_restore(self, seconds: float) -> None:
        if self._restore_timer is not None:
            self._restore_timer()

        @callback
        def _restore(_now: datetime) -> None:
            self._restore_timer = None
            if self._loop is None:
                self.hass.async_create_task(self._async_restore_volume(), eager_start=False)

        self._restore_timer = async_call_later(self.hass, seconds, _restore)

    async def async_test(self, src: str, players: list[str] | None = None, volume: float | None = None) -> bool:
        """Play a sound once (panel test button); players default to the saved ones."""
        async with self._lock:
            if self._loop is not None:
                return False
            if players is not None:
                self._test_players = list(players)
            return await self._async_play_once(src, test=True, players=players, volume=volume)

    async def async_stop_test(self) -> None:
        """Stop a test sound."""
        async with self._lock:
            if self._loop is not None:
                return
            if self._restore_timer is not None:
                self._restore_timer()
                self._restore_timer = None
            players = set(self.players) | set(self._test_players)
            self._test_players = []
            await asyncio.gather(*(self._call("media_stop", {"entity_id": p}) for p in players))
            await self._async_restore_volume()


async def async_media_files(hass: HomeAssistant, limit: int = 200) -> list[dict[str, str]]:
    """Audio files from Home Assistant's media sources (for the sound picker)."""
    try:
        from homeassistant.components import media_source  # noqa: PLC0415
    except ImportError:
        return []
    out: list[dict[str, str]] = []

    async def walk(media_id: str | None, path: str, depth: int) -> None:
        if depth > 4 or len(out) >= limit:
            return
        try:
            item = await media_source.async_browse_media(hass, media_id)
        except Exception:  # noqa: BLE001 - a broken source must not break the panel
            return
        for child in item.children or []:
            if len(out) >= limit:
                return
            title = f"{path}{child.title}"
            if child.can_expand:
                await walk(child.media_content_id, f"{title} / ", depth + 1)
            elif str(child.media_content_type or "").startswith("audio/") or child.media_class == "music":
                out.append({"id": child.media_content_id, "title": title})

    # Only local media ("My media"); other sources such as radio directories are huge.
    if "media_source" in hass.config.components:
        await walk("media-source://media_source", "", 0)
    return out
