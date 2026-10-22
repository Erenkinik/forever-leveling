"""Quest selection for a route and the prerequisite graph over the selected quests."""
import heapq
import statistics
from dataclasses import dataclass, field

from pipeline.config import CLASS_BITS
from pipeline.generate import GenerationError
from pipeline.generate.config import ISLAND_MAPS, LEVEL_CAP, ZONE_OUTLIER_SPREAD
from pipeline.generate.zone_order import ZoneOrder

REASONS = ("not-in-forever", "level-unknown", "over-cap", "race", "faction", "class", "zone", "zone-outlier")


@dataclass
class Selection:
    quests: dict[int, dict]
    excluded: dict[str, list[int]] = field(default_factory=dict)
    # Prereqs excluded only because they start outside the route zones, pulled back in (located starts).
    pulled: set[int] = field(default_factory=set)


@dataclass
class QuestGraph:
    order: list[int]
    gaps: dict[int, str]


def _exclusion_reason(q: dict, order: ZoneOrder) -> str | None:
    if not q.get("inForever"):
        return "not-in-forever"
    min_level = q.get("minLevel")
    if min_level is None:
        return "level-unknown"
    if min_level > LEVEL_CAP or (q.get("level") is not None and q["level"] > LEVEL_CAP):
        return "over-cap"
    races = q.get("races")
    if races is not None:
        # Unknown race bits cannot be matched to a race, so the quest is not safe to include.
        if any(r.startswith("unknown-bit-") for r in races) or order.race not in races:
            return "race"
    factions = q.get("factions")
    if factions is not None and order.faction not in factions:
        return "faction"
    if q.get("classes") is not None:
        # Ruling (Phase 2a): the v1 route is class-agnostic; classOnly steps come later.
        return "class"
    if (q.get("start") or {}).get("uiMapId") not in order.zones:
        return "zone"
    return None


def _zone_outliers(selected: dict[int, dict]) -> list[int]:
    """Quests whose level exceeds their start zone's median level (known levels only) by ZONE_OUTLIER_SPREAD."""
    by_zone: dict[int, list[int]] = {}
    for q in selected.values():
        if q.get("level") is not None:
            by_zone.setdefault(q["start"]["uiMapId"], []).append(q["level"])
    medians = {zone: statistics.median(levels) for zone, levels in by_zone.items()}
    return [
        qid for qid, q in selected.items()
        if q.get("level") is not None and q["level"] > medians[q["start"]["uiMapId"]] + ZONE_OUTLIER_SPREAD
    ]


def _has_start_point(q: dict) -> bool:
    start = q.get("start") or {}
    return all(start.get(k) is not None for k in ("uiMapId", "x", "y"))


def _short_detour(dependent: dict, prereq: dict, continents: dict[int, int] | None) -> bool:
    """True when the prereq starts on the dependent's continent and not on an island (no boat trip)."""
    a, b = dependent["start"].get("uiMapId"), prereq["start"]["uiMapId"]
    if b in ISLAND_MAPS and a not in ISLAND_MAPS:
        return False
    if continents is None:
        return True
    return continents.get(a) is not None and continents.get(a) == continents.get(b)


def _for_most_classes(q: dict) -> bool:
    """A class version every class but one can do (the one left has its own version of the quest). Data lists
    a Horde quest without Paladins and an Alliance one without Shamans, so two classes may be missing."""
    return q.get("classes") is not None and len(q["classes"]) >= len(CLASS_BITS) - 2


def _choose_alternative(q: dict, quests: dict[int, dict], selected: dict[int, dict], off_route: set[int],
                        class_out: set[int], continents: dict[int, int] | None) -> dict:
    """For a quest whose prereqs are alternatives (prereqsAny), the quest with only the one this route does:
    one already on the route (on the quest's own start map first), else the first that can be pulled in, else a
    version for all classes but one that was left out for its class. Without any, the quest keeps all its
    prereqs (and becomes a gap)."""
    if not q.get("prereqsAny"):
        return q
    alternatives = [p for p in q["prereqs"] if p in quests]
    on_route = [p for p in alternatives if p in selected]
    here = q["start"].get("uiMapId")
    on_route.sort(key=lambda p: (quests[p]["start"].get("uiMapId") != here, p))
    pullable = [p for p in alternatives if p in off_route and _has_start_point(quests[p])
                and _short_detour(q, quests[p], continents)]
    class_versions = [p for p in alternatives if p in class_out and _for_most_classes(quests[p])
                      and quests[p]["start"].get("uiMapId") == here]
    chosen = (on_route or pullable or class_versions or [None])[0]
    return q if chosen is None else {**q, "prereqs": [chosen]}


