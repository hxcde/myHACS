"""Data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
from typing import Any

from .const import SEVERITY_ORDER, Category, Severity


def finding_id(check: str, *parts: Any) -> str:
    """Stable id of a finding."""
    raw = "|".join([check, *(str(p) for p in parts)])
    return f"{check}_{hashlib.sha1(raw.encode()).hexdigest()[:10]}"


@dataclass(slots=True)
class Finding:
    """A single audit result."""

    id: str
    check: str
    text_key: str
    severity: Severity
    category: Category
    data: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    description: str = ""
    recommendation: str = ""
    first_seen: str | None = None
    dismissed: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serialize."""
        out = asdict(self)
        out["severity"] = self.severity.value
        out["category"] = self.category.value
        return out

    @property
    def rank(self) -> int:
        """Sort key."""
        return SEVERITY_ORDER[self.severity]


def make_finding(
    check: str,
    severity: Severity,
    category: Category,
    *id_parts: Any,
    text_key: str | None = None,
    **data: Any,
) -> Finding:
    """Helper used by the checks."""
    return Finding(
        id=finding_id(check, *id_parts),
        check=check,
        text_key=text_key or check,
        severity=severity,
        category=category,
        data=data,
    )
