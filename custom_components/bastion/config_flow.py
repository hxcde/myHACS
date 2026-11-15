"""Config and options flow."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)
import probatio

from .audit import CHECK_GROUPS
from .const import (
    ALL_AREAS,
    CONF_ANOMALY_ACTIONS,
    CONF_ANOMALY_ENTITIES,
    CONF_ANOMALY_LOGIN_TIME,
    CONF_ANOMALY_OUTBOUND,
    CONF_ANOMALY_SABOTAGE,
    CONF_ANOMALY_SENSITIVITY,
    CONF_AUDIT_INTERVAL,
    CONF_BRUTE_FORCE_THRESHOLD,
    CONF_DISABLED_CHECKS,
    CONF_GEOIP,
    CONF_GIT_ALLOW_UNVERIFIED_PRIVATE,
    CONF_GIT_AREAS,
    CONF_GIT_AUTH,
    CONF_GIT_AUTHOR_EMAIL,
    CONF_GIT_AUTHOR_NAME,
    CONF_GIT_BRANCH,
    CONF_GIT_DAILY_TIME,
    CONF_GIT_DEBOUNCE,
    CONF_GIT_ENABLED,
    CONF_GIT_ESPHOME_PATH,
    CONF_GIT_EXTRA_PATHS,
    CONF_GIT_HOST_KEY,
    CONF_GIT_PASSPHRASE,
    CONF_GIT_PRIVATE_KEY,
    CONF_GIT_PUBLIC_KEY,
    CONF_GIT_SALT,
    CONF_GIT_TOKEN,
    CONF_GIT_URL,
    CONF_GIT_USERNAME,
    CONF_GIT_Z2M_PATH,
    CONF_GITHUB_TOKEN,
    CONF_MAX_ADMINS,
    CONF_NOTIFY_LOGINS,
    CONF_NOTIFY_MIN_SEVERITY,
    CONF_NOTIFY_PUBLIC_ONLY,
    CONF_NOTIFY_TARGETS,
    CONF_PROBE_INTERVAL,
    CONF_PROBE_TOKEN,
    CONF_PROBE_URL,
    CONF_REPAIRS_MIN_SEVERITY,
    CONF_SABOTAGE_COUNT,
    CONF_SABOTAGE_WINDOW,
    CONF_TOKEN_MAX_AGE_DAYS,
    CONF_TOKEN_UNUSED_DAYS,
    DEFAULT_OPTIONS,
    DOMAIN,
    GIT_AUTH_NONE,
    GIT_AUTH_SSH,
    GIT_AUTH_TOKEN,
    NAME,
)
from .crypto import new_salt
from .gitsync.remote import RemoteError, generate_ssh_keypair, parse_remote, safe_branch

_LOGGER = logging.getLogger(__name__)

SEVERITIES = ["critical", "high", "medium", "low"]
KEEP = "keep_existing"


def _select(options: list[str], key: str, multiple: bool = False) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            translation_key=key,
            multiple=multiple,
            mode=SelectSelectorMode.DROPDOWN if not multiple else SelectSelectorMode.LIST,
        )
    )


def _number(minimum: float, maximum: float, step: float = 1, unit: str | None = None) -> NumberSelector:
    config = NumberSelectorConfig(min=minimum, max=maximum, step=step, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
_TEXT = TextSelector()
_TEXT_LIST = TextSelector(TextSelectorConfig(multiple=True))
_URL = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))


class BastionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup: nothing to ask, configuration happens in the options."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm and create."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={}, options=dict(DEFAULT_OPTIONS))
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options flow."""
        return BastionOptionsFlow()