def _pull_prereqs(quests: dict[int, dict], selected: dict[int, dict], excluded: dict[str, list[int]],
                  continents: dict[int, int] | None) -> set[int]:
    """Bring back prereqs of selected quests that were excluded only for starting outside the route zones.

    Without them the whole chain would be a gap; with a located start on the same continent the route can
    detour to them. Prereqs of pulled quests are pulled too.
    """
    off_route = set(excluded.get("zone", []))
    class_out = set(excluded.get("class", []))
    pulled: set[int] = set()
    for qid in list(selected):
        before = selected[qid]
        selected[qid] = _choose_alternative(before, quests, selected, off_route, class_out, continents)
        chosen = selected[qid]["prereqs"]
        if chosen != before["prereqs"] and chosen[0] in class_out:  # the chosen class version joins the route
            class_out.discard(chosen[0])
            selected[chosen[0]] = quests[chosen[0]]
    queue = list(selected)
    while queue:
        dependent = selected[queue.pop()]
        for p in dependent.get("prereqs") or []:
            if p in off_route and _has_start_point(quests[p]) and _short_detour(dependent, quests[p], continents):
                off_route.discard(p)
                selected[p] = _choose_alternative(quests[p], quests, selected, off_route, class_out, continents)
                pulled.add(p)
                queue.append(p)
    for reason, left in (("zone", off_route), ("class", class_out)):
        if left:
            excluded[reason] = sorted(left)
        else:
            excluded.pop(reason, None)
    return pulled


def drop_pulled(sel: Selection, drop: set[int]) -> Selection:
    """Undo pulling `drop` back in, and any pulled quest that is then no selected quest's prereq."""
    quests = dict(sel.quests)
    pulled = set(sel.pulled)
    excluded = {k: list(v) for k, v in sel.excluded.items()}
    while drop:
        for qid in drop:
            quests.pop(qid, None)
            pulled.discard(qid)
            excluded.setdefault("zone", []).append(qid)
        needed = {p for q in quests.values() for p in q.get("prereqs") or []}
        drop = {qid for qid in pulled if qid not in needed}
    excluded["zone"] = sorted(excluded["zone"])
    return Selection(quests, excluded, pulled)


def select_quests(quests: dict[int, dict], order: ZoneOrder, continents: dict[int, int] | None = None) -> Selection:
    """Keep quests usable on the route; each excluded quest is counted under its first failing reason.

    The zone-outlier check runs over the quests that passed every other filter; then located prereqs
    that start outside the route zones are pulled back in (Selection.pulled).
    """
    selected: dict[int, dict] = {}
    excluded: dict[str, list[int]] = {}
    for qid in sorted(quests):
        reason = _exclusion_reason(quests[qid], order)
        if reason is None:
            selected[qid] = quests[qid]
        else:
            excluded.setdefault(reason, []).append(qid)
    outliers = _zone_outliers(selected)
    if outliers:
        excluded["zone-outlier"] = outliers
        for qid in outliers:
            del selected[qid]
    pulled = _pull_prereqs(quests, selected, excluded, continents)
    return Selection(dict(sorted(selected.items())), excluded, pulled)


def _cycle_members(deps: dict[int, set[int]]) -> list[int]:
    """Nodes that lie on or between cycles: peel off nodes nothing depends on, then nodes with no prereqs."""
    alive = set(deps)
    changed = True
    while changed:
        changed = False
        needed = {p for n in alive for p in deps[n] if p in alive}
        for n in sorted(alive):
            if n not in needed or not (deps[n] & alive):
                alive.discard(n)
                changed = True
    return sorted(alive)


def build_graph(sel: Selection, tier: str) -> QuestGraph:
    """Topological order (ties by (minLevel, id)); prereqs outside the selection are gaps (beta) or errors (full)."""
    gaps: dict[int, str] = {}
    deps: dict[int, set[int]] = {}
    for qid, q in sel.quests.items():
        deps[qid] = {p for p in q.get("prereqs") or [] if p in sel.quests}
        missing = sorted(p for p in q.get("prereqs") or [] if p not in sel.quests)
        if missing:
            if tier == "full":
                raise GenerationError(f"quest {qid}: prereq {missing[0]} not in route (full tier)")
            gaps[qid] = f"prereq {missing[0]} not in route"

    dependents: dict[int, list[int]] = {qid: [] for qid in deps}
    remaining = {qid: len(d) for qid, d in deps.items()}
    for qid, d in deps.items():
        for p in d:
            dependents[p].append(qid)

    def key(qid: int) -> tuple[int, int]:
        return (sel.quests[qid]["minLevel"], qid)

    heap = [key(q) for q, n in remaining.items() if n == 0]
    heapq.heapify(heap)
    result: list[int] = []
    while heap:
        _, qid = heapq.heappop(heap)
        result.append(qid)
        for dep in dependents[qid]:
            remaining[dep] -= 1
            if remaining[dep] == 0:
                heapq.heappush(heap, key(dep))

    if len(result) != len(deps):
        stuck = {q: d for q, d in deps.items() if q not in set(result)}
        members = _cycle_members(stuck)
        raise GenerationError(f"prerequisite cycle among quests {members}")
    return QuestGraph(result, gaps)
