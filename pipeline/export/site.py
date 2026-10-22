"""Site JSON export: the route with human-readable names added next to the ids."""
import copy
import math

# How many item sources (dropping units/objects) a collect objective names: the nearest ones on the step map.
MAX_SOURCES = 3
# The objective area drawn on the site map: at most this many spawn points, the ones nearest the step.
MAX_AREA_POINTS = 200
_KINDS = (("units", "kill"), ("items", "collect"), ("objects", "use"))


def _on_map(entity: dict, step: dict) -> list[tuple[float, float]]:
    return [(x, y) for m, x, y in entity.get("points", []) if m == step["mapId"]]


def _nearest_droppers(item: dict, spawns: dict, step: dict) -> list[dict]:
    """The item's dropping units/objects on the step's map, nearest to the step first (ties by name), at most
    MAX_SOURCES distinct names."""
    best: dict[str, tuple[float, list[dict]]] = {}
    for table, ids in (("units", item.get("units", [])), ("objects", item.get("objects", []))):
        for eid in ids:
            entity = spawns.get(table, {}).get(str(eid)) or {}
            points, name = _on_map(entity, step), entity.get("name")
            if not points or not name:
                continue
            dist = min(math.dist(p, (step["x"], step["y"])) for p in points)
            prev = best.get(name)
            best[name] = (min(dist, prev[0]), prev[1] + [entity]) if prev else (dist, [entity])
    ranked = sorted(best.items(), key=lambda kv: (kv[1][0], kv[0]))[:MAX_SOURCES]
    return [{"name": name, "entities": entities} for name, (_, entities) in ranked]


def _area(quest: dict, spawns: dict, step: dict) -> list[list[float]]:
    """Spawn points on the step's map where the objectives are done: the units to kill, the nearest droppers of
    items to collect and the objects to use; rounded to 0.1, deduplicated, nearest MAX_AREA_POINTS, sorted."""
    objectives = quest.get("objectives") or {}
    entities = [spawns.get("units", {}).get(str(u)) or {} for u in objectives.get("units", [])]
    entities += [spawns.get("objects", {}).get(str(o)) or {} for o in objectives.get("objects", [])]
    for i in objectives.get("items", []):
        item = spawns.get("items", {}).get(str(i)) or {}
        entities += [e for d in _nearest_droppers(item, spawns, step) for e in d["entities"]]
    points = {(round(x, 1), round(y, 1)) for e in entities for x, y in _on_map(e, step)}
    nearest = sorted(points, key=lambda p: (math.dist(p, (step["x"], step["y"])), p))[:MAX_AREA_POINTS]
    return [list(p) for p in sorted(nearest)]


def _objectives(quest: dict, spawns: dict, step: dict, item_icons: dict[str, int | None] | None) -> list[dict]:
    """What a complete step asks for: units to kill, items to collect (with nearby sources), objects to use."""
    out: list[dict] = []
    objectives = quest.get("objectives") or {}
    for key, kind in _KINDS:
        table = spawns.get(key, {})
        for eid in objectives.get(key, []):
            entry = table.get(str(eid)) or {}
            obj = {"kind": kind, "id": eid, "name": entry.get("name")}
            if kind == "collect":
                obj["sources"] = [d["name"] for d in _nearest_droppers(entry, spawns, step)]
                if item_icons is not None:
                    obj["icon"] = item_icons.get(str(eid))
            out.append(obj)
    return out


def optional_quests(route: dict, quests: dict[int, dict]) -> list[dict]:
    """Quests the route does not take that its race and faction can do, starting at a known point on a map the
    route visits (the site's exploration mode shows them): by map, then level."""
    from pipeline.generate.config import LEVEL_CAP
    from pipeline.generate.graph import class_only

    maps = {s["mapId"] for s in route.get("steps", [])}
    taken = {s["questId"] for s in route.get("steps", []) if s.get("questId") is not None}
    race, faction = route.get("race"), route.get("faction")
    out = []
    for qid, q in quests.items():
        start = q.get("start") or {}
        level = q.get("level") if q.get("level") is not None else q.get("minLevel")
        if (qid in taken or not q.get("inForever") or level is None or level > LEVEL_CAP
                or (q.get("minLevel") or 0) > LEVEL_CAP or start.get("uiMapId") not in maps
                or start.get("x") is None or start.get("y") is None
                or (q.get("races") is not None and race not in q["races"])
                or (q.get("factions") is not None and faction not in q["factions"])):
            continue
        entry = {"questId": qid, "name": q.get("name"), "mapId": start["uiMapId"], "x": start["x"], "y": start["y"],
                 "level": level, "minLevel": q.get("minLevel"), "npcName": start.get("name")}
        if q.get("classes"):
            playable = class_only(q, race)
            if not playable:
                continue
            entry["classOnly"] = playable
        out.append(entry)
    return sorted(out, key=lambda e: (e["mapId"], e["level"], e["questId"]))


def to_site_json(route: dict, quests: dict[int, dict], spawns: dict, uimaps: dict[int, str],
                 levels: dict[str, int] | None = None, item_icons: dict[str, int | None] | None = None,
                 seconds: dict[str, int] | None = None) -> dict:
    """Return a copy of route whose steps also carry questName, npcName and zoneName (None when unknown);
    complete steps also carry their objectives, and with `levels` (xpsim.estimate_levels) every step
    carries its estimated player level; with `item_icons` (site/src/data/item-icons.json) collect objectives
    carry their item's icon FileDataID; with `seconds` (export.timing.step_seconds) every step carries its
    estimated time. `optional` lists the quests off the route (optional_quests)."""
    out = copy.deepcopy(route)
    units = spawns.get("units", {})
    for step in out.get("steps", []):
        quest_id, npc_id, map_id = step.get("questId"), step.get("npcId"), step.get("mapId")
        step["questName"] = quests.get(quest_id, {}).get("name") if quest_id is not None else None
        step["npcName"] = units.get(str(npc_id), {}).get("name") if npc_id is not None else None
        step["zoneName"] = uimaps.get(map_id) if map_id is not None else None
        if levels is not None and step.get("id") in levels:
            step["level"] = levels[step["id"]]
        if seconds is not None and step.get("id") in seconds:
            step["seconds"] = seconds[step["id"]]
        if step.get("type") == "complete" and quest_id in quests:
            step["objectives"] = _objectives(quests[quest_id], spawns, step, item_icons)
            step["area"] = _area(quests[quest_id], spawns, step)
    out["optional"] = optional_quests(route, quests)
    return out
