"""Quest selection for a route and the prerequisite graph over the selected quests."""
import heapq
import statistics
from dataclasses import dataclass, field

from pipeline.generate import GenerationError
from pipeline.generate.config import LEVEL_CAP, ZONE_OUTLIER_SPREAD
from pipeline.generate.zone_order import ZoneOrder

REASONS = ("not-in-forever", "level-unknown", "over-cap", "race", "faction", "class", "zone", "zone-outlier")


@dataclass
class Selection:
    quests: dict[int, dict]
    excluded: dict[str, list[int]] = field(default_factory=dict)


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


def select_quests(quests: dict[int, dict], order: ZoneOrder) -> Selection:
    """Keep quests usable on the route; each excluded quest is counted under its first failing reason.

    The zone-outlier check runs last, over the quests that passed every other filter.
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
    return Selection(selected, excluded)


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
