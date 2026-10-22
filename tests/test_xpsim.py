from pathlib import Path

import pytest

from pipeline.generate.config import LEVEL_CAP, PLAYER_XP_TO_LEVEL
from pipeline.generate.xpsim import XpState, quest_xp
from pipeline.ingest.wago import load_quest_xp

FIX = Path(__file__).parent / "fixtures" / "wago"


def test_load_quest_xp_reads_all_difficulty_columns():
    table = load_quest_xp(FIX)
    assert table[1] == [0, 10, 20, 40, 60, 80, 100, 120, 0, 0]
    assert all(len(row) == 10 for row in table.values())


def test_quest_xp_level_10():
    assert quest_xp(10, load_quest_xp(FIX)) == 840


def test_quest_xp_unknown_level_is_zero():
    assert quest_xp(999, load_quest_xp(FIX)) == 0
    assert quest_xp(0, {}) == 0


def test_gain_below_threshold_keeps_level():
    assert XpState(1, 0).gain(399) == XpState(1, 399)


def test_level_up_carries_overflow():
    # 400 to reach 2, 900 to reach 3: 1500 = 400 + 900 + 200 left over.
    assert XpState(1, 0).gain(1500) == XpState(3, 200)
    assert XpState(1, 300).gain(100) == XpState(2, 0)


def test_gain_stops_at_level_cap():
    near = XpState(LEVEL_CAP - 1, PLAYER_XP_TO_LEVEL[LEVEL_CAP - 1] - 1)
    assert near.gain(10**9) == XpState(LEVEL_CAP, 0)
    assert XpState(LEVEL_CAP, 0).gain(500) == XpState(LEVEL_CAP, 0)


def test_xp_state_is_frozen():
    with pytest.raises(AttributeError):
        XpState(1, 0).level = 2


def _step(sid, kind, qid=None, **extra):
    step = {"id": sid, "type": kind, "mapId": 1, "x": 1.0, "y": 1.0, "confidence": "unverified", **extra}
    if qid is not None:
        step["questId"] = qid
    return step


def test_estimate_levels_replays_turnin_xp_and_grind():
    from pipeline.generate.xpsim import estimate_levels

    table = {5: [0, 0, 0, 0, 0, 450, 0, 0, 0, 0], 1: [0, 0, 0, 0, 0, 100, 0, 0, 0, 0]}
    quests = {1: {"level": 5, "minLevel": 1}, 2: {"level": None, "minLevel": 1}}
    route = {"levelRange": [1, 30], "steps": [
        _step("a1", "accept", 1), _step("t1", "turnin", 1), _step("a2", "accept", 2),
        _step("t2", "turnin", 2), _step("g", "grind", untilLevel=6), _step("x", "travel"),
        _step("t9", "turnin", 999),  # unknown quest gives no XP
    ]}
    levels = estimate_levels(route, quests, table)
    # Level is the level *before* the step's XP: 450 XP at t1 -> level 2 with 50 XP; quest 2 uses minLevel 1.
    assert levels == {"a1": 1, "t1": 1, "a2": 2, "t2": 2, "g": 2, "x": 6, "t9": 6}


def test_grind_never_lowers_the_level():
    from pipeline.generate.xpsim import estimate_levels

    route = {"levelRange": [1, 30], "steps": [_step("g1", "grind", untilLevel=8), _step("g2", "grind", untilLevel=4),
                                              _step("end", "travel")]}
    assert estimate_levels(route, {}, {})["end"] == 8
