"""Central runtime object of Bastion."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE, EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_change, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .alarm.engine import AlarmEngine
from .alarm.relay import AlarmRelay
from .anomaly.engine import AnomalyEngine
from .audit import AuditContext, async_run_audit
from .audit.supply_chain import accept_integrity
from .canary import CanaryManager
from .const import (
    CONF_AUDIT_INTERVAL,
    CONF_DISABLED_CHECKS,
    CONF_NOTIFY_MIN_SEVERITY,
    CONF_PROBE_INTERVAL,
    CONF_PROBE_TOKEN,
    CONF_PROBE_URL,
    CONF_REPAIRS_MIN_SEVERITY,
    CONF_REPORT_ENABLED,
    CONF_REPORT_TIME,
    CONF_REPORT_WEEKDAY,
    DOMAIN,
    EVENT_FINDING,
    SEVERITY_ORDER,
    SEVERITY_WEIGHT,
    SIGNAL_UPDATE,
    STORAGE_KEY_DATA,
    STORAGE_VERSION,
    Severity,
)
from .gitsync.manager import GitSyncManager, apply_pending_restore
from .guard import TokenGuard
from .login_monitor import LoginMonitor
from .models import Finding
from .notifier import Notifier
from .probe import async_run_probe, probe_findings
from .report import build_report
from .responder import Responder
from .texts import alarm_text, event_text, finding_text

_LOGGER = logging.getLogger(__name__)

FIRST_AUDIT_DELAY = 120
_IR_SEVERITY = {
    Severity.CRITICAL: ir.IssueSeverity.CRITICAL,
    Severity.HIGH: ir.IssueSeverity.ERROR,
    Severity.MEDIUM: ir.IssueSeverity.WARNING,
    Severity.LOW: ir.IssueSeverity.WARNING,
    Severity.INFO: ir.IssueSeverity.WARNING,
}


class Bastion:
    """Owns all Bastion components of a config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Init."""
        self.hass = hass
        self.entry = entry
        self.notifier = Notifier(hass, self.options)
        self.anomaly = AnomalyEngine(hass, self.notifier, lambda: self.options)
        self.logins = LoginMonitor(hass, self.notifier, lambda: self.options, self.anomaly)
        self.git = GitSyncManager(hass, entry, self.notifier)
        self.responder = Responder(hass, self)
        self.canary = CanaryManager(hass, self)
        self.guard = TokenGuard(hass, self.logins.on_token_used, self.canary.on_token_used)
        self.logins.responder = self.responder
        self.logins.ignored_user_ids = lambda: {self.canary.user_id} if self.canary.user_id else set()
        self.git.decoy = self.canary.decoy_text
        self.alarm = AlarmEngine(hass, self)
        self.relay = AlarmRelay(hass, self.alarm)
        self.alarm.on_event = self._on_alarm_event
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY_DATA)
        self.data: dict[str, Any] = {}
        self.findings: list[Finding] = []
        self.audit_errors: list[str] = []
        self.audit_running = False
        self._cache: dict[str, Any] = {}
        self._unsubs: list[CALLBACK_TYPE] = []
        self._started_unsub: CALLBACK_TYPE | None = None
        self._stop_unsub: CALLBACK_TYPE | None = None
        self._stopped = False

    @property
    def options(self) -> dict[str, Any]:
        """Effective options."""
        from . import get_options  # noqa: PLC0415

        return get_options(self.entry)

    # ---------------------------------------------------------------- lifecycle
    async def async_setup(self) -> None:
        """Start everything."""
        self.data = await self._store.async_load() or {}
        self.data.setdefault("dismissed", {})
        self.data.setdefault("known", {})
        self.data.setdefault("baseline", {})
        self.data.setdefault("issues", [])
        self.findings = [_finding_from_dict(f) for f in self.data.get("findings", [])]
        self.guard.install()
        self.responder.setup()
        await self.anomaly.async_setup()
        await self.alarm.async_setup()
        self.relay.setup()
        await self.canary.async_setup()
        await self.logins.async_setup()
        await self.git.async_setup()

        opts = self.options
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_scheduled_audit, timedelta(hours=float(opts.get(CONF_AUDIT_INTERVAL) or 6))
            )
        )
        if opts.get(CONF_PROBE_URL):
            self._unsubs.append(
                async_track_time_interval(
                    self.hass, self._async_scheduled_probe, timedelta(hours=float(opts.get(CONF_PROBE_INTERVAL) or 24))
                )
            )
        if opts.get(CONF_REPORT_ENABLED):
            h, m, sec = (int(x) for x in str(opts.get(CONF_REPORT_TIME) or "08:13:00").split(":"))
            self._unsubs.append(
                async_track_time_change(self.hass, self._async_scheduled_report, hour=h, minute=m, second=sec)
            )

        @callback
        def _started(_event: Event | None = None) -> None:
            self._started_unsub = None
            self._unsubs.append(async_call_later(self.hass, FIRST_AUDIT_DELAY, self._async_scheduled_audit))
            if self.options.get(CONF_PROBE_URL) and not self.data.get("probe"):
                self._unsubs.append(async_call_later(self.hass, FIRST_AUDIT_DELAY + 60, self._async_scheduled_probe))

        if self.hass.state is CoreState.running:
            _started()
        else:
            self._started_unsub = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _started)

        async def _stop(_event: Event) -> None:
            self._stop_unsub = None
            await self._async_shutdown()

        self._stop_unsub = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop)

    async def _async_shutdown(self) -> None:
        """Cancel timers and listeners, save state. Idempotent."""
        if self._stopped:
            return
        self._stopped = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._started_unsub is not None:
            self._started_unsub()
            self._started_unsub = None
        self.guard.uninstall()
        self.responder.unload()
        self.canary.unload()
        self.relay.unload()
        await self.alarm.async_unload()
        await self.git.async_unload()
        await self.logins.async_unload()
        await self.anomaly.async_unload()
        await self._async_save()

    async def async_unload(self) -> None:
        """Stop everything (entry unload)."""
        if self._stop_unsub is not None:
            self._stop_unsub()
            self._stop_unsub = None
        await self._async_shutdown()

    async def _async_save(self) -> None:
        self.data["findings"] = [f.as_dict() for f in self.findings]
        await self._store.async_save(self.data)

    def schedule_save(self) -> None:
        """Delayed save (used by responder and decoys)."""

        def _data() -> dict[str, Any]:
            self.data["findings"] = [f.as_dict() for f in self.findings]
            return self.data

        self._store.async_delay_save(_data, 5)

    # -------------------------------------------------------------------- audit
    async def _async_scheduled_audit(self, _now: datetime | None = None) -> None:
        try:
            await self.async_run_audit()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Bastion audit failed")

    async def async_run_audit(self, notify: bool = True) -> list[Finding]:
        """Run the audit and update findings, repairs and notifications."""
        if self.audit_running:
            return self.findings
        self.audit_running = True
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)
        try:
            opts = self.options
            self._cache["token_usage"] = self.logins.token_usage
            self._cache["usage_since"] = self.logins.usage_since
            self._cache["canary_user"] = self.canary.user_id
            ctx = AuditContext(self.hass, opts, self._cache, self.data["baseline"])
            findings = await async_run_audit(ctx, list(opts.get(CONF_DISABLED_CHECKS) or []))
            findings.extend(self.git.findings(await self.hass.async_add_executor_job(self.git.pending_restore)))
            findings.extend(probe_findings(self.data.get("probe"), self.hass.config.language))
            self.audit_errors = ctx.errors
            await self._async_apply_findings(findings, notify)
            self.data["last_audit"] = dt_util.utcnow().isoformat()
            self._record_history()
            await self._async_save()
            return self.findings
        finally:
            self.audit_running = False
            async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    async def _async_apply_findings(self, findings: list[Finding], notify: bool) -> None:
        language = self.hass.config.language
        known: dict[str, str] = self.data["known"]
        dismissed: dict[str, Any] = self.data["dismissed"]
        now = dt_util.utcnow().isoformat()
        unique: dict[str, Finding] = {}
        for finding in findings:
            unique.setdefault(finding.id, finding)
        new: list[Finding] = []
        for finding in unique.values():
            finding.title, finding.description, finding.recommendation = finding_text(
                finding.text_key, language, finding.data
            )
            if finding.id not in known:
                known[finding.id] = now
                new.append(finding)
            finding.first_seen = known[finding.id]
            finding.dismissed = finding.id in dismissed
        # Forget findings that are resolved, so they notify again if they return.
        previous = {f.id: f for f in self.findings}
        resolved: list[dict[str, Any]] = self.data.setdefault("resolved", [])
        for fid in list(known):
            if fid not in unique:
                known.pop(fid)
                if (old := previous.get(fid)) is not None:
                    resolved.append({"time": now, "title": old.title, "severity": old.severity.value})
        del resolved[:-200]
        self.findings = sorted(unique.values(), key=lambda f: (-f.rank, f.title))

        notify_min = SEVERITY_ORDER[Severity(self.options.get(CONF_NOTIFY_MIN_SEVERITY) or "high")]
        to_notify = [f for f in new if not f.dismissed and f.rank >= notify_min]
        for finding in new:
            self.hass.bus.async_fire(
                EVENT_FINDING,
                {"id": finding.id, "check": finding.check, "severity": finding.severity.value, "title": finding.title},
            )
        if notify and to_notify:
            if len(to_notify) <= 3:
                for finding in to_notify:
                    title, message = event_text(
                        "new_finding",
                        language,
                        {
                            "title": finding.title,
                            "description": finding.description,
                            "recommendation": finding.recommendation,
                        },
                    )
                    await self.notifier.async_send(title, message, key=f"finding_{finding.id}")
            else:
                lines = "\n".join(f"• [{f.severity.value}] {f.title}" for f in to_notify[:20])
                await self.notifier.async_send("Bastion", lines, key="findings_summary")
        self._sync_repairs()

    def _sync_repairs(self) -> None:
        repairs_min = SEVERITY_ORDER[Severity(self.options.get(CONF_REPAIRS_MIN_SEVERITY) or "high")]
        wanted = {f.id: f for f in self.findings if not f.dismissed and f.rank >= repairs_min}
        for issue_id in set(self.data.get("issues", [])) - set(wanted):
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        for issue_id, finding in wanted.items():
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                is_persistent=False,
                severity=_IR_SEVERITY[finding.severity],
                translation_key="finding",
                translation_placeholders={
                    "title": finding.title,
                    "description": finding.description,
                    "recommendation": finding.recommendation,
                },
            )
        self.data["issues"] = sorted(wanted)

    async def async_dismiss(self, finding_id: str, dismissed: bool = True) -> None:
        """Hide or show a finding."""
        if dismissed:
            self.data["dismissed"][finding_id] = dt_util.utcnow().isoformat()
        else:
            self.data["dismissed"].pop(finding_id, None)
        for finding in self.findings:
            if finding.id == finding_id:
                finding.dismissed = dismissed
        self._sync_repairs()
        await self._async_save()
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    async def async_accept_integrity(self, domain: str | None = None) -> None:
        """Accept current custom_components / www state."""
        current = self._cache.get("integrity_current")
        if current is None:
            await self.async_run_audit(notify=False)
            current = self._cache.get("integrity_current")
        accept_integrity(self.data["baseline"], current, domain)
        await self.async_run_audit(notify=False)

    @callback
    def _on_alarm_event(self, kind: str, entry: dict[str, Any]) -> None:
        self.hass.async_create_task(self._async_alarm_event(kind, entry), eager_start=True)

    async def _async_alarm_event(self, kind: str, entry: dict[str, Any]) -> None:
        actions = self.alarm.config.get("actions") or {}
        notify_kind = "armed" if kind in ("arming", "rearmed") else kind
        if notify_kind in (actions.get("notify_events") or []):
            if (texts := alarm_text(kind, self.hass.config.language, entry)) is not None:
                data = None
                if kind == "triggered" and actions.get("critical_push", True):
                    data = {
                        "push": {"sound": {"name": "default", "critical": 1, "volume": 1.0}},
                        "ttl": 0,
                        "priority": "high",
                        "channel": "alarm_stream",
                    }
                await self.notifier.async_send(
                    texts[0],
                    texts[1],
                    key=f"alarm_{kind}",
                    data=data,
                    persistent=kind in ("triggered", "pending", "arm_failed"),
                )
        await self.relay.async_send_event(kind, entry)

    def _record_history(self) -> None:
        """One score entry per day (last audit of the day wins), 120 days."""
        summary = self.summary()
        today = dt_util.now().date().isoformat()
        history: list[dict[str, Any]] = self.data.setdefault("history", [])
        entry = {"date": today, "score": summary["score"], "counts": summary["counts"]}
        if history and history[-1].get("date") == today:
            history[-1] = entry
        else:
            history.append(entry)
        del history[:-120]

    # ------------------------------------------------------------------- report
    async def _async_scheduled_report(self, now: datetime) -> None:
        if str(dt_util.as_local(now).weekday()) != str(self.options.get(CONF_REPORT_WEEKDAY, "0")):
            return
        try:
            await self.async_send_report()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Bastion weekly report failed")

    async def async_build_report(self) -> tuple[str, str]:
        """Title and markdown of the weekly report."""
        commits = None
        if self.git.enabled:
            try:
                history = await self.git.async_history(limit=200, refresh=False)
                cutoff = dt_util.utcnow().timestamp() - 7 * 86400
                commits = sum(1 for c in history["commits"] if c["time"] >= cutoff)
            except Exception:  # noqa: BLE001
                commits = None
        return build_report(self, commits)

    async def async_send_report(self) -> dict[str, str]:
        """Build and send the weekly report."""
        title, message = await self.async_build_report()
        self.data["last_report"] = {"time": dt_util.utcnow().isoformat(), "title": title, "message": message}
        self.schedule_save()
        await self.notifier.async_send(title, message, key="weekly_report")
        return {"title": title, "message": message}

    # -------------------------------------------------------------------- probe
    async def _async_scheduled_probe(self, _now: datetime | None = None) -> None:
        try:
            await self.async_run_probe()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Bastion external probe failed")

    async def async_run_probe(self) -> dict[str, Any]:
        """Run the external port probe."""
        opts = self.options
        url = opts.get(CONF_PROBE_URL)
        if not url:
            return {}
        try:
            result = await async_run_probe(self.hass, url, opts.get(CONF_PROBE_TOKEN) or "")
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            result = {"error": str(err)[:200], "time": dt_util.utcnow().isoformat()}
        self.data["probe"] = result
        await self.async_run_audit()
        return result

    # ------------------------------------------------------------------ summary
    def summary(self) -> dict[str, Any]:
        """Aggregated state for sensors and the panel."""
        active = [f for f in self.findings if not f.dismissed]
        counts = {s.value: 0 for s in Severity}
        for finding in active:
            counts[finding.severity.value] += 1
        score = max(0, 100 - sum(SEVERITY_WEIGHT[f.severity] for f in active))
        return {
            "score": score,
            "counts": counts,
            "open": len([f for f in active if f.severity != Severity.INFO]),
            "last_audit": self.data.get("last_audit"),
            "running": self.audit_running,
            "errors": self.audit_errors,
        }


def _finding_from_dict(data: dict[str, Any]) -> Finding:
    from .const import Category  # noqa: PLC0415

    return Finding(
        id=data["id"],
        check=data["check"],
        text_key=data.get("text_key", data["check"]),
        severity=Severity(data["severity"]),
        category=Category(data["category"]),
        data=data.get("data", {}),
        title=data.get("title", ""),
        description=data.get("description", ""),
        recommendation=data.get("recommendation", ""),
        first_seen=data.get("first_seen"),
        dismissed=data.get("dismissed", False),
    )


def register_close_listener(hass: HomeAssistant) -> None:
    """Apply staged .storage restores after HA wrote its final state."""

    async def _on_close(_event: Event) -> None:
        try:
            applied = await hass.async_add_executor_job(apply_pending_restore, hass.config.path())
            if applied:
                _LOGGER.warning("Bastion restored %s .storage files from git", applied)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Bastion could not apply the staged restore")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _on_close)
