"""Which selected quests become gap steps, and where quest objectives are.

Spawn contract (spawns.json): an entity that is absent, or has empty points, has an unknown
location. An item is located through its dropping units and objects; with none located it is
unknown too. Unknown locations become gaps, never invented coordinates.
"""
from pipeline.generate.graph import QuestGraph

_OBJECTIVE_KINDS = (("units", "unit"), ("objects", "object"), ("items", "item"))


def _entity_points(kind: str, eid: int, spawns: dict) -> list[list]:
    if kind == "unit":
        return (spawns["units"].get(str(eid)) or {}).get("points") or []
    if kind == "object":
        return (spawns["objects"].get(str(eid)) or {}).get("points") or []
    item = spawns["items"].get(str(eid)) or {}
    points: list[list] = []
    for unit in item.get("units", []):
        points.extend(_entity_points("unit", unit, spawns))
    for obj in item.get("objects", []):
        points.extend(_entity_points("object", obj, spawns))
    return points


def _objective_refs(q: dict) -> list[tuple[str, int]]:
    obj = q.get("objectives") or {}
    return [(kind, eid) for key, kind in _OBJECTIVE_KINDS for eid in obj.get(key, [])]


def _allowed_maps(q: dict, zones) -> set:
    """Maps a complete step may sit on: the quest's start and end maps plus the route zones."""
    return {(q.get("start") or {}).get("uiMapId"), (q.get("end") or {}).get("uiMapId")} | set(zones)


def complete_location(q: dict, spawns: dict, zones) -> tuple[int, float, float] | None:
    """Mean of the objective spawn points on the quest's start map, else on the map with the most points.

    Only points on the quest's start map, end map or a route zone count. None when the quest has no
    objectives or no such point. Callers must have ruled out unknown objectives first.
    """
    refs = _objective_refs(q)
    if not refs:
        return None
    allowed = _allowed_maps(q, zones)
    by_map: dict[int, list[tuple[float, float]]] = {}
    for kind, eid in refs:
        for map_id, x, y in _entity_points(kind, eid, spawns):
            if map_id in allowed:
                by_map.setdefault(map_id, []).append((x, y))
    if not by_map:
        return None
    start_map = (q.get("start") or {}).get("uiMapId")
    if start_map in by_map:
        map_id = start_map
    else:
        map_id = max(by_map, key=lambda m: (len(by_map[m]), -m))
    pts = by_map[map_id]
    return map_id, round(sum(p[0] for p in pts) / len(pts), 2), round(sum(p[1] for p in pts) / len(pts), 2)


def _located(ref: dict) -> bool:
    return ref.get("uiMapId") is not None and ref.get("x") is not None and ref.get("y") is not None


def _own_reason(q: dict, spawns: dict, zones) -> str | None:
    start, end = q.get("start") or {}, q.get("end") or {}
    if start.get("type") != "npc" or start.get("id") is None:
        return f"start type is {start.get('type') or 'unknown'}, not an NPC"
    if not _located(end):
        return "end location unknown"
    if end.get("type") != "npc" or end.get("id") is None:
        return f"end type is {end.get('type') or 'unknown'}, not an NPC"
    for kind, eid in _objective_refs(q):
        if not _entity_points(kind, eid, spawns):
            return f"objective {kind} {eid} location unknown"
    if _objective_refs(q) and complete_location(q, spawns, zones) is None:
        return "objective located only off-route"
    return None


def quest_gaps(quests: dict[int, dict], graph: QuestGraph, unplaced: set[int], spawns: dict,
               zones) -> dict[int, str]:
    """Quest id -> gap reason, in graph order so a gap propagates to every (transitive) dependent."""
    gaps: dict[int, str] = {}
    for qid in graph.order:
        q = quests[qid]
        gap_prereq = next((p for p in sorted(q.get("prereqs") or []) if p in gaps), None)
        if qid in graph.gaps:
            reason = graph.gaps[qid]
        elif gap_prereq is not None:
            reason = f"prereq {gap_prereq} is a gap"
        elif qid in unplaced:
            reason = "start location unknown"
        else:
            reason = _own_reason(q, spawns, zones)
        if reason is not None:
            gaps[qid] = f"quest {qid}: {reason}"
    return gaps
