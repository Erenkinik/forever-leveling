"""Suggest a zone order from quest data: start zone, then zones by median quest level."""
import statistics
from dataclasses import dataclass

from pipeline.generate.config import (
    CITY_ZONES, CONTINENT_SWITCH_PENALTY, CONTINENTS, LEVEL_CAP, MIN_ZONE_QUESTS, START_ZONES, ZONE_BEHIND,
)
from pipeline.generate.graph import select_quests
from pipeline.generate.zone_order import ZoneOrder


@dataclass(frozen=True)
class ZoneStat:
    uiMapId: int
    name: str
    median: float
    count: int
    continent: str


def _zone_stats(quests: dict[int, dict], names: dict[int, str], parents: dict[int, int], race: str,
                faction: str) -> dict[int, ZoneStat]:
    """Usable quests of known level grouped by start zone; only zones directly under a continent."""
    sel = select_quests(quests, ZoneOrder("suggest", race, faction, False, list(names)))
    levels: dict[int, list[int]] = {}
    for q in sel.quests.values():
        if q.get("level") is not None:
            levels.setdefault(q["start"]["uiMapId"], []).append(q["level"])
    return {
        map_id: ZoneStat(map_id, names[map_id], statistics.median(lv), len(lv), CONTINENTS[parents[map_id]])
        for map_id, lv in levels.items()
        if parents.get(map_id) in CONTINENTS
    }


def suggest_zones(quests: dict[int, dict], names: dict[int, str], parents: dict[int, int], race: str,
                  faction: str) -> list[ZoneStat]:
    """Start zone first; then repeatedly the zone with the lowest median level, where a zone on the other
    continent counts CONTINENT_SWITCH_PENALTY levels higher.

    Left out: cities, other races' start zones, zones under MIN_ZONE_QUESTS, zones whose median level is
    LEVEL_CAP or more, and zones left more than ZONE_BEHIND below the highest median reached.
    """
    start_name = START_ZONES.get(race)
    if start_name is None:
        raise ValueError(f"no start zone known for race {race!r}")
    stats = _zone_stats(quests, names, parents, race, faction)
    start = next((s for s in stats.values() if s.name == start_name and s.count >= MIN_ZONE_QUESTS), None)
    if start is None:
        raise ValueError(f"start zone {start_name!r} has fewer than {MIN_ZONE_QUESTS} usable quests for {race}")
    remaining = [
        s for s in stats.values()
        if s.name not in CITY_ZONES and s.name not in START_ZONES.values()
        and s.count >= MIN_ZONE_QUESTS and s.median < LEVEL_CAP
    ]
    result = [start]
    reached = start.median
    while True:
        remaining = [s for s in remaining if s.median >= reached - ZONE_BEHIND]
        if not remaining:
            return result
        here = result[-1].continent
        nxt = min(remaining, key=lambda s: (
            s.median + (CONTINENT_SWITCH_PENALTY if s.continent != here else 0), -s.count, s.uiMapId))
        remaining.remove(nxt)
        result.append(nxt)
        reached = max(reached, nxt.median)


def render_yaml(route: str, race: str, faction: str, stats: list[ZoneStat]) -> str:
    """A zone order file (schema/zone-order.schema.json) marked unreviewed, one comment per zone."""
    lines = [
        "# TASLAK — veriden önerildi (python -m pipeline suggest-zones); Eren gözden geçirecek (§8.2)",
        f"route: {route}",
        f"race: {race}",
        f"faction: {faction}",
        "reviewed: false",
        "zones:",
    ]
    for s in stats:
        lines.append(f"  - {s.name}  # median {s.median:g}, {s.count} quests, {s.continent}")
    return "\n".join(lines) + "\n"
