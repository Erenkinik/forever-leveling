"""Assemble route steps from hubs: accept / complete / turnin, plus travel, grind and gap steps."""
import math

from pipeline.generate import GenerationError
from pipeline.generate.config import (
    CONTINENT_TRAVEL, ISLAND_MAPS, LEVEL_CAP, PORTAL_MAPS, QUEST_LEVEL_MARGIN, QUEST_LOG_LIMIT,
)
from pipeline.generate.flight import Flights
from pipeline.generate.gaps import complete_location, quest_gaps
from pipeline.generate.graph import build_graph, class_only, drop_pulled, select_quests
from pipeline.generate.hubs import Hub, build_hubs, unplaced
from pipeline.generate.xpsim import XpState, kill_xp, quest_level, quest_xp, shared_xp
from pipeline.generate.zone_order import ZoneOrder

TIERS = ("beta", "full")
STEP_TYPES = ("accept", "turnin", "complete", "travel", "flightpath", "sethearth", "train", "grind", "gap")
NON_QUEST_CONFIDENCE = "unverified"
# Exclusion reasons whose quest ids the report lists; the others are counted only.
LISTED_EXCLUSIONS = ("class", "zone-outlier")


class _Steps:
    """Step list that emits a travel step on every map change and keeps ids unique (-2, -3, ...).

    `continents` (map -> continent UiMap) decides the travel mode: across continents, or to or from an
    island, the faction's boat or zeppelin; to or from Zephras Isle the Skyborne portal; otherwise walking. Unknown maps walk. With `flights`, a flight master
    near a step is found there (a flightpath step), and a walk to another map flies when that is much shorter.
    Steps of the quests in `classes` (quest id -> classes) are marked classOnly.
    """

    def __init__(self, faction: str = "Alliance", continents: dict[int, int] | None = None,
                 flights: Flights | None = None, classes: dict[int, list[str]] | None = None) -> None:
        self.steps: list[dict] = []
        self._used: set[str] = set()
        self.pos: tuple[int, float, float] | None = None
        self._ship = CONTINENT_TRAVEL.get(faction, "boat")
        self._continents = continents or {}
        self._flights = flights
        self._classes = classes or {}

    def _mode(self, src: int, dst: int) -> str:
        if src in PORTAL_MAPS or dst in PORTAL_MAPS:
            return "portal"
        a, b = self._continents.get(src), self._continents.get(dst)
        if src in ISLAND_MAPS or dst in ISLAND_MAPS or (a is not None and b is not None and a != b):
            return "boat" if (src in ISLAND_MAPS or dst in ISLAND_MAPS) else self._ship
        return "walk"

    def add(self, base_id: str, kind: str, map_id: int, x: float, y: float,
            confidence: str = NON_QUEST_CONFIDENCE, **extra) -> None:
        if extra.get("questId") in self._classes:
            extra["classOnly"] = self._classes[extra["questId"]]
        if self.pos is not None and self.pos[0] != map_id:
            mode = self._mode(self.pos[0], map_id)
            hop = self._flights.plan(self.pos, (map_id, x, y)) if self._flights and mode == "walk" else None
            if hop:
                a, b = (self._flights.nodes[n] for n in hop)
                self._push(f"travel-fly-{hop[0]}-{hop[1]}", "travel", b["uiMapId"], b["x"], b["y"],
                           NON_QUEST_CONFIDENCE, {"mode": "flight", "radius": 5, "fromNode": a["name"], "node": b["name"]})
            if self.pos[0] != map_id:
                self._push(f"travel-{self.pos[0]}-{map_id}", "travel", map_id, x, y, NON_QUEST_CONFIDENCE,
                           {"mode": self._mode(self.pos[0], map_id), "radius": 5})
        self._push(base_id, kind, map_id, x, y, confidence, extra)
        self._find_flight_masters()

    def _find_flight_masters(self) -> None:
        """A flightpath step for each flight master not found yet near where the player now is."""
        if self._flights is None or self.pos is None:
            return
        for n in self._flights.found_near(*self.pos):
            node = self._flights.nodes[n]
            self._flights.known.add(n)
            self.add(f"flightpath-{n}", "flightpath", node["uiMapId"], node["x"], node["y"], node=node["name"])

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


def _turn_in(steps: _Steps, qid: int, quests: dict[int, dict], xp_table: dict[int, list[int]],
             state: XpState) -> XpState:
    q = quests[qid]
    e = q["end"]
    steps.add(f"turnin-{qid}", "turnin", e["uiMapId"], e["x"], e["y"], q["confidence"], questId=qid, npcId=e["id"])
    return state.gain(quest_xp(quest_level(q), xp_table, state.level)) if shared_xp(q) else state


