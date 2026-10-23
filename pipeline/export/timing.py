"""Rough time for each route step, for the site's zone times and session plan: walking and flying between steps,
killing what the objectives need, grinding to a level. Every number here is an estimate."""
import math

from pipeline.generate.config import PLAYER_XP_TO_LEVEL
from pipeline.generate.xpsim import mob_xp, objective_kills
from pipeline.normalize.taxi import to_world

RUN_YARDS_PER_SECOND = 7.0      # on foot, no mount below level 40
FLY_YARDS_PER_SECOND = 30.0
FLIGHT_OVERHEAD_SECONDS = 30    # walking to the flight master, the take-off and landing
SHIP_SECONDS = 180              # waiting for the boat or zeppelin and the crossing
ZONE_CROSSING_SECONDS = 60      # walking into the next zone; the walk inside it counts at the next step
TALK_SECONDS = 10               # accepting, turning in, learning a flight path
KILL_SECONDS = 25               # one mob: the fight, looting, a little rest
SAME_MAP_FALLBACK_YARDS = 10.0  # yards per map unit when a map has no bounds


def _yards(a: tuple[int, float, float], b: tuple[int, float, float], bounds: dict[int, list[float]]) -> float:
    """Straight-line yards between two points on the same map; 0 across maps (the travel step covers that)."""
    if a[0] != b[0]:
        return 0.0
    box = bounds.get(a[0])
    if box is None:
        return math.dist(a[1:], b[1:]) * SAME_MAP_FALLBACK_YARDS
    return math.dist(to_world(a[1], a[2], box), to_world(b[1], b[2], box))


def _flight_yards(step: dict, taxi: dict) -> float:
    """The flight's straight length from its start flight master (fromNode) to where it lands (node)."""
    by_name = {n["name"]: n for n in taxi["nodes"].values()}
    start, end = by_name.get(step.get("fromNode")), by_name.get(step.get("node"))
    return math.dist(start["world"], end["world"]) if start and end else 0.0


def _grind_seconds(level: int, until: int) -> float:
    """Killing same-level mobs from `level` to `until`."""
    xp = sum(PLAYER_XP_TO_LEVEL.get(lv, 0) for lv in range(level, until))
    return xp / max(1, mob_xp(level, level)) * KILL_SECONDS


def step_seconds(route: dict, quests: dict[int, dict], levels: dict[str, int] | None,
                 taxi: dict | None) -> dict[str, int]:
    """Step id -> estimated seconds for that step, including getting there from the step before."""
    bounds = {int(k): b for k, b in (taxi or {}).get("bounds", {}).items()}
    out: dict[str, int] = {}
    prev: tuple[int, float, float] | None = None
    for step in route.get("steps", []):
        here = (step["mapId"], step["x"], step["y"])
        kind, seconds = step["type"], 0.0
        if kind == "travel":
            mode = step.get("mode", "walk")
            if mode == "flight" and taxi:
                seconds = _flight_yards(step, taxi) / FLY_YARDS_PER_SECOND + FLIGHT_OVERHEAD_SECONDS
            elif mode in ("boat", "zeppelin"):
                seconds = SHIP_SECONDS
            elif mode == "portal":
                seconds = TALK_SECONDS
            else:
                seconds = ZONE_CROSSING_SECONDS
        elif kind != "gap":
            seconds = _yards(prev, here, bounds) / RUN_YARDS_PER_SECOND if prev else 0.0
            if kind in ("accept", "turnin", "flightpath", "sethearth", "train"):
                seconds += TALK_SECONDS
            elif kind == "complete":
                q = quests.get(step.get("questId"), {})
                seconds += sum(objective_kills(e) for e in q.get("kills", [])) * KILL_SECONDS
            elif kind == "grind":
                seconds += _grind_seconds((levels or {}).get(step["id"], 1), step["untilLevel"])
        out[step["id"]] = round(seconds)
        if kind != "gap":
            prev = here
    return out
