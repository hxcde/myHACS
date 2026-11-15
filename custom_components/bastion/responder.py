"""Reactions to security events: actionable notifications and blocking.

Every notification about a login, a new token or a new user can carry two
buttons in the Companion App: "That was me" and "Block". Blocking revokes the
token, bans the IP and/or deactivates the user. Each button carries a random
nonce bound to one pending action, so actions cannot be replayed or forged.
"""

from __future__ import annotations

from datetime import timedelta
import ipaddress
import logging
import secrets
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import CONF_NOTIFY_ACTIONS, EVENT_SECURITY
from .texts import action_text

_LOGGER = logging.getLogger(__name__)

ACTION_EVENT = "mobile_app_notification_action"
PREFIX = "BASTION_"
PENDING_TTL = timedelta(hours=48)

# event kind -> what "block" does
BLOCKABLE = {
    "login": ("token", "ip"),
    "new_ip": ("token", "ip"),
    "token_new_ip": ("token", "ip"),
    "token_created": ("token",),
    "user_added": ("user",),
    "admin_granted": ("user",),
    "user_activated": ("user",),
    "unusual_action": ("user",),
    "brute_force": ("ip",),
    "canary": ("ip",),
}
CONFIRMABLE = {
    "login",
    "new_ip",
    "token_new_ip",
    "token_created",
    "user_added",
    "admin_granted",
    "user_activated",
    "unusual_action",
}


class Responder:
    """Builds notification actions and executes them."""

    def __init__(self, hass: HomeAssistant, bastion) -> None:
        """Init."""
        self.hass = hass
        self.bastion = bastion
        self._unsub: CALLBACK_TYPE | None = None

    @property
    def _pending(self) -> dict[str, dict[str, Any]]:
        return self.bastion.data.setdefault("pending_actions", {})

    def setup(self) -> None:
        """Listen for button presses."""
        self._unsub = self.hass.bus.async_listen(ACTION_EVENT, self._on_action, self._filter)

    def unload(self) -> None:
        """Stop listening."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    # ------------------------------------------------------------- building
    def actions_for(self, kind: str, data: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Notification actions for an event, or None."""
        if kind not in BLOCKABLE or not self.bastion.options.get(CONF_NOTIFY_ACTIONS, True):
            return None
        targets = {
            "ip": data.get("ip") if data.get("ip") not in (None, "?") else None,
            "token_id": data.get("token_id"),
            "user_id": data.get("user_id"),
        }
        if not any(targets[k] for k in ("ip", "token_id", "user_id")):
            return None
        self._prune()
        nonce = secrets.token_urlsafe(12)
        self._pending[nonce] = {
            "kind": kind,
            "created": dt_util.utcnow().isoformat(),
            "summary": data.get("user") or data.get("ip") or data.get("name") or kind,
            **targets,
        }
        self.bastion.schedule_save()
        language = self.hass.config.language
        actions = []
        if kind in CONFIRMABLE:
            actions.append({"action": f"{PREFIX}OK_{nonce}", "title": action_text("ok", language)})
        actions.append(
            {
                "action": f"{PREFIX}BLOCK_{nonce}",
                "title": action_text("block", language),
                "destructive": True,
                "authenticationRequired": True,
            }
        )
        return actions

    def _prune(self) -> None:
        cutoff = dt_util.utcnow() - PENDING_TTL
        for nonce, item in list(self._pending.items()):
            created = dt_util.parse_datetime(item.get("created", ""))
            if created is None or created < cutoff:
                self._pending.pop(nonce)

    # ------------------------------------------------------------- handling
    @callback
    def _filter(self, event_data: dict[str, Any]) -> bool:
        return str(event_data.get("action", "")).startswith(PREFIX)

    @callback
    def _on_action(self, event: Event) -> None:
        self.hass.async_create_task(self._async_handle(event), eager_start=True)

    async def _async_handle(self, event: Event) -> None:
        action = str(event.data.get("action", ""))
        verb, _, nonce = action.removeprefix(PREFIX).partition("_")
        user_id = event.context.user_id
        if user_id is not None:
            user = await self.hass.auth.async_get_user(user_id)
            if user is None or not user.is_admin:
                _LOGGER.warning("Bastion action %s ignored: user is not an administrator", verb)
                return
        self._prune()
        item = self._pending.pop(nonce, None)
        language = self.hass.config.language
        if item is None:
            await self.bastion.notifier.async_send("Bastion", action_text("expired", language), key="action_result")
            return
        if verb == "OK":
            result = [action_text("confirmed", language, what=item.get("summary"))]
            await self._async_log("confirmed", item, result, user_id)
        elif verb == "BLOCK":
            result = await self.async_block(
                ip=item.get("ip") if "ip" in BLOCKABLE[item["kind"]] else None,
                token_id=item.get("token_id") if "token" in BLOCKABLE[item["kind"]] else None,
                user_id=item.get("user_id") if "user" in BLOCKABLE[item["kind"]] else None,
                actor_id=user_id,
            )
            await self._async_log("blocked", item, result, user_id)
        else:
            return
        self.bastion.schedule_save()
        await self.bastion.notifier.async_send("Bastion", "\n".join(result), key="action_result")

    async def _async_log(self, kind: str, item: dict[str, Any], result: list[str], actor: str | None) -> None:
        data = {
            "source": item.get("kind"),
            "ip": item.get("ip"),
            "user_id": item.get("user_id"),
            "token_id": item.get("token_id"),
            "result": "; ".join(result),
            "actor": actor,
        }
        self.bastion.logins.record(kind, data)
        self.hass.bus.async_fire(EVENT_SECURITY, {"type": kind, **data})

    # ------------------------------------------------------------- blocking
    async def async_block(
        self,
        *,
        ip: str | None = None,
        token_id: str | None = None,
        user_id: str | None = None,
        actor_id: str | None = None,
    ) -> list[str]:
        """Revoke a token, ban an IP and/or deactivate a user."""
        language = self.hass.config.language
        out: list[str] = []
        if token_id:
            token = self.hass.auth.async_get_refresh_token(token_id)
            if token is not None and token.user.id != actor_id:
                self.hass.auth.async_remove_refresh_token(token)
                out.append(action_text("token_revoked", language, name=token.client_name or token_id[:8]))
            elif token is not None:
                out.append(action_text("own_token", language))
        if ip:
            out.append(await self._async_ban(ip, language))
        if user_id:
            user = await self.hass.auth.async_get_user(user_id)
            if user is None:
                pass
            elif user.is_owner or user.system_generated or user.id == actor_id:
                out.append(action_text("user_protected", language, user=user.name))
            elif user.is_active:
                await self.hass.auth.async_deactivate_user(user)
                out.append(action_text("user_deactivated", language, user=user.name))
        return out or [action_text("nothing", language)]

    async def _async_ban(self, ip: str, language: str) -> str:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return action_text("ban_invalid", language, ip=ip)
        http = getattr(self.hass, "http", None)
        proxies = list(getattr(http, "trusted_proxies", []) or [])
        if addr.is_loopback or addr.is_unspecified or any(addr in net for net in proxies):
            return action_text("ban_protected", language, ip=ip)
        try:
            from homeassistant.components.http.ban import KEY_BAN_MANAGER  # noqa: PLC0415
        except ImportError:
            return action_text("ban_unavailable", language, ip=ip)
        manager = http.app.get(KEY_BAN_MANAGER) if http is not None else None
        if manager is None:
            return action_text("ban_unavailable", language, ip=ip)
        await manager.async_add_ban(addr)
        return action_text("ip_banned", language, ip=ip)
