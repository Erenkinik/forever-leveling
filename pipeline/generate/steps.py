"""Assemble route steps from hubs: accept / complete / turnin, plus travel, grind and gap steps."""
import math

from pipeline.generate import GenerationError
from pipeline.generate.config import GRIND_TRIGGER, LEVEL_CAP, QUEST_LOG_LIMIT
from pipeline.generate.gaps import complete_location, quest_gaps
from pipeline.generate.graph import build_graph, select_quests
from pipeline.generate.hubs import Hub, build_hubs, unplaced
from pipeline.generate.xpsim import XpState, quest_level, quest_xp
from pipeline.generate.zone_order import ZoneOrder

TIERS = ("beta", "full")
STEP_TYPES = ("accept", "turnin", "complete", "travel", "sethearth", "train", "grind", "gap")
NON_QUEST_CONFIDENCE = "unverified"
# Exclusion reasons whose quest ids the report lists; the others are counted only.
LISTED_EXCLUSIONS = ("class", "zone-outlier")


class _Steps:
    """Step list that emits a travel step on every map change and keeps ids unique (-2, -3, ...)."""

    def __init__(self) -> None:
        self.steps: list[dict] = []
        self._used: set[str] = set()
        self.pos: tuple[int, float, float] | None = None

    def add(self, base_id: str, kind: str, map_id: int, x: float, y: float,
            confidence: str = NON_QUEST_CONFIDENCE, **extra) -> None:
        if self.pos is not None and self.pos[0] != map_id:
            self._push(f"travel-{self.pos[0]}-{map_id}", "travel", map_id, x, y, NON_QUEST_CONFIDENCE,
                       {"mode": "walk", "radius": 5})
        self._push(base_id, kind, map_id, x, y, confidence, extra)

    def _push(self, base_id: str, kind: str, map_id: int, x: float, y: float, confidence: str, extra: dict) -> None:
        sid, n = base_id, 1
        while sid in self._used:
            n += 1
            sid = f"{base_id}-{n}"
        self._used.add(sid)
        self.steps.append({"id": sid, "type": kind, "mapId": map_id, "x": x, "y": y, "confidence": confidence, **extra})
        self.pos = (map_id, x, y)


def _chunks(ids: list[int], quests: dict[int, dict]) -> list[list[int]]:
    """Split a hub's quests so no chunk holds a quest and its prereq, nor more than QUEST_LOG_LIMIT quests.

    `ids` is in prereq order, so a quest's wave is one past its latest in-hub prereq.
    """
    wave: dict[int, int] = {}
    for qid in ids:
        wave[qid] = 1 + max((wave[p] for p in quests[qid].get("prereqs") or [] if p in wave), default=-1)
    out: list[list[int]] = []
    for w in sorted(set(wave.values())):
        members = [q for q in ids if wave[q] == w]
        out.extend(members[i:i + QUEST_LOG_LIMIT] for i in range(0, len(members), QUEST_LOG_LIMIT))
    return out


def _run_chunk(steps: _Steps, chunk: list[int], quests: dict[int, dict], spawns: dict,
               xp_table: dict[int, list[int]], state: XpState, zones: list[int]) -> XpState:
    """Accept every quest, complete objectives nearest-neighbour first, then turn every quest in."""
    for qid in chunk:
        q = quests[qid]
        s = q["start"]
        steps.add(f"accept-{qid}", "accept", s["uiMapId"], s["x"], s["y"], q["confidence"], questId=qid, npcId=s["id"])

    pending = {qid: loc for qid in chunk if (loc := complete_location(quests[qid], spawns, zones)) is not None}
    rank = {qid: i for i, qid in enumerate(chunk)}
    while pending:
        cur_map, cx, cy = steps.pos

        def key(qid: int) -> tuple:
            map_id, x, y = pending[qid]
            same = map_id == cur_map
            return (not same, math.dist((cx, cy), (x, y)) if same else 0.0, rank[qid])

        qid = min(pending, key=key)
        map_id, x, y = pending.pop(qid)
        steps.add(f"complete-{qid}", "complete", map_id, x, y, quests[qid]["confidence"], questId=qid)

    for qid in chunk:
        q = quests[qid]
        e = q["end"]
        steps.add(f"turnin-{qid}", "turnin", e["uiMapId"], e["x"], e["y"], q["confidence"], questId=qid, npcId=e["id"])
        state = state.gain(quest_xp(quest_level(q), xp_table))
    return state


