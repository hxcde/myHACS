"""Token guard: observes every access token validation.

Home Assistant does not record when a long-lived access token is used (its
"last used" only changes when a refresh token creates a new access token).
The guard wraps ``hass.auth.async_validate_access_token`` to

* record usage time and client IP of long-lived tokens,
* reject decoy (canary) tokens and report their use immediately.

The wrapper never raises and always falls back to the original result.
"""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN, RefreshToken
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.http import current_request

_LOGGER = logging.getLogger(__name__)

_ATTR = "async_validate_access_token"
_MARK = "_bastion_guard"


class TokenGuard:
    """Installs the validation wrapper."""

    def __init__(
        self,
        hass: HomeAssistant,
        on_used: Callable[[RefreshToken, str | None], None],
        on_canary: Callable[[RefreshToken, str | None, str | None], None],
    ) -> None:
        """Init."""
        self.hass = hass
        self.canary_ids: set[str] = set()
        self._on_used = on_used
        self._on_canary = on_canary

    def install(self) -> None:
        """Wrap the validation method of the auth manager."""
        auth = self.hass.auth
        current = getattr(auth, _ATTR)
        if getattr(current, _MARK, False):
            return
        original = current

        @callback
        def guarded(token: str) -> RefreshToken | None:
            result = original(token)
            if result is None:
                return None
            try:
                request = current_request.get()
                ip = request.remote if request is not None else None
                if result.id in self.canary_ids:
                    agent = request.headers.get("User-Agent", "")[:200] if request is not None else None
                    self._on_canary(result, ip, agent)
                    return None
                if result.token_type == TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN:
                    self._on_used(result, ip)
            except Exception:  # noqa: BLE001 - authentication must never break
                _LOGGER.exception("Bastion token guard failed")
            return result

        setattr(guarded, _MARK, True)
        setattr(auth, _ATTR, guarded)

    def uninstall(self) -> None:
        """Restore the original method."""
        auth = self.hass.auth
        if getattr(auth.__dict__.get(_ATTR), _MARK, False):
            delattr(auth, _ATTR)
