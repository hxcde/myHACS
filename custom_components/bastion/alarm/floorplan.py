"""Floor plan of the home for the worker dashboard (3D model, wall tablet).

The plan is configuration of the user, imported as JSON in the panel; it never
ships with Bastion. Coordinates are plan units with the origin top left.

    {
      "size": [w, h],
      "areas":    [{"id", "label", "rect": [x, y, w, h], "outdoor", "room", "keywords", "label_at": [x, y]}],
      "walls":    [{"points": [[x, y], ...], "exterior"}],
      "glazing":  [{"id", "label", "from": [x, y], "to": [x, y], "panels", "door_panels", "transom", "area", "sensor"}],
      "dividers": [[[x, y], ...]],
      "entrance": {"from": [x, y], "to": [x, y], "area", "sensor"},
      "boxes":    [{"points": [[x, y], ...], "height", "bottom", "kind", "group"}]
    }

Walls are 50 units high. A box is a body over its footprint: `height` above
`bottom` (both in plan units); `kind` furniture, soft, screen or shade; boxes
with the same `group` are drawn together (bed with mattress and pillows).

`room` links an area to a Bastion room (by name), `sensor` links a door to a
sensor (by name); without them the dashboard matches by keywords.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

LIMIT = 10000
MAX_BYTES = 64 * 1024


class FloorPlanError(ValueError):
    """The floor plan is not valid."""


def _num(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not -LIMIT <= value <= LIMIT:
        raise FloorPlanError(f"{what}: Zahl erwartet")
    return round(float(value), 2)


def _point(value: Any, what: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise FloorPlanError(f"{what}: Punkt [x, y] erwartet")
    return [_num(value[0], what), _num(value[1], what)]


def _points(value: Any, what: str, minimum: int = 2, maximum: int = 64) -> list[list[float]]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise FloorPlanError(f"{what}: {minimum} bis {maximum} Punkte erwartet")
    return [_point(p, what) for p in value]


def _text(value: Any, what: str, maximum: int = 60, *, required: bool = False) -> str | None:
    if value in (None, ""):
        if required:
            raise FloorPlanError(f"{what} fehlt")
        return None
    if not isinstance(value, str):
        raise FloorPlanError(f"{what}: Text erwartet")
    return value.strip()[:maximum] or None


def _list(value: Any, what: str, maximum: int) -> list:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise FloorPlanError(f"{what}: Liste mit höchstens {maximum} Einträgen erwartet")
    return value


def clean_floorplan(data: Any) -> dict[str, Any]:
    """Validated copy of a floor plan, only known keys."""
    if not isinstance(data, dict):
        raise FloorPlanError("Grundriss: JSON-Objekt erwartet")
    size = _point(data.get("size"), "size")
    if size[0] <= 0 or size[1] <= 0:
        raise FloorPlanError("size: Breite und Höhe müssen positiv sein")
    areas = []
    ids = set()
    for i, a in enumerate(_list(data.get("areas"), "areas", 40)):
        if not isinstance(a, dict):
            raise FloorPlanError(f"areas[{i}]: Objekt erwartet")
        area_id = _text(a.get("id"), f"areas[{i}].id", 40, required=True)
        if area_id in ids:
            raise FloorPlanError(f"areas[{i}].id doppelt: {area_id}")
        ids.add(area_id)
        rect = a.get("rect")
        if not isinstance(rect, list) or len(rect) != 4:
            raise FloorPlanError(f"areas[{i}].rect: [x, y, Breite, Höhe] erwartet")
        area = {
            "id": area_id,
            "label": _text(a.get("label"), f"areas[{i}].label") or area_id,
            "rect": [_num(v, f"areas[{i}].rect") for v in rect],
            "outdoor": bool(a.get("outdoor")),
        }
        if room := _text(a.get("room"), f"areas[{i}].room"):
            area["room"] = room
        keywords = [_text(k, f"areas[{i}].keywords", 30) for k in _list(a.get("keywords"), "keywords", 10)]
        if keywords := [k.lower() for k in keywords if k]:
            area["keywords"] = keywords
        if a.get("label_at") is not None:
            area["label_at"] = _point(a.get("label_at"), f"areas[{i}].label_at")
        areas.append(area)
    if not areas:
        raise FloorPlanError("areas: mindestens eine Fläche")
    walls = []
    for i, w in enumerate(_list(data.get("walls"), "walls", 200)):
        if not isinstance(w, dict):
            raise FloorPlanError(f"walls[{i}]: Objekt erwartet")
        walls.append({"points": _points(w.get("points"), f"walls[{i}].points"), "exterior": bool(w.get("exterior"))})
    glazing = []
    for i, g in enumerate(_list(data.get("glazing"), "glazing", 40)):
        if not isinstance(g, dict):
            raise FloorPlanError(f"glazing[{i}]: Objekt erwartet")
        panels = g.get("panels", 1)
        if not isinstance(panels, int) or not 1 <= panels <= 12:
            raise FloorPlanError(f"glazing[{i}].panels: 1 bis 12")
        door_panels = [
            p for p in _list(g.get("door_panels"), "door_panels", 12) if isinstance(p, int) and 0 <= p < panels
        ]
        item = {
            "id": _text(g.get("id"), f"glazing[{i}].id", 40) or f"g{i}",
            "label": _text(g.get("label"), f"glazing[{i}].label", 80),
            "from": _point(g.get("from"), f"glazing[{i}].from"),
            "to": _point(g.get("to"), f"glazing[{i}].to"),
            "panels": panels,
            "door_panels": door_panels,
        }
        if g.get("transom") is not None:
            transom = _num(g.get("transom"), f"glazing[{i}].transom")
            if 0 < transom < 1:
                item["transom"] = transom
        for key in ("area", "sensor"):
            if value := _text(g.get(key), f"glazing[{i}].{key}"):
                item[key] = value
        glazing.append(item)
    dividers = [_points(d, f"dividers[{i}]") for i, d in enumerate(_list(data.get("dividers"), "dividers", 40))]
    entrance = None
    if isinstance(data.get("entrance"), dict):
        e = data["entrance"]
        entrance = {"from": _point(e.get("from"), "entrance.from"), "to": _point(e.get("to"), "entrance.to")}
        for key in ("area", "sensor"):
            if value := _text(e.get(key), f"entrance.{key}"):
                entrance[key] = value
    boxes = []
    for i, b in enumerate(_list(data.get("boxes"), "boxes", 80)):
        if not isinstance(b, dict):
            raise FloorPlanError(f"boxes[{i}]: Objekt erwartet")
        height = _num(b.get("height", 20), f"boxes[{i}].height")
        bottom = _num(b.get("bottom", 0), f"boxes[{i}].bottom")
        if not 0 < height <= 200 or not 0 <= bottom <= 200:
            raise FloorPlanError(f"boxes[{i}]: Höhe 0–200")
        box = {"points": _points(b.get("points"), f"boxes[{i}].points", 3, 24), "height": height, "bottom": bottom}
        if kind := _text(b.get("kind"), f"boxes[{i}].kind", 20):
            box["kind"] = kind
        if group := _text(b.get("group"), f"boxes[{i}].group", 30):
            box["group"] = group
        boxes.append(box)
    plan = {"size": size, "areas": areas, "walls": walls, "glazing": glazing, "dividers": dividers, "boxes": boxes}
    if entrance:
        plan["entrance"] = entrance
    if len(json.dumps(plan, separators=(",", ":"))) > MAX_BYTES:
        raise FloorPlanError("Grundriss zu groß (höchstens 64 KB)")
    return plan


def plan_hash(plan: dict[str, Any] | None) -> str | None:
    """Short fingerprint: the worker only gets the plan when it changed."""
    if not plan:
        return None
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
