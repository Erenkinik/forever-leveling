"""Group quest start points into hubs and order them along the route."""
import math
from dataclasses import dataclass

from pipeline.generate.config import HUB_RADIUS
from pipeline.generate.graph import QuestGraph

LEVEL_WINDOW = 1.0


@dataclass
class Hub:
    """A cluster of quest starts.

    mapId, x, y and avgLevel describe the original cluster before prereq moves. Quests moved
    in from another hub or zone keep their own data, so consumers must use each quest's own
    start coordinates and uiMapId, not the hub's.
    """

    mapId: int
    x: float
    y: float
    quests: list[int]
    avgLevel: float


def _is_placed(q: dict, zones: list[int]) -> bool:
    start = q.get("start") or {}
    return start.get("x") is not None and start.get("y") is not None and start.get("uiMapId") in zones


def _level(qid: int, q: dict) -> float:
    level = q.get("level")
    if level is None:
        level = q.get("minLevel")
    if level is None:
        raise ValueError(f"quest {qid}: neither level nor minLevel is set")
    return level


def unplaced(quests: dict[int, dict], graph: QuestGraph, zones: list[int]) -> list[int]:
    """Quests in route order that build_hubs does not place (missing x, y or uiMapId, or map not in zones)."""
    return [qid for qid in graph.order if not _is_placed(quests[qid], zones)]


def _cluster(ids: list[int], quests: dict[int, dict]) -> list[list[int]]:
    """Connected components where two starts are linked when their distance is <= HUB_RADIUS."""
    pts = {i: (quests[i]["start"]["x"], quests[i]["start"]["y"]) for i in ids}
    seen: set[int] = set()
    clusters: list[list[int]] = []
    for root in ids:
        if root in seen:
            continue
        seen.add(root)
        stack, comp = [root], []
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for other in ids:
                if other not in seen and math.dist(pts[cur], pts[other]) <= HUB_RADIUS:
                    seen.add(other)
                    stack.append(other)
        clusters.append(comp)
    return clusters


def _order_zone(hubs: list[Hub], first_id: dict[int, int]) -> list[Hub]:
    """Greedy: lowest avgLevel first, then the hub nearest the previous centre among those within the window."""
    remaining = sorted(hubs, key=lambda h: (h.avgLevel, first_id[id(h)]))
    ordered: list[Hub] = []
    while remaining:
        if not ordered:
            pick = remaining[0]
        else:
            prev = ordered[-1]
            low = remaining[0].avgLevel
            window = [h for h in remaining if h.avgLevel - low <= LEVEL_WINDOW]
            pick = min(window, key=lambda h: (math.dist((prev.x, prev.y), (h.x, h.y)), first_id[id(h)]))
        remaining.remove(pick)
        ordered.append(pick)
    return ordered


def build_hubs(quests: dict[int, dict], graph: QuestGraph, zones: list[int]) -> list[Hub]:
    """Hubs in zone order, then level order. No quest precedes its prereq.

    Centre and avgLevel describe the cluster of start points before prereq moves, so the
    hub order stays fixed while quests move to later hubs. Hubs left empty by moves are dropped.
    """
    pos_in_order = {qid: i for i, qid in enumerate(graph.order)}
    placed = [q for q in graph.order if _is_placed(quests[q], zones)]

    hubs: list[Hub] = []
    first_id: dict[int, int] = {}
    for zone in zones:
        zone_ids = [q for q in placed if quests[q]["start"].get("uiMapId") == zone]
        zone_hubs: list[Hub] = []
        for comp in _cluster(zone_ids, quests):
            comp.sort(key=pos_in_order.__getitem__)
            xs = [quests[i]["start"]["x"] for i in comp]
            ys = [quests[i]["start"]["y"] for i in comp]
            hub = Hub(zone, sum(xs) / len(xs), sum(ys) / len(ys), comp,
                      sum(_level(i, quests[i]) for i in comp) / len(comp))
            first_id[id(hub)] = min(comp)
            zone_hubs.append(hub)
        hubs.extend(_order_zone(zone_hubs, first_id))

    hub_index = {qid: n for n, hub in enumerate(hubs) for qid in hub.quests}
    changed = True
    while changed:
        changed = False
        for qid in placed:
            later = max((hub_index[p] for p in quests[qid].get("prereqs") or [] if p in hub_index), default=-1)
            if later > hub_index[qid]:
                hub_index[qid] = later
                changed = True

    for hub in hubs:
        hub.quests = []
    for qid in placed:
        hubs[hub_index[qid]].quests.append(qid)
    return [h for h in hubs if h.quests]
