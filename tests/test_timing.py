import pytest

from pipeline.export.timing import (
    FLIGHT_OVERHEAD_SECONDS, FLY_YARDS_PER_SECOND, KILL_SECONDS, RUN_YARDS_PER_SECOND, SHIP_SECONDS, TALK_SECONDS,
    ZONE_CROSSING_SECONDS, step_seconds,
)

# One 1000 x 1000 yard map: map x runs along -Y, map y along -X (pipeline.normalize.taxi).
TAXI = {
    "bounds": {"10": [0.0, 0.0, 1000.0, 1000.0, 0]},
    "nodes": {"1": {"name": "A", "world": [0.0, 0.0]}, "2": {"name": "B", "world": [0.0, 900.0]}},
}


def _s(sid, kind, x=0.0, y=0.0, map_id=10, **kw):
    return {"id": sid, "type": kind, "mapId": map_id, "x": x, "y": y, **kw}


def test_steps_take_the_walk_there_plus_what_is_done_there():
    quests = {7: {"kills": [{"kind": "kill", "id": 1, "count": 10, "chance": None, "level": 2.0}]}}
    route = {"steps": [
        _s("a", "accept", 10, 10, questId=7),
        _s("c", "complete", 10, 50, questId=7),          # 400 yards further
        _s("g", "gap", 90, 90),                          # takes no time, and is no place
        _s("t", "turnin", 10, 10, questId=7),            # back 400 yards
        _s("f", "travel", 0, 0, mode="flight", fromNode="A", node="B"),
        _s("b", "travel", 0, 0, map_id=20, mode="boat"),
        _s("w", "travel", 0, 0, map_id=30, mode="walk"),
    ]}
    secs = step_seconds(route, quests, None, TAXI)
    assert secs["a"] == TALK_SECONDS
    assert secs["c"] == round(400 / RUN_YARDS_PER_SECOND + 10 * KILL_SECONDS)
    assert secs["g"] == 0
    assert secs["t"] == round(400 / RUN_YARDS_PER_SECOND + TALK_SECONDS)
    assert secs["f"] == round(900 / FLY_YARDS_PER_SECOND + FLIGHT_OVERHEAD_SECONDS)
    assert (secs["b"], secs["w"]) == (SHIP_SECONDS, ZONE_CROSSING_SECONDS)


def test_a_grind_takes_the_kills_for_the_missing_xp():
    from pipeline.generate.config import PLAYER_XP_TO_LEVEL
    from pipeline.generate.xpsim import mob_xp

    secs = step_seconds({"steps": [_s("g", "grind", untilLevel=3)]}, {}, {"g": 1}, TAXI)
    kills = (PLAYER_XP_TO_LEVEL[1] + PLAYER_XP_TO_LEVEL[2]) / mob_xp(1, 1)
    assert secs["g"] == pytest.approx(kills * KILL_SECONDS, abs=1)
