"""Spawn index: where the quest NPCs, objects and item sources are, for route generation."""
from pipeline.config import DATA_BUILD
from pipeline.ingest.pfquest import PfData


def _referenced(quests: list[dict]) -> tuple[set[int], set[int], set[int]]:
    units: set[int] = set()
    objects: set[int] = set()
    items: set[int] = set()
    by_type = {"npc": units, "object": objects, "item": items}
    for q in quests:
        for label in ("start", "end"):
            ref = q.get(label) or {}
            if ref.get("type") in by_type and ref.get("id") is not None:
                by_type[ref["type"]].add(ref["id"])
        obj = q.get("objectives") or {}
        units.update(obj.get("units", []))
        objects.update(obj.get("objects", []))
        items.update(obj.get("items", []))
    return units, objects, items


def build_spawns(pf: PfData, quests: list[dict], zone_to_uimap: dict[int, int]) -> dict:
    """Spawn index for the entities the canonical quests reference (plus item droppers).

    Contract: an entity that is absent from `units`/`objects` (listed in `missingUnits`/
    `missingObjects`/`missingItems`, no pfQuest record) or present with empty `points`
    (counted in `emptyPointUnits`/`emptyPointObjects`) means "location unknown".
    Consumers must turn that into a gap step, never an invented coordinate.
    """
    units, objects, items = _referenced(quests)
    item_sources = {i: pf.items[i] for i in sorted(items) if i in pf.items}
    for src in item_sources.values():  # a dropped item needs its droppers located too
        units.update(src["units"])
        objects.update(src["objects"])
    missing_items = sorted(i for i in items if i not in pf.items)
    dropped = 0

    def points(coords) -> list[list]:
        nonlocal dropped
        out: list[list] = []
        for x, y, zone in coords:
            ui = zone_to_uimap.get(zone)
            if ui is None:
                dropped += 1
                continue
            point = [ui, x, y]
            if point not in out:
                out.append(point)
        return out

    out_units = {
        str(i): {"name": pf.units[i].get("name"), "points": points(pf.units[i]["coords"])}
        for i in sorted(units) if i in pf.units
    }
    out_objects = {
        str(i): {"points": points(pf.objects[i]["coords"])} for i in sorted(objects) if i in pf.objects
    }
    return {
        "build": DATA_BUILD,
        "missingUnits": sorted(i for i in units if i not in pf.units),
        "missingObjects": sorted(i for i in objects if i not in pf.objects),
        "missingItems": missing_items,
        "emptyPointUnits": sum(1 for v in out_units.values() if not v["points"]),
        "emptyPointObjects": sum(1 for v in out_objects.values() if not v["points"]),
        "units": out_units,
        "objects": out_objects,
        "items": {
            str(i): {"units": sorted(set(s["units"])), "objects": sorted(set(s["objects"]))}
            for i, s in item_sources.items()
        },
        "droppedPoints": dropped,
    }