def _min_level_gate(steps: _Steps, chunk: list[int], quests: dict[int, dict], state: XpState) -> XpState:
    """Grind at the first quest's start until every quest in the chunk is within GRIND_TRIGGER of its minLevel."""
    need = max(quests[qid]["minLevel"] for qid in chunk) - GRIND_TRIGGER
    if state.level >= need:
        return state
    s = quests[chunk[0]]["start"]
    steps.add(f"grind-{s['uiMapId']}-{need}", "grind", s["uiMapId"], s["x"], s["y"], untilLevel=need)
    return XpState(need, 0)


def _attach_unplaced(ids: list[int], quests: dict[int, dict], hubs: list[Hub]) -> dict[int, list[int]]:
    """Hub index for each quest without start coordinates: same map, closest avgLevel, earliest on ties."""
    if ids and not hubs:
        raise GenerationError(f"no hub to anchor gap steps for quests {ids}")
    out: dict[int, list[int]] = {}
    for qid in ids:
        q = quests[qid]
        candidates = [i for i, h in enumerate(hubs) if h.mapId == q["start"].get("uiMapId")] or list(range(len(hubs)))
        best = min(candidates, key=lambda i: (abs(hubs[i].avgLevel - quest_level(q)), i))
        out.setdefault(best, []).append(qid)
    return out


def generate_route(order: ZoneOrder, quests: dict[int, dict], spawns: dict, xp_table: dict[int, list[int]],
                   tier: str, data_build: str, now: str, reach_cap: bool = True) -> tuple[dict, dict]:
    """Build the route for a zone order and the generation report. XP is an estimate.

    reach_cap=False leaves out the closing grind to LEVEL_CAP (unit tests of the quest steps).
    """
    if tier not in TIERS:
        raise GenerationError(f"unknown release tier {tier!r}; expected one of {TIERS}")
    sel = select_quests(quests, order)
    graph = build_graph(sel, tier)
    hubs = build_hubs(sel.quests, graph, order.zones)
    no_start = unplaced(sel.quests, graph, order.zones)
    gaps = quest_gaps(sel.quests, graph, set(no_start), spawns, order.zones)
    if tier == "full" and gaps:
        first = min(gaps, key=graph.order.index)
        raise GenerationError(f"{len(gaps)} gap(s) in a full-tier route; first: {gaps[first]}")

    position = {qid: i for i, qid in enumerate(graph.order)}
    attached = _attach_unplaced(no_start, sel.quests, hubs)
    steps = _Steps()
    state = XpState(1, 0)
    for index, hub in enumerate(hubs):
        hub_gaps = sorted([q for q in hub.quests if q in gaps] + attached.get(index, []), key=position.__getitem__)
        for qid in hub_gaps:
            on_map = steps.pos is not None and steps.pos[0] == hub.mapId
            x, y = (steps.pos[1], steps.pos[2]) if on_map else (hub.x, hub.y)
            steps.add(f"gap-{qid}", "gap", hub.mapId, x, y, questId=qid, reason=gaps[qid])

        for chunk in _chunks([q for q in hub.quests if q not in gaps], sel.quests):
            state = _min_level_gate(steps, chunk, sel.quests, state)
            state = _run_chunk(steps, chunk, sel.quests, spawns, xp_table, state, order.zones)

    # spec 2.5: the route reaches LEVEL_CAP. Kill XP is not modelled, so the shortfall is one closing grind.
    quest_level_reached = state.level
    if reach_cap and state.level < LEVEL_CAP and steps.pos is not None:
        map_id, x, y = steps.pos
        steps.add(f"grind-{map_id}-{LEVEL_CAP}", "grind", map_id, x, y, untilLevel=LEVEL_CAP)
        state = XpState(LEVEL_CAP, 0)

    route = {
        "id": order.route,
        "race": order.race,
        "faction": order.faction,
        "levelRange": [1, LEVEL_CAP],
        "generatedAt": now,
        "dataBuild": data_build,
        "reviewed": order.reviewed,
        "releaseTier": tier,
        "steps": steps.steps,
    }
    counts = {t: sum(1 for s in steps.steps if s["type"] == t) for t in STEP_TYPES}
    report = {
        "questLevel": quest_level_reached,
        "estimatedFinalLevel": state.level,
        "stepCounts": counts,
        "gaps": counts["gap"],
        "excluded": {reason: len(ids) for reason, ids in sel.excluded.items()},
        "excludedIds": {reason: sorted(ids) for reason, ids in sel.excluded.items() if reason in LISTED_EXCLUSIONS},
        "xpIsEstimate": True,
    }
    return route, report
