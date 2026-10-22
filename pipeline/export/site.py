"""Site JSON export: the route with human-readable names added next to the ids."""
import copy
import math

# How many item sources (dropping units/objects) a collect objective names: the nearest ones on the step map.
MAX_SOURCES = 3
_KINDS = (("units", "kill"), ("items", "collect"), ("objects", "use"))


def _nearest_sources(item: dict, spawns: dict, step: dict) -> list[str]:
    """Names of the item's droppers on the step's map, nearest to the step first (ties by name)."""
    ranked: dict[str, float] = {}
    for table, ids in (("units", item.get("units", [])), ("objects", item.get("objects", []))):
        for eid in ids:
            entity = spawns.get(table, {}).get(str(eid)) or {}
            dists = [math.dist((x, y), (step["x"], step["y"])) for m, x, y in entity.get("points", [])
                     if m == step["mapId"]]
            name = entity.get("name")
            if dists and name:
                ranked[name] = min(min(dists), ranked.get(name, math.inf))
    return [name for name, _ in sorted(ranked.items(), key=lambda kv: (kv[1], kv[0]))][:MAX_SOURCES]


def _objectives(quest: dict, spawns: dict, step: dict) -> list[dict]:
    """What a complete step asks for: units to kill, items to collect (with nearby sources), objects to use."""
    out: list[dict] = []
    objectives = quest.get("objectives") or {}
    for key, kind in _KINDS:
        table = spawns.get(key, {})
        for eid in objectives.get(key, []):
            entry = table.get(str(eid)) or {}
            obj = {"kind": kind, "id": eid, "name": entry.get("name")}
            if kind == "collect":
                obj["sources"] = _nearest_sources(entry, spawns, step)
            out.append(obj)
    return out


def to_site_json(route: dict, quests: dict[int, dict], spawns: dict, uimaps: dict[int, str],
                 levels: dict[str, int] | None = None) -> dict:
    """Return a copy of route whose steps also carry questName, npcName and zoneName (None when unknown);
    complete steps also carry their objectives, and with `levels` (xpsim.estimate_levels) every step
    carries its estimated player level."""
    out = copy.deepcopy(route)
    units = spawns.get("units", {})
    for step in out.get("steps", []):
        quest_id, npc_id, map_id = step.get("questId"), step.get("npcId"), step.get("mapId")
        step["questName"] = quests.get(quest_id, {}).get("name") if quest_id is not None else None
        step["npcName"] = units.get(str(npc_id), {}).get("name") if npc_id is not None else None
        step["zoneName"] = uimaps.get(map_id) if map_id is not None else None
        if levels is not None and step.get("id") in levels:
            step["level"] = levels[step["id"]]
        if step.get("type") == "complete" and quest_id in quests:
            step["objectives"] = _objectives(quests[quest_id], spawns, step)
    return out
