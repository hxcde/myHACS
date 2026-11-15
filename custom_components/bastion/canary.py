"""Decoys (canary tokens).

Bastion creates

* a long-lived access token of an inconspicuous, read-only, local-only user
  ("api-backup"). The token guard rejects it on every use and raises an alarm;
* an unauthenticated webhook. Any request to it raises an alarm.

Both are meant to be planted where an intruder would look (password manager
notes, shares, old backups) and, optionally, as a plain file in the git
repository, so a leak of that repository is detected the moment someone tries
the credentials.
"""

from __future__ import annotations

from datetime import timedelta
import logging
import secrets
from typing import Any

from aiohttp import web
from homeassistant.auth.const import GROUP_ID_READ_ONLY
from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN, RefreshToken
from homeassistant.components import webhook
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import dt as dt_util

from .const import CONF_CANARY_ENABLED, DOMAIN, EVENT_SECURITY, SIGNAL_UPDATE
from .texts import event_text

_LOGGER = logging.getLogger(__name__)

CANARY_USER = "api-backup"
CANARY_CLIENT = "backup-sync"
ALARM_HOLD = timedelta(hours=24)


class CanaryManager:
    """Creates, tracks and removes the decoys."""

    def __init__(self, hass: HomeAssistant, bastion) -> None:
        """Init."""
        self.hass = hass
        self.bastion = bastion
        self._webhook_id: str | None = None

    @property
    def state(self) -> dict[str, Any]:
        """Persisted state (part of bastion.data)."""
        return self.bastion.data.setdefault("canary", {})

    @property
    def user_id(self) -> str | None:
        """Id of the decoy user."""
        return self.state.get("user_id")

    @property
    def token_id(self) -> str | None:
        """Id of the decoy refresh token."""
        return self.state.get("token_id")

    async def async_setup(self) -> None:
        """Create or remove the decoys according to the options."""
        if self.bastion.options.get(CONF_CANARY_ENABLED):
            await self._async_ensure()
        else:
            await self.async_remove()

    async def _async_ensure(self) -> None:
        state = self.state
        user = await self.hass.auth.async_get_user(state["user_id"]) if state.get("user_id") else None
        if user is None:
            # Home Assistant makes the first real user the owner. Never let the decoy
            # become that user: only create it when a human account already exists.
            if not any(not u.system_generated for u in await self.hass.auth.async_get_users()):
                _LOGGER.warning("Bastion decoy not created: no user exists yet")
                return
            user = await self.hass.auth.async_create_user(CANARY_USER, group_ids=[GROUP_ID_READ_ONLY], local_only=True)
            if user.is_owner or user.is_admin:
                await self.hass.auth.async_remove_user(user)
                _LOGGER.error("Bastion decoy user would have elevated rights, removed")
                return
            state["user_id"] = user.id
            state.pop("token_id", None)
        token = self.hass.auth.async_get_refresh_token(state["token_id"]) if state.get("token_id") else None
        if token is None:
            token = await self.hass.auth.async_create_refresh_token(
                user,
                client_name=CANARY_CLIENT,
                token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
                access_token_expiration=timedelta(days=3650),
            )
            state["token_id"] = token.id
            state["token"] = self.hass.auth.async_create_access_token(token)
            state["created"] = dt_util.utcnow().isoformat()
        if not state.get("webhook_id"):
            state["webhook_id"] = secrets.token_hex(32)
        self.bastion.guard.canary_ids = {token.id}
        if self._webhook_id is None:
            webhook.async_register(
                self.hass,
                DOMAIN,
                "Bastion",
                state["webhook_id"],
                self._async_handle_webhook,
                local_only=False,
                allowed_methods=("GET", "POST", "PUT", "HEAD"),
            )
            self._webhook_id = state["webhook_id"]
        self.bastion.schedule_save()

    async def async_remove(self) -> None:
        """Delete decoy user, token and webhook."""
        self.unload()
        state = self.state
        if state.get("user_id"):
            user = await self.hass.auth.async_get_user(state["user_id"])
            if user is not None and user.name == CANARY_USER and not user.is_owner:
                await self.hass.auth.async_remove_user(user)
        triggers = state.get("triggers", [])
        state.clear()
        if triggers:
            state["triggers"] = triggers
        self.bastion.guard.canary_ids = set()
        self.bastion.schedule_save()

    def unload(self) -> None:
        """Unregister the webhook (state is kept)."""
        if self._webhook_id is not None:
            webhook.async_unregister(self.hass, self._webhook_id)
            self._webhook_id = None

    # ---------------------------------------------------------------- alarms
    async def _async_handle_webhook(self, hass: HomeAssistant, webhook_id: str, request: web.Request) -> web.Response:
        await self.async_trigger("webhook", request.remote, request.headers.get("User-Agent", "")[:200])
        return web.Response(text="ok")

    @callback
    def on_token_used(self, token: RefreshToken, ip: str | None, agent: str | None) -> None:
        """Called synchronously by the token guard."""
        self.hass.async_create_task(self.async_trigger("token", ip, agent), eager_start=True)

    async def async_trigger(self, via: str, ip: str | None, agent: str | None) -> None:
        """A decoy was used."""
        entry = {"time": dt_util.utcnow().isoformat(), "via": via, "ip": ip or "?", "agent": agent or ""}
        triggers = self.state.setdefault("triggers", [])
        triggers.append(entry)
        del triggers[:-50]
        self.state["last_trigger"] = entry["time"]
        self.bastion.schedule_save()
        data = {"via": via, "ip": ip or "?", "agent": agent or "—"}
        self.hass.bus.async_fire(EVENT_SECURITY, {"type": "canary", **data})
        self.bastion.logins.record("canary", data)
        title, message = event_text("canary", self.hass.config.language, data)
        await self.bastion.notifier.async_send(
            title,
            message,
            key=f"canary_{ip}",
            rate_limit=300,
            actions=self.bastion.responder.actions_for("canary", data),
        )
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    @property
    def alarm_active(self) -> bool:
        """True within 24 h after a trigger."""
        last = dt_util.parse_datetime(self.state.get("last_trigger") or "")
        return last is not None and dt_util.utcnow() - last < ALARM_HOLD

    # ---------------------------------------------------------------- output
    def webhook_url(self) -> str | None:
        """Full URL of the decoy webhook."""
        webhook_id = self.state.get("webhook_id")
        if not webhook_id:
            return None
        try:
            base = get_url(self.hass, prefer_external=True)
        except NoURLAvailableError:
            base = "http://homeassistant.local:8123"
        return f"{base}{webhook.async_generate_path(webhook_id)}"

    def base_url(self) -> str:
        """URL an intruder would use."""
        try:
            return get_url(self.hass, prefer_external=True)
        except NoURLAvailableError:
            return "http://homeassistant.local:8123"

    def decoy_text(self) -> str | None:
        """Content of the decoy file that is placed in the git repository."""
        if not self.state.get("token"):
            return None
        return (
            "# Home Assistant API access (backup sync)\n"
            f"HA_URL={self.base_url()}\n"
            f"HA_TOKEN={self.state['token']}\n"
            f"HA_BACKUP_WEBHOOK={self.webhook_url()}\n"
        )

    def summary(self) -> dict[str, Any]:
        """For the panel (admin only)."""
        state = self.state
        return {
            "enabled": bool(self.bastion.options.get(CONF_CANARY_ENABLED)),
            "token": state.get("token"),
            "webhook_url": self.webhook_url(),
            "created": state.get("created"),
            "triggers": list(reversed(state.get("triggers", [])))[:20],
            "alarm": self.alarm_active,
        }