class BastionOptionsFlow(OptionsFlow):
    """Menu based options."""

    def __init__(self) -> None:
        """Init."""
        self._git: dict[str, Any] = {}

    @property
    def _opts(self) -> dict[str, Any]:
        return {**DEFAULT_OPTIONS, **(self.config_entry.options or {})}

    def _save(self, changes: dict[str, Any]) -> ConfigFlowResult:
        return self.async_create_entry(data={**self._opts, **changes})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Main menu."""
        return self.async_show_menu(step_id="init", menu_options=["audit", "notifications", "git", "probe", "anomaly"])

    # ------------------------------------------------------------------ audit
    async def async_step_audit(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Audit options."""
        opts = self._opts
        if user_input is not None:
            token = user_input.pop(CONF_GITHUB_TOKEN, "") or ""
            if token == KEEP or (not token and opts.get(CONF_GITHUB_TOKEN)):
                token = opts.get(CONF_GITHUB_TOKEN, "")
            if user_input.pop("clear_github_token", False):
                token = ""
            return self._save(
                {
                    **_ints(
                        user_input,
                        CONF_AUDIT_INTERVAL,
                        CONF_MAX_ADMINS,
                        CONF_TOKEN_MAX_AGE_DAYS,
                        CONF_TOKEN_UNUSED_DAYS,
                    ),
                    CONF_GITHUB_TOKEN: token,
                }
            )
        schema = probatio.Schema(
            {
                probatio.Required(CONF_AUDIT_INTERVAL, default=opts[CONF_AUDIT_INTERVAL]): _number(1, 168, unit="h"),
                probatio.Required(CONF_REPAIRS_MIN_SEVERITY, default=opts[CONF_REPAIRS_MIN_SEVERITY]): _select(
                    SEVERITIES, "severity"
                ),
                probatio.Required(CONF_MAX_ADMINS, default=opts[CONF_MAX_ADMINS]): _number(1, 50),
                probatio.Required(CONF_TOKEN_MAX_AGE_DAYS, default=opts[CONF_TOKEN_MAX_AGE_DAYS]): _number(
                    30, 3650, unit="d"
                ),
                probatio.Required(CONF_TOKEN_UNUSED_DAYS, default=opts[CONF_TOKEN_UNUSED_DAYS]): _number(
                    7, 3650, unit="d"
                ),
                probatio.Optional(CONF_DISABLED_CHECKS, default=opts[CONF_DISABLED_CHECKS]): _select(
                    list(CHECK_GROUPS), "check_group", multiple=True
                ),
                probatio.Optional(CONF_GITHUB_TOKEN, default=""): _PASSWORD,
                probatio.Optional("clear_github_token", default=False): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="audit",
            data_schema=schema,
            description_placeholders={"token_state": "✔" if opts.get(CONF_GITHUB_TOKEN) else "—"},
        )

    # ---------------------------------------------------------- notifications
    async def async_step_notifications(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Notification options."""
        opts = self._opts
        if user_input is not None:
            user_input[CONF_NOTIFY_TARGETS] = [
                t.strip() for t in user_input.get(CONF_NOTIFY_TARGETS) or [] if t.strip()
            ]
            return self._save(_ints(user_input, CONF_BRUTE_FORCE_THRESHOLD))
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_NOTIFY_TARGETS, default=opts[CONF_NOTIFY_TARGETS]): _TEXT_LIST,
                probatio.Required(CONF_NOTIFY_MIN_SEVERITY, default=opts[CONF_NOTIFY_MIN_SEVERITY]): _select(
                    SEVERITIES, "severity"
                ),
                probatio.Required(CONF_NOTIFY_LOGINS, default=opts[CONF_NOTIFY_LOGINS]): BooleanSelector(),
                probatio.Required(CONF_NOTIFY_PUBLIC_ONLY, default=opts[CONF_NOTIFY_PUBLIC_ONLY]): BooleanSelector(),
                probatio.Required(CONF_BRUTE_FORCE_THRESHOLD, default=opts[CONF_BRUTE_FORCE_THRESHOLD]): _number(
                    2, 100
                ),
                probatio.Required(CONF_GEOIP, default=opts[CONF_GEOIP]): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="notifications", data_schema=schema)

    # -------------------------------------------------------------------- git
    async def async_step_git(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Repository, authentication and content."""
        opts = self._opts
        errors: dict[str, str] = {}
        if user_input is not None:
            git = dict(user_input)
            git[CONF_GIT_URL] = (git.get(CONF_GIT_URL) or "").strip()
            git[CONF_GIT_EXTRA_PATHS] = [p.strip() for p in git.get(CONF_GIT_EXTRA_PATHS) or [] if p.strip()]
            git[CONF_GIT_DEBOUNCE] = int(git.get(CONF_GIT_DEBOUNCE) or 120)
            for secret_key in (CONF_GIT_TOKEN, CONF_GIT_PASSPHRASE):
                if not git.get(secret_key):
                    git[secret_key] = opts.get(secret_key, "")
            if git.pop("clear_passphrase", False):
                git[CONF_GIT_PASSPHRASE] = ""
            if git[CONF_GIT_PASSPHRASE] != opts.get(CONF_GIT_PASSPHRASE) or not opts.get(CONF_GIT_SALT):
                git[CONF_GIT_SALT] = new_salt() if git[CONF_GIT_PASSPHRASE] else ""
            else:
                git[CONF_GIT_SALT] = opts.get(CONF_GIT_SALT, "")
            regenerate = git.pop("regenerate_key", False)
            if git[CONF_GIT_URL] != opts.get(CONF_GIT_URL):
                git[CONF_GIT_HOST_KEY] = ""
            else:
                git[CONF_GIT_HOST_KEY] = opts.get(CONF_GIT_HOST_KEY, "")
            if not git.get(CONF_GIT_ENABLED):
                return self._save(git)
            try:
                spec = parse_remote(git[CONF_GIT_URL])
                git[CONF_GIT_BRANCH] = safe_branch(git.get(CONF_GIT_BRANCH) or "main")
            except RemoteError as err:
                errors["base"] = err.reason
            else:
                if spec.kind == "ssh" and git[CONF_GIT_AUTH] != GIT_AUTH_SSH:
                    errors[CONF_GIT_AUTH] = "ssh_needs_key"
                elif spec.kind in ("https", "http") and git[CONF_GIT_AUTH] == GIT_AUTH_SSH:
                    errors[CONF_GIT_AUTH] = "https_needs_token"
                elif spec.kind == "http":
                    errors[CONF_GIT_URL] = "insecure_http"
                elif git[CONF_GIT_AUTH] == GIT_AUTH_TOKEN and not git.get(CONF_GIT_TOKEN):
                    errors[CONF_GIT_TOKEN] = "token_required"
            if not errors:
                if git[CONF_GIT_AUTH] == GIT_AUTH_SSH and (regenerate or not opts.get(CONF_GIT_PRIVATE_KEY)):
                    private, public = await self.hass.async_add_executor_job(
                        generate_ssh_keypair, f"bastion@{self.hass.config.location_name}"
                    )
                    git[CONF_GIT_PRIVATE_KEY] = private
                    git[CONF_GIT_PUBLIC_KEY] = public
                else:
                    git[CONF_GIT_PRIVATE_KEY] = opts.get(CONF_GIT_PRIVATE_KEY, "")
                    git[CONF_GIT_PUBLIC_KEY] = opts.get(CONF_GIT_PUBLIC_KEY, "")
                self._git = git
                if git[CONF_GIT_AUTH] == GIT_AUTH_SSH:
                    return await self.async_step_git_key()
                return await self.async_step_git_test()
        schema = probatio.Schema(
            {
                probatio.Required(CONF_GIT_ENABLED, default=opts[CONF_GIT_ENABLED]): BooleanSelector(),
                probatio.Optional(CONF_GIT_URL, default=opts[CONF_GIT_URL]): _TEXT,
                probatio.Required(CONF_GIT_BRANCH, default=opts[CONF_GIT_BRANCH]): _TEXT,
                probatio.Required(CONF_GIT_AUTH, default=opts[CONF_GIT_AUTH]): _select(
                    [GIT_AUTH_SSH, GIT_AUTH_TOKEN, GIT_AUTH_NONE], "git_auth"
                ),
                probatio.Optional(CONF_GIT_USERNAME, default=opts[CONF_GIT_USERNAME]): _TEXT,
                probatio.Optional(CONF_GIT_TOKEN, default=""): _PASSWORD,
                probatio.Optional("regenerate_key", default=False): BooleanSelector(),
                probatio.Optional(CONF_GIT_PASSPHRASE, default=""): _PASSWORD,
                probatio.Optional("clear_passphrase", default=False): BooleanSelector(),
                probatio.Required(CONF_GIT_AREAS, default=opts[CONF_GIT_AREAS]): _select(
                    ALL_AREAS, "git_area", multiple=True
                ),
                probatio.Optional(CONF_GIT_ESPHOME_PATH, default=opts[CONF_GIT_ESPHOME_PATH]): _TEXT,
                probatio.Optional(CONF_GIT_Z2M_PATH, default=opts[CONF_GIT_Z2M_PATH]): _TEXT,
                probatio.Optional(CONF_GIT_EXTRA_PATHS, default=opts[CONF_GIT_EXTRA_PATHS]): _TEXT_LIST,
                probatio.Required(CONF_GIT_DEBOUNCE, default=opts[CONF_GIT_DEBOUNCE]): _number(30, 86400, unit="s"),
                probatio.Required(CONF_GIT_DAILY_TIME, default=opts[CONF_GIT_DAILY_TIME]): TimeSelector(),
                probatio.Required(CONF_GIT_AUTHOR_NAME, default=opts[CONF_GIT_AUTHOR_NAME]): _TEXT,
                probatio.Required(CONF_GIT_AUTHOR_EMAIL, default=opts[CONF_GIT_AUTHOR_EMAIL]): _TEXT,
                probatio.Required(
                    CONF_GIT_ALLOW_UNVERIFIED_PRIVATE, default=opts[CONF_GIT_ALLOW_UNVERIFIED_PRIVATE]
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="git",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "token_state": "✔" if opts.get(CONF_GIT_TOKEN) else "—",
                "passphrase_state": "✔" if opts.get(CONF_GIT_PASSPHRASE) else "—",
            },
        )

    async def async_step_git_key(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the public key to add as deploy key."""
        if user_input is not None:
            return await self.async_step_git_test()
        return self.async_show_form(
            step_id="git_key",
            data_schema=probatio.Schema({}),
            description_placeholders={"public_key": self._git[CONF_GIT_PUBLIC_KEY], "url": self._git[CONF_GIT_URL]},
        )

    async def async_step_git_test(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Connect, show host key and privacy, then save."""
        from .gitsync.manager import async_test_connection  # noqa: PLC0415

        git = self._git
        if user_input is not None:
            return self._save(git)
        errors: dict[str, str] = {}
        placeholders = {"fingerprint": "—", "privacy": "—", "refs": "0", "error": ""}
        try:
            result = await async_test_connection(self.hass, {**self._opts, **git})
        except RemoteError as err:
            errors["base"] = err.reason if err.reason in _GIT_ERRORS else "cannot_connect"
            placeholders["error"] = (err.detail or str(err))[:300]
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Git connection test failed")
            errors["base"] = "cannot_connect"
            placeholders["error"] = str(err)[:300]
        else:
            git[CONF_GIT_HOST_KEY] = result["host_key"]
            placeholders.update(
                fingerprint=result["host_key_fp"] or "—",
                privacy=result["privacy"],
                refs=str(result["refs"]),
            )
            if result["privacy"] == "public":
                errors["base"] = "repo_public"
            elif result["privacy"] == "unknown" and not git.get(CONF_GIT_ALLOW_UNVERIFIED_PRIVATE):
                errors["base"] = "repo_unverified"
        if errors:
            return self.async_show_form(
                step_id="git_test_failed",
                data_schema=probatio.Schema({}),
                errors=errors,
                description_placeholders=placeholders,
            )
        return self.async_show_form(
            step_id="git_test",
            data_schema=probatio.Schema({}),
            description_placeholders=placeholders,
        )

    async def async_step_git_test_failed(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Back to the git form after a failed test."""
        return await self.async_step_git()

    # ------------------------------------------------------------------ probe
    async def async_step_probe(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """External probe options."""
        opts = self._opts
        errors: dict[str, str] = {}
        if user_input is not None:
            url = (user_input.get(CONF_PROBE_URL) or "").strip()
            token = user_input.get(CONF_PROBE_TOKEN) or opts.get(CONF_PROBE_TOKEN, "")
            if user_input.get("clear_probe_token"):
                token = ""
            if url and not url.startswith("https://"):
                errors[CONF_PROBE_URL] = "https_required"
            else:
                return self._save(
                    {
                        CONF_PROBE_URL: url,
                        CONF_PROBE_TOKEN: token,
                        CONF_PROBE_INTERVAL: int(user_input[CONF_PROBE_INTERVAL]),
                    }
                )
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_PROBE_URL, default=opts[CONF_PROBE_URL]): _URL,
                probatio.Optional(CONF_PROBE_TOKEN, default=""): _PASSWORD,
                probatio.Optional("clear_probe_token", default=False): BooleanSelector(),
                probatio.Required(CONF_PROBE_INTERVAL, default=opts[CONF_PROBE_INTERVAL]): _number(1, 720, unit="h"),
            }
        )
        return self.async_show_form(
            step_id="probe",
            data_schema=schema,
            errors=errors,
            description_placeholders={"token_state": "✔" if opts.get(CONF_PROBE_TOKEN) else "—"},
        )

    # ---------------------------------------------------------------- anomaly
    async def async_step_anomaly(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Anomaly options."""
        opts = self._opts
        if user_input is not None:
            user_input[CONF_ANOMALY_SENSITIVITY] = float(user_input[CONF_ANOMALY_SENSITIVITY])
            return self._save(_ints(user_input, CONF_SABOTAGE_COUNT, CONF_SABOTAGE_WINDOW))
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_ANOMALY_ENTITIES, default=opts[CONF_ANOMALY_ENTITIES]): EntitySelector(
                    EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                probatio.Required(CONF_ANOMALY_SENSITIVITY, default=opts[CONF_ANOMALY_SENSITIVITY]): _number(2, 8, 0.5),
                probatio.Required(CONF_ANOMALY_LOGIN_TIME, default=opts[CONF_ANOMALY_LOGIN_TIME]): BooleanSelector(),
                probatio.Required(CONF_ANOMALY_ACTIONS, default=opts[CONF_ANOMALY_ACTIONS]): BooleanSelector(),
                probatio.Required(CONF_ANOMALY_SABOTAGE, default=opts[CONF_ANOMALY_SABOTAGE]): BooleanSelector(),
                probatio.Required(CONF_SABOTAGE_COUNT, default=opts[CONF_SABOTAGE_COUNT]): _number(2, 20),
                probatio.Required(CONF_SABOTAGE_WINDOW, default=opts[CONF_SABOTAGE_WINDOW]): _number(
                    10, 3600, unit="s"
                ),
                probatio.Required(CONF_ANOMALY_OUTBOUND, default=opts[CONF_ANOMALY_OUTBOUND]): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="anomaly", data_schema=schema)


_GIT_ERRORS = {
    "auth_failed",
    "cannot_connect",
    "host_key_mismatch",
    "invalid_key",
    "invalid_url",
    "invalid_branch",
    "missing_key",
    "repo_not_found",
    "protocol_error",
}


def _ints(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    out = dict(data)
    for key in keys:
        if key in out and out[key] is not None:
            out[key] = int(out[key])
    return out
