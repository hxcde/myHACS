"""Notifications: persistent notification plus optional notify targets."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant

from .const import CONF_NOTIFY_TARGETS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class Notifier:
    """Send messages with simple per key rate limiting."""

    def __init__(self, hass: HomeAssistant, options: dict[str, Any]) -> None:
        """Init."""
        self.hass = hass
        self._targets: list[str] = list(options.get(CONF_NOTIFY_TARGETS) or [])
        self._last: dict[str, float] = {}

    def update_options(self, options: dict[str, Any]) -> None:
        """Apply new options."""
        self._targets = list(options.get(CONF_NOTIFY_TARGETS) or [])

    async def async_send(
        self,
        title: str,
        message: str,
        *,
        key: str | None = None,
        rate_limit: float = 0,
        persistent: bool = True,
        data: dict[str, Any] | None = None,
        actions: list[dict[str, Any]] | None = None,
        mobile: dict[str, Any] | None = None,
    ) -> None:
        """Send a notification. Actions and `mobile` data are added for Companion App targets."""
        if key and rate_limit:
            now = time.monotonic()
            if now - self._last.get(key, -rate_limit - 1) < rate_limit:
                return
            self._last[key] = now
        if persistent:
            persistent_notification.async_create(
                self.hass,
                message,
                title=title,
                notification_id=f"{DOMAIN}_{key}" if key else None,
            )
        for target in self._targets:
            payload_data = dict(data or {})
            if self._is_mobile(target):
                if actions:
                    payload_data["actions"] = actions
                    payload_data.setdefault("push", {"interruption-level": "time-sensitive"})
                    if key:
                        payload_data["tag"] = f"{DOMAIN}_{key}"
                payload_data.update(mobile or {})
            await self._send_target(target, title, message, payload_data or None)

    @staticmethod
    def _is_mobile(target: str) -> bool:
        return target.strip().removeprefix("notify.").startswith("mobile_app_")

    async def async_clear(self, tag: str) -> None:
        """Remove a tagged notification from Companion App devices."""
        for target in self._targets:
            if self._is_mobile(target):
                await self._send_target(target, "", "clear_notification", {"tag": tag})

    async def _send_target(self, target: str, title: str, message: str, data: dict[str, Any] | None) -> None:
        target = target.strip()
        if not target:
            return
        try:
            if target.startswith("notify.") and self.hass.states.get(target) is not None:
                await self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {"entity_id": target, "title": title, "message": message},
                    blocking=False,
                )
                return
            service = target.removeprefix("notify.")
            if self.hass.services.has_service("notify", service):
                payload: dict[str, Any] = {"title": title, "message": message}
                if data:
                    payload["data"] = data
                await self.hass.services.async_call("notify", service, payload, blocking=False)
                return
            _LOGGER.warning("Notify target %s not found", target)
        except Exception:  # noqa: BLE001 - a broken target must not break the audit
            _LOGGER.exception("Sending notification to %s failed", target)