class _Deferred:
    """Turn-ins whose NPC is on another map than the hub's.

    They wait until the route is on that map anyway, until it leaves the zone (unless a later route zone
    is that map), until a quest that needs one is about to be accepted, until a grind (their XP first), until
    the quest log would overflow, or until the route ends.
    """

    def __init__(self) -> None:
        self.ids: list[int] = []

    def take(self, qid: int, quests: dict[int, dict], here: int) -> bool:
        if quests[qid]["end"]["uiMapId"] != here:
            self.ids.append(qid)
            return True
        return False

    def flush_needed(self, steps: _Steps, chunk: list[int], quests: dict[int, dict],
                     xp_table: dict[int, list[int]], state: XpState) -> XpState:
        """Turn in the waiting quests that a quest of `chunk` needs, so it can be accepted."""
        needed = {p for qid in chunk for p in quests[qid].get("prereqs") or []}
        keep = {quests[q]["end"]["uiMapId"] for q in self.ids if q not in needed}
        due_maps = {quests[q]["end"]["uiMapId"] for q in self.ids if q in needed}
        return self.flush(steps, quests, xp_table, state, keep_maps=keep - due_maps) if due_maps else state

    def flush(self, steps: _Steps, quests: dict[int, dict], xp_table: dict[int, list[int]], state: XpState,
              keep_maps=frozenset()) -> XpState:
        """Turn in every waiting quest except those ending on keep_maps; the current map first, then by map."""
        due = [q for q in self.ids if quests[q]["end"]["uiMapId"] not in keep_maps]
        here = steps.pos[0] if steps.pos else None
        first_seen = {m: i for i, m in reversed(list(enumerate(quests[q]["end"]["uiMapId"] for q in due)))}
        due.sort(key=lambda q: (quests[q]["end"]["uiMapId"] != here, first_seen[quests[q]["end"]["uiMapId"]]))
        for qid in due:
            self.ids.remove(qid)
            state = _turn_in(steps, qid, quests, xp_table, state)
        return state

    def flush_here(self, steps: _Steps, quests: dict[int, dict], xp_table: dict[int, list[int]],
                   state: XpState) -> XpState:
        here = steps.pos[0] if steps.pos else None
        others = {quests[q]["end"]["uiMapId"] for q in self.ids} - {here}
        return self.flush(steps, quests, xp_table, state, keep_maps=others)


def _run_chunk(steps: _Steps, chunk: list[int], quests: dict[int, dict], spawns: dict,
               xp_table: dict[int, list[int]], state: XpState, zones: list[int], deferred: _Deferred,
               here: int, continents: dict[int, int] | None) -> XpState:
    """Accept every quest, complete objectives nearest-neighbour first, then turn every quest in.

    Quests ending on another map than `here` (the hub's map) are handed to `deferred` instead.
    """
    state = deferred.flush_needed(steps, chunk, quests, xp_table, state)
    for qid in chunk:
        q = quests[qid]
        s = q["start"]
        steps.add(f"accept-{qid}", "accept", s["uiMapId"], s["x"], s["y"], q["confidence"], questId=qid, npcId=s["id"])

    pending = {qid: loc for qid in chunk
               if (loc := complete_location(quests[qid], spawns, zones, continents)) is not None}
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
        if shared_xp(quests[qid]):
            state = state.gain(kill_xp(quests[qid], state.level))

    for qid in chunk:
        if not deferred.take(qid, quests, here):
            state = _turn_in(steps, qid, quests, xp_table, state)
    return deferred.flush_here(steps, quests, xp_table, state)


def level_needed(q: dict) -> int:
    """The level a quest is taken at: its minLevel, and at most QUEST_LEVEL_MARGIN below its level."""
    return max(q["minLevel"] or 1, quest_level(q) - QUEST_LEVEL_MARGIN)


