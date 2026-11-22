"""Statistics for anomaly detection. Pure Python, no Home Assistant imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
from typing import Any

MIN_BUCKET_SAMPLES = 36
CONSECUTIVE = 3
MAX_WEIGHT = 2000
MIN_CONTINUOUS_SAMPLES = 288 * 7
MIN_RUNS = 5
MIN_CONTINUOUS_SECONDS = 3 * 3600
DRIFT_RATIO = 1.25
DRIFT_MIN_DAYS = 21


@dataclass(slots=True)
class Running:
    """Welford running mean / variance with a weight cap (slow adaptation)."""

    n: float = 0.0
    mean: float = 0.0
    m2: float = 0.0

    def add(self, x: float) -> None:
        if self.n >= MAX_WEIGHT:
            factor = (MAX_WEIGHT - 1) / self.n
            self.n *= factor
            self.m2 *= factor
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (x - self.mean)

    @property
    def std(self) -> float:
        return math.sqrt(self.m2 / (self.n - 1)) if self.n > 1 else 0.0

    def to_list(self) -> list[float]:
        return [round(self.n, 3), self.mean, self.m2]

    @classmethod
    def from_list(cls, data: list[float] | None) -> Running:
        if not data or len(data) != 3:
            return cls()
        return cls(float(data[0]), float(data[1]), float(data[2]))


def bucket_index(ts: datetime) -> int:
    """Weekday/weekend x hour of day."""
    return (24 if ts.weekday() >= 5 else 0) + ts.hour


def _neighbours(index: int) -> list[int]:
    """The hour before, the hour itself and the hour after (same weekday/weekend half)."""
    base, hour = (index // 24) * 24, index % 24
    return [base + (hour - 1) % 24, index, base + (hour + 1) % 24]


def _pool(parts: list[Running]) -> Running:
    """Mean and variance of several running statistics together."""
    n = sum(p.n for p in parts)
    if not n:
        return Running()
    mean = sum(p.n * p.mean for p in parts) / n
    m2 = sum(p.m2 + p.n * (p.mean - mean) ** 2 for p in parts)
    return Running(n, mean, m2)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(math.ceil(0.95 * len(ordered))) - 1)]


@dataclass(slots=True)
class SensorModel:
    """Learned behaviour of one numeric sensor."""

    buckets: list[Running] = field(default_factory=lambda: [Running() for _ in range(48)])
    overall: Running = field(default_factory=Running)
    samples: int = 0
    idle_samples: int = 0
    run_start: float | None = None
    runs: list[float] = field(default_factory=list)
    daily: dict[str, list[float]] = field(default_factory=dict)
    deviation_count: int = 0
    # Values the user marked as normal ("ist normal"), as small separate ranges: never reported again.
    # Separate ranges, so that accepting 28 °C and later 45 °C does not make everything in between normal.
    accepted: list[list[float]] | None = None
    # Set per sensor kind by the engine (not stored): smallest reported distance from the learned mean
    # (absolute, and relative to the mean) and how many 5-minute samples a value must stay outside.
    margin: float = 0.0
    margin_rel: float = 0.0
    need: int = CONSECUTIVE
    ordinary: tuple[float, float] | None = None

    # ------------------------------------------------------------ persistence
    def to_dict(self) -> dict[str, Any]:
        return {
            "b": [b.to_list() for b in self.buckets],
            "o": self.overall.to_list(),
            "s": self.samples,
            "i": self.idle_samples,
            "rs": self.run_start,
            "r": self.runs[-50:],
            "d": dict(sorted(self.daily.items())[-45:]),
            "a": self.accepted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SensorModel:
        model = cls()
        buckets = data.get("b") or []
        if len(buckets) == 48:
            model.buckets = [Running.from_list(b) for b in buckets]
        model.overall = Running.from_list(data.get("o"))
        model.samples = int(data.get("s", 0))
        model.idle_samples = int(data.get("i", 0))
        model.run_start = data.get("rs")
        model.runs = [float(x) for x in data.get("r", [])]
        model.daily = {k: [float(v[0]), float(v[1])] for k, v in (data.get("d") or {}).items()}
        accepted = data.get("a")
        if isinstance(accepted, list) and len(accepted) == 2 and all(isinstance(x, (int, float)) for x in accepted):
            accepted = [accepted]  # 0.7.1 stored one range
        if isinstance(accepted, list):
            model.accepted = [
                [float(r[0]), float(r[1])] for r in accepted if isinstance(r, list) and len(r) == 2
            ] or None
        return model

    def configure(
        self,
        margin: float = 0.0,
        margin_rel: float = 0.0,
        need: int = CONSECUTIVE,
        ordinary: tuple[float, float] | None = None,
    ) -> None:
        """Tolerance for the kind of sensor (temperature, humidity, …)."""
        self.margin, self.margin_rel, self.need, self.ordinary = margin, margin_rel, max(1, need), ordinary

    def band(self, ts: datetime, z: float) -> tuple[float, float, float] | None:
        """Usual range at this time: (low, mean, high), None while still learning.

        The neighbouring hours count too, so a shower at 7:40 instead of 7:10 is no surprise.
        """
        index = bucket_index(ts)
        if self.buckets[index].n < MIN_BUCKET_SAMPLES:
            return None
        pooled = _pool([self.buckets[i] for i in _neighbours(index)])
        spread = max(pooled.std, abs(pooled.mean) * 0.05, 1e-6)
        half = max(z * spread, self.margin, self.margin_rel * abs(pooled.mean))
        return pooled.mean - half, pooled.mean, pooled.mean + half

    def _tolerance(self, value: float) -> float:
        return max(self.margin * 0.2, abs(value) * 0.02, 1e-6)

    def accept(self, value: float) -> None:
        """The user says this value is normal (only it and values close to it)."""
        ranges = sorted([*(self.accepted or []), [value, value]])
        merged: list[list[float]] = []
        for lo, hi in ranges:
            if merged and lo - merged[-1][1] <= self._tolerance(lo):
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        self.accepted = merged[-20:]
        self.deviation_count = 0

    def _is_accepted(self, value: float) -> bool:
        if self.ordinary is not None and self.ordinary[0] <= value <= self.ordinary[1]:
            return True
        tol = self._tolerance(value)
        return any(lo - tol <= value <= hi + tol for lo, hi in self.accepted or [])

    def is_accepted(self, value: float) -> bool:
        """True if the user marked this value (or one close to it) as normal."""
        return self._is_accepted(value)

    # ---------------------------------------------------------------- learning
    def idle_level(self) -> float:
        return max(abs(self.overall.mean) * 0.01, 1e-9)

    def seed(self, ts: datetime, value: float) -> None:
        """Add a historic (hourly mean) value."""
        self.buckets[bucket_index(ts)].add(value)
        self.overall.add(value)
        self._add_daily(ts, value)

    def _add_daily(self, ts: datetime, value: float) -> None:
        key = ts.date().isoformat()
        day = self.daily.setdefault(key, [0.0, 0.0])
        day[0] += value
        day[1] += 1

    def observe(self, ts: datetime, value: float, z: float) -> list[dict[str, Any]]:
        """Evaluate a new sample, then learn from it. Returns active anomalies."""
        anomalies: list[dict[str, Any]] = []
        bucket = self.buckets[bucket_index(ts)]
        band = self.band(ts, z)
        learn = value
        if band is not None:
            low, mean, high = band
            if (value < low or value > high) and not self._is_accepted(value):
                self.deviation_count += 1
            else:
                self.deviation_count = 0
            if self.deviation_count >= self.need:
                anomalies.append(
                    {"type": "deviation", "value": round(value, 3), "low": round(low, 3), "high": round(high, 3)}
                )
            # Learn from unusual values too, but limited: recurring peaks (shower, cooking) widen the
            # range over time, a single extreme value (fire, burst pipe) barely moves it.
            reach = 1.5 * (high - mean)
            learn = min(max(value, mean - reach), mean + reach)

        now = ts.timestamp()
        idle = abs(value) <= self.idle_level()
        if idle:
            if self.run_start is not None:
                self.runs.append(now - self.run_start)
                self.runs = self.runs[-50:]
            self.run_start = None
        elif self.run_start is None:
            self.run_start = now
        idle_fraction = self.idle_samples / self.samples if self.samples else 0
        if (
            not idle
            and self.run_start is not None
            and self.samples >= MIN_CONTINUOUS_SAMPLES
            and idle_fraction >= 0.3
            and len(self.runs) >= MIN_RUNS
        ):
            usual = max(_p95(self.runs), 1800.0)
            running = now - self.run_start
            if running > max(MIN_CONTINUOUS_SECONDS, 1.5 * usual):
                anomalies.append(
                    {"type": "continuous", "hours": round(running / 3600, 1), "usual": round(usual / 3600, 1)}
                )

        days = sorted(self.daily)
        today = ts.date().isoformat()
        complete = [d for d in days if d != today]
        if len(complete) >= DRIFT_MIN_DAYS:
            means = [self.daily[d][0] / self.daily[d][1] for d in complete if self.daily[d][1]]
            recent = means[-7:]
            base = means[-37:-7]
            if recent and base:
                recent_mean = sum(recent) / len(recent)
                base_mean = sum(base) / len(base)
                if (
                    base_mean > 0
                    and recent_mean > base_mean * DRIFT_RATIO
                    and recent_mean - base_mean > 0.5 * max(self.overall.std, 1e-9)
                ):
                    anomalies.append(
                        {
                            "type": "drift",
                            "recent": round(recent_mean, 3),
                            "baseline": round(base_mean, 3),
                            "percent": round((recent_mean / base_mean - 1) * 100),
                        }
                    )

        bucket.add(learn)
        self.overall.add(learn)
        self.samples += 1
        if idle:
            self.idle_samples += 1
        self._add_daily(ts, value)
        if len(self.daily) > 45:
            for key in sorted(self.daily)[:-45]:
                del self.daily[key]
        return anomalies


@dataclass(slots=True)
class HourHistogram:
    """Counts per hour of day."""

    counts: list[int] = field(default_factory=lambda: [0] * 24)

    @property
    def total(self) -> int:
        return sum(self.counts)

    def unusual(self, hour: int, min_total: int) -> bool:
        if self.total < min_total:
            return False
        window = self.counts[(hour - 1) % 24] + self.counts[hour] + self.counts[(hour + 1) % 24]
        return window == 0

    def add(self, hour: int) -> None:
        self.counts[hour] += 1
