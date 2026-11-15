"""Git sync orchestration inside Home Assistant."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import logging
import os
import shutil
import time
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CALL_SERVICE, __version__ as HA_VERSION
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_custom_components
from homeassistant.util import dt as dt_util

from ..const import (
    AREA_ADDONS,
    AREA_CONFIG,
    AREA_ESPHOME,
    AREA_EXTRA,
    AREA_INVENTORY,
    AREA_STORAGE,
    AREA_Z2M,
    CONF_CANARY_GIT,
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
    EVENT_SECURITY,
    SIGNAL_UPDATE,
    STORAGE_KEY_GIT,
    STORAGE_VERSION,
    WORK_DIR,
    Category,
    Severity,
)
from ..crypto import DecryptionError, FileCipher
from ..models import Finding, make_finding
from ..texts import README, lang, misc
from . import collector, repo as gitrepo
from .remote import (
    HostKeyMismatch,
    RemoteContext,
    RemoteError,
    RemoteSpec,
    anonymous_refs_url,
    parse_remote,
    safe_branch,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)
PRIVACY_RECHECK = 6 * 3600
PUSH_RETRY = 15 * 60
UI_ACTIVITY_WINDOW = 300
PENDING_RESTORE = "pending_restore.json"

UI_EVENTS = (
    "automation_reloaded",
    "script_reloaded",
    "scene_reloaded",
    "lovelace_updated",
    "core_config_updated",
    "area_registry_updated",
    "floor_registry_updated",
    "label_registry_updated",
    "entity_registry_updated",
    "device_registry_updated",
    "category_registry_updated",
    "panels_updated",
)


@dataclass(slots=True)
class GitState:
    """Persisted runtime state."""

    last_commit: str | None = None
    last_commit_time: str | None = None
    last_commit_summary: str | None = None
    last_push_ok: bool | None = None
    last_push_time: str | None = None
    last_error: str | None = None
    last_error_reason: str | None = None
    pending_push: bool = False
    privacy: str | None = None  # private | public | unknown
    host_key: str | None = None
    host_key_fp: str | None = None
    host_key_mismatch: str | None = None
    skipped_secrets: list[str] | None = None


def get_git_options(options: dict[str, Any]) -> dict[str, Any]:
    """Return git related options."""
    return {k: v for k, v in options.items() if k.startswith("git_")}


def build_context(options: dict[str, Any], host_key: str | None = None, on_new=None) -> RemoteContext:
    """RemoteContext from options."""
    spec = parse_remote(options[CONF_GIT_URL])
    return RemoteContext(
        spec=spec,
        auth=options.get(CONF_GIT_AUTH, "ssh"),
        username=options.get(CONF_GIT_USERNAME, ""),
        token=options.get(CONF_GIT_TOKEN, ""),
        private_key=options.get(CONF_GIT_PRIVATE_KEY, ""),
        host_key=host_key if host_key is not None else options.get(CONF_GIT_HOST_KEY, ""),
        on_new_host_key=on_new,
    )


async def async_check_privacy(hass: HomeAssistant, spec: RemoteSpec) -> str:
    """Return 'public', 'private' or 'unknown' for a remote."""
    if spec.kind == "local":
        return "private"
    url = anonymous_refs_url(spec)
    if url is None:
        return "unknown"
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=15),
            allow_redirects=True,
            headers={"User-Agent": "git/2.45.0 (bastion)"},
        ) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if resp.status == 200 and "git-upload-pack-advertisement" in ctype:
                return "public"
            if resp.status in (401, 403, 404):
                return "private"
            return "unknown"
    except (aiohttp.ClientError, TimeoutError):
        return "unknown"


def apply_pending_restore(config_dir: str) -> int:
    """Move staged .storage files into place. Called while HA shuts down."""
    work = os.path.join(config_dir, WORK_DIR)
    manifest_path = os.path.join(work, PENDING_RESTORE)
    if not os.path.isfile(manifest_path):
        return 0
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    storage_dir = os.path.realpath(os.path.join(config_dir, ".storage"))
    applied = 0
    for item in manifest.get("files", []):
        staged = item.get("staged", "")
        target = os.path.realpath(item.get("target", ""))
        if os.path.dirname(target) != storage_dir or not os.path.isfile(staged):
            continue
        os.replace(staged, target)
        applied += 1
    os.remove(manifest_path)
    shutil.rmtree(os.path.join(work, "staged"), ignore_errors=True)
    return applied


class GitSyncManager:
    """Keeps the configuration in a private git repository."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, notifier) -> None:
        """Init."""
        self.hass = hass
        self.entry = entry
        self.notifier = notifier
        self.config_dir = hass.config.path()
        self.work_dir = hass.config.path(WORK_DIR)
        self.repo_path = os.path.join(self.work_dir, "repo.git")
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY_GIT)
        self.state = GitState()
        self._lock = asyncio.Lock()
        self._unsubs: list[CALLBACK_TYPE] = []
        self._signature: str | None = None
        self._config_signature: str | None = None
        self._dirty_since: float | None = None
        self._external_files: set[str] = set()
        self._activity: deque[tuple[float, str | None]] = deque(maxlen=200)
        self._users_since_commit: set[str] = set()
        self._cipher_cache: tuple[str, str, FileCipher] | None = None
        self._privacy_checked: float | None = None
        self._last_push_try: float | None = None
        self._new_host_key: tuple[str, str] | None = None
        self._last_config_files: dict[str, tuple[int, int]] = {}
        # Set by the coordinator: returns the decoy file content or None.
        self.decoy: Callable[[], str | None] | None = None

    # ------------------------------------------------------------ lifecycle
    @property
    def options(self) -> dict[str, Any]:
        """Effective options."""
        from .. import get_options  # noqa: PLC0415 - avoid import cycle

        return get_options(self.entry)

    @property
    def enabled(self) -> bool:
        """True if sync is configured."""
        opts = self.options
        return bool(opts.get(CONF_GIT_ENABLED) and opts.get(CONF_GIT_URL))

    async def async_setup(self) -> None:
        """Load state and start timers."""
        if (data := await self._store.async_load()) is not None:
            for key, value in data.items():
                if hasattr(self.state, key):
                    setattr(self.state, key, value)
        if not self.enabled:
            return
        self._unsubs.append(async_track_time_interval(self.hass, self._async_tick, SCAN_INTERVAL))
        h, m, s = (int(x) for x in (self.options.get(CONF_GIT_DAILY_TIME) or "03:17:00").split(":"))
        self._unsubs.append(async_track_time_change(self.hass, self._async_daily, hour=h, minute=m, second=s))
        for event_type in UI_EVENTS:
            self._unsubs.append(self.hass.bus.async_listen(event_type, self._on_ui_event))
        self._unsubs.append(self.hass.bus.async_listen(EVENT_CALL_SERVICE, self._on_service_call, self._service_filter))

    async def async_unload(self) -> None:
        """Stop timers."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    async def _async_save_state(self) -> None:
        await self._store.async_save(_state_dict(self.state))
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    # ------------------------------------------------------- activity tracking
    @callback
    def _service_filter(self, event_data: dict[str, Any]) -> bool:
        service = str(event_data.get("service", ""))
        return service.startswith("reload") or service in ("create", "update", "delete")

    @callback
    def _on_service_call(self, event: Event) -> None:
        self._record_activity(event.context.user_id)

    @callback
    def _on_ui_event(self, event: Event) -> None:
        self._record_activity(event.context.user_id)

    @callback
    def _record_activity(self, user_id: str | None) -> None:
        self._activity.append((time.monotonic(), user_id))
        if user_id:
            self._users_since_commit.add(user_id)

    def _recent_ui_activity(self) -> bool:
        cutoff = time.monotonic() - UI_ACTIVITY_WINDOW
        return any(ts >= cutoff for ts, _ in self._activity)

    # ------------------------------------------------------------- triggers
    async def _async_tick(self, _now: datetime | None = None) -> None:
        if not self.enabled or self.state.host_key_mismatch:
            return
        try:
            generated = await self._async_generated_files()
            signature, config_files = await self.hass.async_add_executor_job(self._sync_signature, generated)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Bastion git change scan failed")
            return
        if self._signature is None:
            self._signature = signature
            self._last_config_files = config_files
            if self.state.last_commit is None:
                await self.async_commit(trigger="initial")
            return
        if signature != self._signature:
            changed_config = [path for path, sig in config_files.items() if self._last_config_files.get(path) != sig]
            if changed_config and not self._recent_ui_activity():
                self._external_files.update(changed_config)
                await self._async_report_external(changed_config)
            self._signature = signature
            self._last_config_files = config_files
            self._dirty_since = time.monotonic()
        debounce = int(self.options.get(CONF_GIT_DEBOUNCE) or 120)
        if self._dirty_since is not None and time.monotonic() - self._dirty_since >= debounce:
            self._dirty_since = None
            await self.async_commit(trigger="auto")
        elif self.state.pending_push and (
            self._last_push_try is None or time.monotonic() - self._last_push_try >= PUSH_RETRY
        ):
            await self.async_commit(trigger="auto")

    async def _async_daily(self, _now: datetime) -> None:
        if self.enabled:
            await self.async_commit(trigger="daily")

    async def _async_report_external(self, files: list[str]) -> None:
        language = self.hass.config.language
        shown = ", ".join(sorted(files)[:10])
        self.hass.bus.async_fire(EVENT_SECURITY, {"type": "external_config_change", "files": sorted(files)})
        from ..texts import event_text  # noqa: PLC0415

        title, message = event_text("external_config_change", language, {"files": shown})
        await self.notifier.async_send(title, message, key="external_config_change", rate_limit=1800)

    def _sync_signature(self, generated: list[collector.SourceFile]) -> tuple[str, dict[str, tuple[int, int]]]:
        opts = self.options
        result = self._collect(opts, generated)
        digest = hashlib.sha256()
        config_files: dict[str, tuple[int, int]] = {}
        for src in sorted(result.files, key=lambda f: f.repo_path):
            if src.abs_path:
                try:
                    st = os.stat(src.abs_path)
                except OSError:
                    continue
                sig = (st.st_size, st.st_mtime_ns)
                digest.update(f"{src.repo_path}|{sig[0]}|{sig[1]}\n".encode())
                if src.area == AREA_CONFIG:
                    config_files[src.repo_path] = sig
            elif src.data is not None:
                digest.update(src.repo_path.encode() + hashlib.sha256(src.data).digest())
        return digest.hexdigest(), config_files

    # ------------------------------------------------------------- helpers
    def _collect(self, opts: dict[str, Any], generated: list[collector.SourceFile]) -> collector.CollectResult:
        return collector.collect(
            self.config_dir,
            list(opts.get(CONF_GIT_AREAS) or []),
            esphome_path=opts.get(CONF_GIT_ESPHOME_PATH) or "",
            z2m_path=opts.get(CONF_GIT_Z2M_PATH) or "",
            extra_paths=list(opts.get(CONF_GIT_EXTRA_PATHS) or []),
            generated=generated,
        )

    async def _async_generated_files(self) -> list[collector.SourceFile]:
        """Inventory (and add-on options with Supervisor)."""
        out: list[collector.SourceFile] = []
        areas = self.options.get(CONF_GIT_AREAS) or []
        if AREA_INVENTORY in areas:
            out.append(
                collector.SourceFile(
                    repo_path=collector.PREFIX[AREA_INVENTORY] + "inventory.json",
                    area=AREA_INVENTORY,
                    data=await self._async_inventory(),
                )
            )
        if AREA_ADDONS in areas and "hassio" in self.hass.config.components:
            out.extend(await self._async_addon_files())
        if self.decoy is not None and self.options.get(CONF_CANARY_GIT) and (text := self.decoy()):
            # Plain on purpose: whoever obtains the repository finds working looking
            # credentials, and their first use raises an alarm.
            out.append(
                collector.SourceFile(
                    repo_path=collector.PREFIX[AREA_CONFIG] + ".env",
                    area=AREA_CONFIG,
                    data=text.encode(),
                    plain=True,
                )
            )
        return out

    async def _async_inventory(self) -> bytes:
        custom = await async_get_custom_components(self.hass)
        resources: list[dict[str, str]] = []
        try:
            from homeassistant.components.lovelace.const import LOVELACE_DATA  # noqa: PLC0415

            if (data := self.hass.data.get(LOVELACE_DATA)) is not None:
                if not getattr(data.resources, "loaded", True):
                    await data.resources.async_load()
                    data.resources.loaded = True
                resources = sorted(
                    (
                        {"url": str(r.get("url")), "type": str(r.get("type", r.get("res_type", "")))}
                        for r in data.resources.async_items()
                    ),
                    key=lambda r: r["url"],
                )
        except Exception:  # noqa: BLE001
            resources = []
        inventory = {
            "home_assistant": HA_VERSION,
            "custom_integrations": [
                {
                    "domain": domain,
                    "name": integ.name,
                    "version": str(integ.version) if integ.version else None,
                    "documentation": integ.documentation,
                    "issue_tracker": integ.issue_tracker,
                }
                for domain, integ in sorted(custom.items())
            ],
            "integrations": sorted({e.domain for e in self.hass.config_entries.async_entries()}),
            "dashboard_resources": resources,
        }
        return json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n"

    async def _async_addon_files(self) -> list[collector.SourceFile]:
        out: list[collector.SourceFile] = []
        try:
            from homeassistant.components.hassio import get_addons_info  # noqa: PLC0415

            infos = get_addons_info(self.hass) or {}
        except Exception:  # noqa: BLE001
            return out
        for slug, info in sorted(infos.items()):
            if not info or "options" not in info:
                continue
            data = {
                "slug": slug,
                "name": info.get("name"),
                "version": info.get("version"),
                "options": info.get("options"),
            }
            out.append(
                collector.SourceFile(
                    repo_path=f"{collector.PREFIX[AREA_ADDONS]}{slug}.json",
                    area=AREA_ADDONS,
                    data=json.dumps(data, indent=2, sort_keys=True).encode() + b"\n",
                    encrypt=True,
                )
            )
        return out

    def _cipher(self, opts: dict[str, Any], salt: str | None = None) -> FileCipher | None:
        passphrase = opts.get(CONF_GIT_PASSPHRASE) or ""
        salt = salt or opts.get(CONF_GIT_SALT) or ""
        if not passphrase or not salt:
            return None
        cached = self._cipher_cache
        key = hashlib.sha256(f"{passphrase}\x00{salt}".encode()).hexdigest()
        if cached and cached[0] == key and cached[1] == salt:
            return cached[2]
        cipher = FileCipher.from_passphrase(passphrase, salt)
        self._cipher_cache = (key, salt, cipher)
        return cipher

    def _context(self, opts: dict[str, Any]) -> RemoteContext:
        expected = opts.get(CONF_GIT_HOST_KEY) or self.state.host_key or ""

        def on_new(line: str, fp: str) -> None:
            self._new_host_key = (line, fp)

        return build_context(opts, host_key=expected, on_new=on_new)

    async def _async_users(self, user_ids: set[str]) -> list[str]:
        names = []
        for user_id in sorted(user_ids):
            user = await self.hass.auth.async_get_user(user_id)
            if user is not None and not user.system_generated:
                names.append(user.name or user_id[:8])
        return sorted(set(names))

    async def _async_privacy_ok(self, opts: dict[str, Any]) -> bool:
        spec = parse_remote(opts[CONF_GIT_URL])
        now = time.monotonic()
        if self.state.privacy is None or self._privacy_checked is None or now - self._privacy_checked > PRIVACY_RECHECK:
            self.state.privacy = await async_check_privacy(self.hass, spec)
            self._privacy_checked = now
        if self.state.privacy == "public":
            return False
        if self.state.privacy == "unknown" and not opts.get(CONF_GIT_ALLOW_UNVERIFIED_PRIVATE):
            return False
        return True

    # --------------------------------------------------------------- commit
    async def async_commit(self, trigger: str = "manual", message: str | None = None) -> dict[str, Any]:
        """Snapshot, commit and push."""
        if not self.enabled:
            raise HomeAssistantError("Git sync is not configured")
        async with self._lock:
            return await self._async_commit_locked(trigger, message)

    async def _async_commit_locked(self, trigger: str, message: str | None) -> dict[str, Any]:
        opts = self.options
        if self.state.host_key_mismatch:
            raise HomeAssistantError(f"SSH host key mismatch: {self.state.host_key_mismatch}")
        branch = safe_branch(opts.get(CONF_GIT_BRANCH) or "main")
        push_allowed = await self._async_privacy_ok(opts)
        generated = await self._async_generated_files()
        users = await self._async_users(self._users_since_commit)
        external = sorted(self._external_files)
        language = self.hass.config.language
        self._last_push_try = time.monotonic()
        try:
            result = await self.hass.async_add_executor_job(
                self._sync_commit, opts, branch, generated, trigger, message, users, external, push_allowed, language
            )
        except HostKeyMismatch as err:
            self.state.host_key_mismatch = err.detail or str(err)
            await self._async_save_state()
            await self.notifier.async_send("Bastion", str(err), key="git_host_key", rate_limit=3600)
            raise HomeAssistantError(str(err)) from err
        finally:
            if self._new_host_key is not None:
                self.state.host_key, self.state.host_key_fp = self._new_host_key
                self._new_host_key = None
        if result.get("committed"):
            self._users_since_commit.clear()
            self._external_files.clear()
            self.state.last_commit = result["sha"]
            self.state.last_commit_time = dt_util.utcnow().isoformat()
            self.state.last_commit_summary = result["summary"]
        self.state.skipped_secrets = result.get("skipped_secrets") or None
        if result.get("push_error"):
            self.state.pending_push = True
            self.state.last_push_ok = False
            self.state.last_error = result["push_error"]
            self.state.last_error_reason = result.get("push_reason")
        elif result.get("pushed"):
            self.state.pending_push = False
            self.state.last_push_ok = True
            self.state.last_push_time = dt_util.utcnow().isoformat()
            self.state.last_error = None
            self.state.last_error_reason = None
        elif not push_allowed:
            self.state.pending_push = True
        await self._async_save_state()
        return result

    def _sync_commit(
        self,
        opts: dict[str, Any],
        branch: str,
        generated: list[collector.SourceFile],
        trigger: str,
        message: str | None,
        users: list[str],
        external: list[str],
        push_allowed: bool,
        language: str,
    ) -> dict[str, Any]:
        repo = gitrepo.open_repo(self.repo_path)
        try:
            ctx = self._context(opts)
            fetch_error: RemoteError | None = None
            try:
                gitrepo.fetch(ctx, repo, branch)
            except HostKeyMismatch:
                raise
            except RemoteError as err:
                fetch_error = err
            base = gitrepo.choose_base(repo, branch)
            if trigger == "initial" and gitrepo.remote_head(repo, branch) is not None:
                # Existing history (e.g. a fresh instance that is about to be
                # restored): do not put an empty configuration on top of it.
                return {"committed": False, "pushed": False, "skipped": "remote_not_empty"}
            collected = self._collect(opts, generated)
            cipher = self._cipher(opts)
            meta = {
                "instance": self.hass.config.location_name,
                "home_assistant": HA_VERSION,
                "areas": sorted(opts.get(CONF_GIT_AREAS) or []),
                "extra_paths": collected.extra_labels,
            }
            snap = gitrepo.build_snapshot(
                repo,
                base,
                collected.files,
                cipher,
                salt=opts.get(CONF_GIT_SALT) or "",
                meta=meta,
                readme=README[lang(language)].encode(),
            )
            out: dict[str, Any] = {
                "committed": False,
                "pushed": False,
                "skipped_secrets": snap.skipped_secrets,
                "auto_encrypted": snap.auto_encrypted,
                "added": snap.added,
                "modified": snap.modified,
                "deleted": snap.deleted,
            }
            if snap.changed or base is None:
                text = self._commit_message(snap, trigger, message, users, external, language)
                author = f"{opts.get(CONF_GIT_AUTHOR_NAME) or 'Bastion'} <{opts.get(CONF_GIT_AUTHOR_EMAIL) or 'bastion@homeassistant.local'}>"
                sha = gitrepo.create_commit(repo, branch, snap.tree_id, base, author=author, message=text)
                out.update(committed=True, sha=sha.decode(), summary=text.splitlines()[0])
            head = gitrepo.local_head(repo, branch)
            if head is not None and head != gitrepo.remote_head(repo, branch):
                if not push_allowed:
                    out.update(push_error="repository not verified as private", push_reason="privacy")
                elif fetch_error is not None:
                    out.update(push_error=str(fetch_error), push_reason=fetch_error.reason)
                else:
                    try:
                        gitrepo.push(ctx, repo, branch, head)
                        out["pushed"] = True
                    except HostKeyMismatch:
                        raise
                    except RemoteError as err:
                        out.update(push_error=str(err), push_reason=err.reason)
            elif head is not None:
                out["pushed"] = True
            gitrepo.gc_local(repo)
            return out
        finally:
            repo.close()

    def _commit_message(
        self,
        snap: gitrepo.SnapshotResult,
        trigger: str,
        message: str | None,
        users: list[str],
        external: list[str],
        language: str,
    ) -> str:
        counts = misc("commit_counts", language, m=len(snap.modified), a=len(snap.added), d=len(snap.deleted))
        title = (
            message.strip().splitlines()[0][:120]
            if message and message.strip()
            else misc("commit_title", language, counts=counts)
        )
        lines = [title, ""]
        lines.append(f"{misc('commit_trigger', language)}: {misc('commit_' + trigger, language)}")
        if users:
            lines.append(f"{misc('commit_users', language)}: {', '.join(users)}")
        if external:
            lines.append(f"{misc('commit_external', language)}: {', '.join(external[:20])}")
        if snap.auto_encrypted:
            lines.append(f"{misc('commit_encrypted', language)}: {', '.join(snap.auto_encrypted[:20])}")
        if snap.skipped_secrets:
            lines.append(f"{misc('commit_skipped', language)}: {', '.join(snap.skipped_secrets[:20])}")
        lines.append("")
        for prefix, items in (("M", snap.modified), ("A", snap.added), ("D", snap.deleted)):
            lines.extend(f"{prefix} {p}" for p in items[:200])
        return "\n".join(lines).rstrip() + "\n"

    # ------------------------------------------------------- read operations
    async def async_history(self, limit: int = 100, refresh: bool = True) -> dict[str, Any]:
        """Commit history of the branch."""
        if not self.enabled:
            return {"enabled": False, "commits": []}
        opts = self.options
        branch = safe_branch(opts.get(CONF_GIT_BRANCH) or "main")
        async with self._lock:
            return await self.hass.async_add_executor_job(self._sync_history, opts, branch, limit, refresh)

    def _sync_history(self, opts: dict[str, Any], branch: str, limit: int, refresh: bool) -> dict[str, Any]:
        repo = gitrepo.open_repo(self.repo_path)
        try:
            error = None
            if refresh:
                try:
                    gitrepo.fetch(self._context(opts), repo, branch)
                except RemoteError as err:
                    error = str(err)
            head = gitrepo.choose_base(repo, branch)
            remote = gitrepo.remote_head(repo, branch)
            commits = gitrepo.history(repo, head, limit)
            for item in commits:
                item["pushed"] = remote is not None and gitrepo.is_ancestor(repo, item["sha"].encode(), remote)
            return {"enabled": True, "branch": branch, "commits": commits, "error": error}
        finally:
            repo.close()

    async def async_commit_files(self, sha: str) -> list[dict[str, Any]]:
        """Files of a commit compared with the current configuration."""
        opts = self.options
        generated = await self._async_generated_files()
        async with self._lock:
            return await self.hass.async_add_executor_job(self._sync_compare, opts, sha, generated, None)

    async def async_file_diff(self, sha: str, path: str) -> dict[str, Any]:
        """Unified diff of one file between commit and current state."""
        opts = self.options
        generated = await self._async_generated_files()
        async with self._lock:
            result = await self.hass.async_add_executor_job(self._sync_compare, opts, sha, generated, path)
        return result[0] if result else {"path": path, "status": "missing"}

    def _current_files(
        self, opts: dict[str, Any], generated: list[collector.SourceFile]
    ) -> dict[str, collector.SourceFile]:
        return {src.repo_path: src for src in self._collect(opts, generated).files}

    def _sync_compare(
        self,
        opts: dict[str, Any],
        sha: str,
        generated: list[collector.SourceFile],
        only_path: str | None,
    ) -> list[dict[str, Any]]:
        repo = gitrepo.open_repo(self.repo_path)
        try:
            commit_sha = sha.encode()
            if commit_sha not in repo.object_store:
                raise HomeAssistantError("Unknown commit")
            files = gitrepo.tree_files(repo, gitrepo.commit_tree_id(repo, commit_sha))
            manifest = gitrepo.read_manifest(repo, files)
            cipher = self._cipher(opts, manifest.get("salt")) if manifest.get("salt") else None
            macs = manifest.get("encrypted", {})
            current = self._current_files(opts, generated)
            out: list[dict[str, Any]] = []
            seen: set[str] = set()
            for path, (_mode, blob_sha) in sorted(files.items()):
                if not path.startswith(collector.MANAGED_PREFIXES) or path == collector.MANIFEST_PATH:
                    continue
                original = path.removesuffix(collector.ENC_SUFFIX)
                if only_path is not None and original != only_path:
                    continue
                seen.add(original)
                encrypted = path.endswith(collector.ENC_SUFFIX)
                src = current.get(original)
                item: dict[str, Any] = {
                    "path": original,
                    "area": collector.area_of(original),
                    "encrypted": encrypted,
                }
                if src is None:
                    item["status"] = "deleted_locally"
                else:
                    try:
                        data = src.read()
                    except OSError:
                        data = None
                    if encrypted:
                        if cipher is None or data is None:
                            item["status"] = "unknown"
                        else:
                            item["status"] = "same" if cipher.mac(original, data) == macs.get(path) else "changed"
                    else:
                        old = gitrepo.read_blob(repo, blob_sha)
                        item["status"] = "same" if old == data else "changed"
                        if only_path is not None and item["status"] == "changed":
                            item["diff"] = gitrepo.unified_diff(data, old, original)
                out.append(item)
            if only_path is None:
                for path in sorted(current):
                    if path not in seen:
                        out.append(
                            {"path": path, "area": collector.area_of(path), "encrypted": False, "status": "new_locally"}
                        )
            return out
        finally:
            repo.close()

    # ---------------------------------------------------------------- restore
    async def async_restore(
        self,
        sha: str,
        *,
        areas: list[str] | None = None,
        paths: list[str] | None = None,
        restart: bool = False,
    ) -> dict[str, Any]:
        """Restore files of a commit."""
        if not self.enabled:
            raise HomeAssistantError("Git sync is not configured")
        from homeassistant.helpers.check_config import async_check_ha_config_file  # noqa: PLC0415

        async with self._lock:
            try:
                await self._async_commit_locked("pre_restore", None)
            except HomeAssistantError:
                raise
            except Exception:  # noqa: BLE001 - the restore must still be possible offline
                _LOGGER.exception("Safety commit before restore failed")
            opts = self.options
            summary = await self.hass.async_add_executor_job(self._sync_restore, opts, sha, areas, paths)
        if summary["config_written"]:
            result = await async_check_ha_config_file(self.hass)
            if result.errors:
                await self.hass.async_add_executor_job(self._sync_rollback, summary)
                errors = "; ".join(str(e.message) for e in result.errors)[:500]
                raise HomeAssistantError(f"Restored configuration is invalid, rolled back: {errors}")
        summary["restart_required"] = bool(summary["staged"]) or summary["core_config_written"]
        if summary["staged"]:
            await self.notifier.async_send(
                "Bastion",
                misc("commit_pre_restore", self.hass.config.language) + f": {sha[:8]}",
                key="restore_pending",
                persistent=False,
            )
        if restart:
            await self.hass.services.async_call("homeassistant", "restart", blocking=False)
        elif summary["config_written"] and self.hass.services.has_service("homeassistant", "reload_all"):
            await self.hass.services.async_call("homeassistant", "reload_all", blocking=False)
        return {k: v for k, v in summary.items() if k not in ("backups", "created")}

    def _sync_restore(
        self,
        opts: dict[str, Any],
        sha: str,
        areas: list[str] | None,
        paths: list[str] | None,
    ) -> dict[str, Any]:
        repo = gitrepo.open_repo(self.repo_path)
        try:
            branch = safe_branch(opts.get(CONF_GIT_BRANCH) or "main")
            commit_sha = sha.encode()
            if commit_sha not in repo.object_store:
                try:
                    gitrepo.fetch(self._context(opts), repo, branch)
                except RemoteError as err:
                    raise HomeAssistantError(str(err)) from err
                if commit_sha not in repo.object_store:
                    raise HomeAssistantError("Unknown commit")
            files = gitrepo.tree_files(repo, gitrepo.commit_tree_id(repo, commit_sha))
            manifest = gitrepo.read_manifest(repo, files)
            salt = manifest.get("salt")
            cipher = self._cipher(opts, salt) if salt else None
            extra_map: dict[str, str] = dict(manifest.get("extra_paths") or {})
            current_extra = collector.CollectResult()
            collector.collect_extra(list(opts.get(CONF_GIT_EXTRA_PATHS) or []), current_extra)
            extra_map.update(current_extra.extra_labels)
            wanted_areas = set(areas or [])
            wanted_paths = set(paths or [])
            stamp = dt_util.utcnow().strftime("%Y%m%d-%H%M%S")
            backup_dir = os.path.join(self.work_dir, "restore-backup", stamp)
            staged_dir = os.path.join(self.work_dir, "staged")
            summary: dict[str, Any] = {
                "commit": sha,
                "written": [],
                "staged": [],
                "skipped": [],
                "backups": [],
                "created": [],
                "backup_dir": backup_dir,
                "config_written": False,
                "core_config_written": False,
            }
            pending: list[dict[str, str]] = []
            for path, (mode, blob_sha) in sorted(files.items()):
                if mode == gitrepo.SYMLINK_MODE or not path.startswith(collector.MANAGED_PREFIXES):
                    continue
                original = path.removesuffix(collector.ENC_SUFFIX)
                area = collector.area_of(original)
                if area is None or area == AREA_INVENTORY or original == collector.MANIFEST_PATH:
                    continue
                if wanted_paths and original not in wanted_paths:
                    continue
                if wanted_areas and area not in wanted_areas:
                    continue
                target = self._restore_target(original, area, opts, extra_map)
                if target is None:
                    summary["skipped"].append({"path": original, "reason": "not_allowed"})
                    continue
                try:
                    _, data = gitrepo.decode_entry(repo, path, blob_sha, cipher)
                except DecryptionError as err:
                    summary["skipped"].append({"path": original, "reason": f"decrypt: {err}"})
                    continue
                if area == AREA_STORAGE:
                    os.makedirs(staged_dir, exist_ok=True)
                    staged = os.path.join(staged_dir, os.path.basename(target))
                    _atomic_write(staged, data)
                    pending.append({"staged": staged, "target": target})
                    summary["staged"].append(original)
                    continue
                if os.path.exists(target):
                    with open(target, "rb") as fh:
                        if fh.read() == data:
                            continue
                    backup = os.path.join(backup_dir, area, os.path.relpath(target, "/"))
                    os.makedirs(os.path.dirname(backup), exist_ok=True)
                    shutil.copy2(target, backup)
                    summary["backups"].append((target, backup))
                else:
                    summary["created"].append(target)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                _atomic_write(target, data)
                summary["written"].append(original)
                if area == AREA_CONFIG:
                    summary["config_written"] = True
                    rel = original[len(collector.PREFIX[AREA_CONFIG]) :]
                    if rel == "configuration.yaml" or rel.startswith("packages/"):
                        summary["core_config_written"] = True
            if pending:
                with open(os.path.join(self.work_dir, PENDING_RESTORE), "w", encoding="utf-8") as fh:
                    json.dump({"commit": sha, "created": stamp, "files": pending}, fh, indent=2)
            self._prune_backups()
            return summary
        finally:
            repo.close()

    def _restore_target(self, original: str, area: str, opts: dict[str, Any], extra_map: dict[str, str]) -> str | None:
        rel = original[len(collector.PREFIX[area]) :]
        if area == AREA_STORAGE:
            name = rel
            if "/" in name or collector._match(name, collector.STORAGE_NEVER):  # noqa: SLF001
                return None
            if not collector._match(name, collector.STORAGE_PLAIN_PATTERNS + collector.STORAGE_ENCRYPTED_PATTERNS):  # noqa: SLF001
                return None
            return collector.resolve_target(os.path.join(self.config_dir, ".storage"), name)
        if area == AREA_CONFIG:
            top = rel.split("/", 1)[0]
            if top in collector.CONFIG_EXCLUDE_DIRS:
                return None
            ext = os.path.splitext(rel)[1].lower()
            if ext not in collector.CONFIG_EXTENSIONS and rel not in collector.CONFIG_EXTRA_FILES:
                return None
            return collector.resolve_target(self.config_dir, rel)
        if area == AREA_ESPHOME:
            base = opts.get(CONF_GIT_ESPHOME_PATH) or os.path.join(self.config_dir, "esphome")
            return collector.resolve_target(base, rel)
        if area == AREA_Z2M:
            base = opts.get(CONF_GIT_Z2M_PATH) or os.path.join(self.config_dir, "zigbee2mqtt")
            if "/" in rel:
                return None
            return collector.resolve_target(base, rel)
        if area == AREA_EXTRA:
            label, _, sub = rel.partition("/")
            base = extra_map.get(label)
            if not base or not sub:
                return None
            if os.path.isfile(base) or (not os.path.exists(base) and os.path.basename(base) == sub):
                return base if os.path.basename(base) == sub else None
            return collector.resolve_target(base, sub)
        return None

    def _sync_rollback(self, summary: dict[str, Any]) -> None:
        for target, backup in summary.get("backups", []):
            shutil.copy2(backup, target)
        for target in summary.get("created", []):
            try:
                os.remove(target)
            except OSError:
                pass
        pending = os.path.join(self.work_dir, PENDING_RESTORE)
        if os.path.exists(pending):
            os.remove(pending)

    def _prune_backups(self, keep: int = 5) -> None:
        root = os.path.join(self.work_dir, "restore-backup")
        if not os.path.isdir(root):
            return
        for name in sorted(os.listdir(root))[:-keep]:
            shutil.rmtree(os.path.join(root, name), ignore_errors=True)

    def pending_restore(self) -> dict[str, Any] | None:
        """Pending restore manifest, if any (sync, small file)."""
        path = os.path.join(self.work_dir, PENDING_RESTORE)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    # ---------------------------------------------------------------- status
    def findings(self, pending: dict[str, Any] | None = None) -> list[Finding]:
        """Findings that originate from the git sync."""
        out: list[Finding] = []
        if not self.enabled:
            return out
        repo_name = self.options.get(CONF_GIT_URL, "")
        try:
            repo_name = parse_remote(repo_name).display
        except RemoteError:
            pass
        if self.state.privacy == "public":
            out.append(make_finding("git_repo_public", Severity.CRITICAL, Category.GIT, repo_name, repo=repo_name))
        elif self.state.privacy == "unknown" and not self.options.get(CONF_GIT_ALLOW_UNVERIFIED_PRIVATE):
            out.append(make_finding("git_repo_unverified", Severity.MEDIUM, Category.GIT, repo_name, repo=repo_name))
        if self.state.host_key_mismatch:
            out.append(
                make_finding(
                    "git_host_key_changed",
                    Severity.CRITICAL,
                    Category.GIT,
                    repo_name,
                    host=self.state.host_key_mismatch,
                )
            )
        if self.state.last_push_ok is False and self.state.last_error_reason not in (None, "privacy"):
            out.append(
                make_finding("git_push_failed", Severity.MEDIUM, Category.GIT, repo_name, error=self.state.last_error)
            )
        if self.state.skipped_secrets:
            out.append(
                make_finding(
                    "git_secrets_skipped",
                    Severity.MEDIUM,
                    Category.GIT,
                    "skipped",
                    files=", ".join(self.state.skipped_secrets[:15]),
                )
            )
        if pending:
            out.append(
                make_finding(
                    "restore_pending",
                    Severity.LOW,
                    Category.GIT,
                    pending.get("commit"),
                    commit=str(pending.get("commit"))[:8],
                )
            )
        return out

    def status(self) -> dict[str, Any]:
        """Status for sensors and the panel."""
        state = self.state
        if not self.enabled:
            value = "disabled"
        elif state.host_key_mismatch or state.privacy == "public":
            value = "blocked"
        elif state.last_push_ok is False:
            value = "error"
        elif state.pending_push:
            value = "pending"
        else:
            value = "ok"
        url = self.options.get(CONF_GIT_URL, "")
        try:
            url = parse_remote(url).display if url else ""
        except RemoteError:
            pass
        return {
            "status": value,
            "url": url,
            "branch": self.options.get(CONF_GIT_BRANCH),
            "last_commit": state.last_commit,
            "last_commit_time": state.last_commit_time,
            "last_commit_summary": state.last_commit_summary,
            "last_push_time": state.last_push_time,
            "last_error": state.last_error,
            "privacy": state.privacy,
            "host_key_fp": state.host_key_fp,
            "encryption": bool(self.options.get(CONF_GIT_PASSPHRASE)),
            "public_key": self.options.get(CONF_GIT_PUBLIC_KEY) if self.options.get(CONF_GIT_AUTH) == "ssh" else None,
            "areas": self.options.get(CONF_GIT_AREAS),
        }

    async def async_reset_host_key(self) -> None:
        """Forget the stored host key (after the user verified a change)."""
        self.state.host_key = None
        self.state.host_key_fp = None
        self.state.host_key_mismatch = None
        await self._async_save_state()


def _atomic_write(path: str, data: bytes) -> None:
    tmp = f"{path}.bastion-tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _state_dict(state: GitState) -> dict[str, Any]:
    return {k: getattr(state, k) for k in GitState.__slots__}  # type: ignore[attr-defined]


async def async_test_connection(hass: HomeAssistant, options: dict[str, Any]) -> dict[str, Any]:
    """Used by the options flow: connect, list refs, check privacy."""
    spec = parse_remote(options[CONF_GIT_URL])
    safe_branch(options.get(CONF_GIT_BRANCH) or "main")
    seen: dict[str, str] = {}

    def on_new(line: str, fp: str) -> None:
        seen["line"] = line
        seen["fp"] = fp

    ctx = build_context(options, host_key=options.get(CONF_GIT_HOST_KEY) or "", on_new=on_new)
    refs = await hass.async_add_executor_job(gitrepo.list_remote_refs, ctx)
    privacy = await async_check_privacy(hass, spec)
    return {
        "refs": len(refs),
        "privacy": privacy,
        "host_key": seen.get("line") or options.get(CONF_GIT_HOST_KEY) or "",
        "host_key_fp": seen.get("fp", ""),
    }
