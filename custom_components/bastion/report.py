"""Weekly security report."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import Severity
from .texts import lang, report_text


def _since(entries: list[dict[str, Any]], days: int = 7) -> list[dict[str, Any]]:
    cutoff = dt_util.utcnow() - timedelta(days=days)
    out = []
    for entry in entries:
        ts = dt_util.parse_datetime(str(entry.get("time", "")))
        if ts is not None and ts >= cutoff:
            out.append(entry)
    return out


def score_week_ago(history: list[dict[str, Any]]) -> int | None:
    """Score of the newest history entry that is at least 7 days old."""
    cutoff = (dt_util.now() - timedelta(days=7)).date().isoformat()
    older = [h for h in history if h.get("date", "") <= cutoff]
    return older[-1]["score"] if older else None


def build_report(bastion, commits: int | None) -> tuple[str, str]:
    """Return (title, markdown message)."""
    language = bastion.hass.config.language
    t = lambda key, **kw: report_text(key, language, **kw)  # noqa: E731
    summary = bastion.summary()
    now = dt_util.now()
    lines: list[str] = []

    previous = score_week_ago(bastion.data.get("history", []))
    if previous is None:
        lines.append(t("score", score=summary["score"]))
    else:
        diff = summary["score"] - previous
        lines.append(t("score_trend", score=summary["score"], previous=previous, diff=f"{diff:+d}"))
    counts = summary["counts"]
    lines.append(
        t(
            "open",
            critical=counts[Severity.CRITICAL.value],
            high=counts[Severity.HIGH.value],
            medium=counts[Severity.MEDIUM.value],
            low=counts[Severity.LOW.value],
        )
    )

    cutoff = dt_util.utcnow() - timedelta(days=7)
    new = [
        f
        for f in bastion.findings
        if not f.dismissed and f.first_seen and (dt_util.parse_datetime(f.first_seen) or cutoff) > cutoff
    ]
    if new:
        lines.append("")
        lines.append(t("new_findings", count=len(new)))
        lines.extend(f"- [{f.severity.value}] {f.title}" for f in new[:8])
    resolved = _since(bastion.data.get("resolved", []))
    if resolved:
        lines.append("")
        lines.append(t("resolved_findings", count=len(resolved)))
        lines.extend(f"- {r.get('title')}" for r in resolved[:8])

    log = _since(list(bastion.logins.log))
    by_type: dict[str, int] = {}
    for entry in log:
        by_type[entry["type"]] = by_type.get(entry["type"], 0) + 1
    lines.append("")
    lines.append(
        t(
            "logins",
            ok=by_type.get("login", 0),
            failed=by_type.get("failed_login", 0),
            new_ip=by_type.get("new_ip", 0) + by_type.get("token_new_ip", 0),
            banned=by_type.get("ip_banned", 0) + by_type.get("blocked", 0),
        )
    )
    canary = _since(bastion.canary.state.get("triggers", []))
    if bastion.canary.state.get("token") or canary:
        lines.append(t("canary_hit", count=len(canary)) if canary else t("canary_quiet"))

    anomalies = _since(list(bastion.anomaly.events))
    lines.append(t("anomalies", count=len(anomalies)))

    git = bastion.git.status()
    if git["status"] != "disabled":
        lines.append(
            t(
                "git",
                commits=commits if commits is not None else "?",
                status=git["status"],
                last=_fmt_time(git.get("last_push_time"), language),
            )
        )
    probe = bastion.data.get("probe") or {}
    open_ports = [str(r["port"]) for r in probe.get("results", []) if r.get("open")]
    if probe and not probe.get("error"):
        lines.append(t("ports", ports=", ".join(open_ports) if open_ports else "—"))

    week = now.isocalendar().week
    return t("title", week=week), "\n".join(lines)


def _fmt_time(value: str | None, language: str) -> str:
    ts = dt_util.parse_datetime(value or "")
    if ts is None:
        return "—"
    fmt = "%d.%m.%Y %H:%M" if lang(language) == "de" else "%Y-%m-%d %H:%M"
    return dt_util.as_local(ts).strftime(fmt)