def _run_doable(steps: _Steps, pending: list[int], quests: dict[int, dict], spawns: dict,
                xp_table: dict[int, list[int]], state: XpState, zones: list[int], deferred: "_Deferred",
                here: int, continents: dict[int, int] | None, last: bool) -> tuple[XpState, list[int]]:
    """Run the quests that are doable (level_needed reached, no prereq still pending), again as their XP makes more
    doable. The rest wait for the next hub on this map; on the map's `last` chunk a grind at the start of the one
    needing the lowest level makes it doable. Returns the state and the quests still waiting."""
    pending = list(pending)
    while pending:
        waiting = set(pending)
        free = [qid for qid in pending if not waiting & set(quests[qid].get("prereqs") or [])]
        ready = [qid for qid in free if level_needed(quests[qid]) <= state.level]
        if not ready:
            if not last:
                return state, pending
            if deferred.ids:  # turn in what waits first: its XP may be enough
                state = deferred.flush(steps, quests, xp_table, state)
                continue
            first = min(free, key=lambda qid: level_needed(quests[qid]))
            need, s = level_needed(quests[first]), quests[first]["start"]
            steps.add(f"grind-{s['uiMapId']}-{need}", "grind", s["uiMapId"], s["x"], s["y"], untilLevel=need)
            state = XpState(need, 0)
            continue
        for part in _chunks(ready, quests):  # the quest log limit still holds
            if len(deferred.ids) + len(part) > QUEST_LOG_LIMIT:
                state = deferred.flush(steps, quests, xp_table, state)
            state = _run_chunk(steps, part, quests, spawns, xp_table, state, zones, deferred, here, continents)
        pending = [qid for qid in pending if qid not in ready]
    return state, []


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
                   tier: str, data_build: str, now: str, reach_cap: bool = True,
                   continents: dict[int, int] | None = None, taxi: dict | None = None) -> tuple[dict, dict]:
    """Build the route for a zone order and the generation report. XP is an estimate.

    reach_cap=False leaves out the closing grind to LEVEL_CAP (unit tests of the quest steps).
    continents (map -> continent UiMap) sets boat/zeppelin travel; without it every trip walks. taxi
    (data/canonical/taxi.json) adds flight paths; without it there are none.
    """
    if tier not in TIERS:
        raise GenerationError(f"unknown release tier {tier!r}; expected one of {TIERS}")
    sel = select_quests(quests, order, continents)
    while True:
        graph = build_graph(sel, tier)
        hubs = build_hubs(sel.quests, graph, order.zones, sel.pulled)
        no_start = unplaced(sel.quests, graph, order.zones, sel.pulled)
        gaps = quest_gaps(sel.quests, graph, set(no_start), spawns, order.zones, continents)
        # A pulled-in prereq that cannot be done itself, or that no doable quest needs, only adds a detour:
        # drop it again.
        useless = {p for p in sel.pulled
                   if p in gaps or all(d in gaps for d in sel.quests if p in (sel.quests[d].get("prereqs") or []))}
        if not useless:
            break
        sel = drop_pulled(sel, useless)
    if tier == "full" and gaps:
        first = min(gaps, key=graph.order.index)
        raise GenerationError(f"{len(gaps)} gap(s) in a full-tier route; first: {gaps[first]}")

    position = {qid: i for i, qid in enumerate(graph.order)}
    attached = _attach_unplaced(no_start, sel.quests, hubs)
    classes = {qid: class_only(q, order.race, order.faction) for qid, q in sel.quests.items() if q.get("classes")}
    steps = _Steps(order.faction, continents, Flights(taxi, order.faction) if taxi else None, classes)
    state = XpState(1, 0)
    deferred = _Deferred()
    waiting: list[int] = []  # quests of this map not doable yet (level), tried again at the next hub
    for index, hub in enumerate(hubs):
        if index > 0 and hubs[index - 1].mapId != hub.mapId and deferred.ids:
            # Leaving a zone: turn in what waits elsewhere, unless a later route zone is that map.
            later = {h.mapId for h in hubs[index:]}
            state = deferred.flush(steps, sel.quests, xp_table, state, keep_maps=later)
        if any(sel.quests[q]["end"]["uiMapId"] == hub.mapId for q in deferred.ids):
            # Arriving where waiting quests end: turn them in first.
            others = {sel.quests[q]["end"]["uiMapId"] for q in deferred.ids} - {hub.mapId}
            state = deferred.flush(steps, sel.quests, xp_table, state, keep_maps=others)
        hub_gaps = sorted([q for q in hub.quests if q in gaps] + attached.get(index, []), key=position.__getitem__)
        for qid in hub_gaps:
            on_map = steps.pos is not None and steps.pos[0] == hub.mapId
            x, y = (steps.pos[1], steps.pos[2]) if on_map else (hub.x, hub.y)
            steps.add(f"gap-{qid}", "gap", hub.mapId, x, y, questId=qid, reason=gaps[qid])

        chunks = _chunks([q for q in hub.quests if q not in gaps], sel.quests) or [[]]
        last_on_map = index == len(hubs) - 1 or hubs[index + 1].mapId != hub.mapId
        for n, chunk in enumerate(chunks):
            state, waiting = _run_doable(steps, waiting + chunk, sel.quests, spawns, xp_table, state, order.zones,
                                         deferred, hub.mapId, continents, last_on_map and n == len(chunks) - 1)
    state = deferred.flush(steps, sel.quests, xp_table, state)

    # spec 2.5: the route reaches LEVEL_CAP. Kill XP is only a rough estimate, so any shortfall is one closing
    # grind.
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
        "pulledIn": sorted(sel.pulled),
        "excludedIds": {reason: sorted(ids) for reason, ids in sel.excluded.items() if reason in LISTED_EXCLUSIONS},
        "xpIsEstimate": True,
    }
    return route, report
