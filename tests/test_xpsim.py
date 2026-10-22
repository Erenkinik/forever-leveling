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


def test_kill_xp_counts_kill_and_collect_objectives():
    from pipeline.generate.config import KILLS_PER_COLLECT, KILLS_PER_KILL_OBJECTIVE
    from pipeline.generate.xpsim import kill_xp, mob_xp

    assert mob_xp(1) == 50 and mob_xp(10) == 95
    q = {"level": 10, "minLevel": 8, "objectives": {"units": [1, 2], "items": [3], "objects": [4]}}
    assert kill_xp(q) == (2 * KILLS_PER_KILL_OBJECTIVE + KILLS_PER_COLLECT) * mob_xp(10)
    assert kill_xp({"level": None, "minLevel": 4, "objectives": {"units": [], "items": [], "objects": [7]}}) == 0
    assert kill_xp({"level": 3, "minLevel": 1}) == 0


def test_estimate_levels_adds_kill_xp_at_complete_steps():
    from pipeline.generate.xpsim import estimate_levels, kill_xp

    table = {5: [0] * 10}
    quests = {1: {"level": 5, "minLevel": 1, "objectives": {"units": [9], "items": [], "objects": []}}}
    route = {"levelRange": [1, 30], "steps": [
        _step("a1", "accept", 1), _step("c1", "complete", 1), _step("t1", "turnin", 1), _step("end", "travel")]}
    levels = estimate_levels(route, quests, table)
    assert kill_xp(quests[1]) >= 400  # one level's worth at level 1
    assert (levels["c1"], levels["t1"]) == (1, 2)


def test_mob_xp_follows_the_vanilla_level_difference_rules():
    from pipeline.generate.xpsim import gray_level, mob_xp

    assert mob_xp(10, 10) == 95  # 45 + 5 * 10
    assert mob_xp(12, 10) == int(95 * 1.10)  # +5% a level above
    assert mob_xp(20, 10) == int(95 * 1.20)  # at most +4 levels
    assert mob_xp(8, 10) == int(95 * (1 - 2 / 7))  # zero difference 7 at level 10
    assert gray_level(10) == 4 and mob_xp(4, 10) == 0  # gray mobs give nothing
    assert gray_level(5) == 0 and mob_xp(1, 5) > 0
    assert mob_xp(1.5, 1) == mob_xp(2, 1)  # a level range's mean is rounded


def test_quest_xp_drops_when_the_player_is_far_above_the_quest():
    from pipeline.generate.xpsim import quest_xp

    table = {10: [0, 0, 0, 0, 0, 1000]}
    assert quest_xp(10, table, 15) == 1000
    assert quest_xp(10, table, 16) == 800
    assert quest_xp(10, table, 19) == 200
    assert quest_xp(10, table, 25) == 100
    assert quest_xp(10, table) == 1000


def test_kill_xp_uses_objective_counts_drop_chances_and_mob_levels():
    from pipeline.generate.config import MAX_KILLS_PER_OBJECTIVE
    from pipeline.generate.xpsim import kill_xp, mob_xp, objective_kills

    assert objective_kills({"kind": "kill", "count": 10}) == 10
    assert objective_kills({"kind": "collect", "count": 8, "chance": 80.0}) == 10
    assert objective_kills({"kind": "collect", "count": 1, "chance": 0.0}) == 0  # from objects only
    assert objective_kills({"kind": "collect", "count": 5, "chance": 0.5}) == MAX_KILLS_PER_OBJECTIVE
    q = {"level": 4, "minLevel": 2, "kills": [
        {"kind": "kill", "id": 1, "count": 10, "chance": None, "level": 2.0},
        {"kind": "collect", "id": 2, "count": 8, "chance": 80.0, "level": None},  # at the quest's level
    ]}
    assert kill_xp(q, 3) == 10 * mob_xp(2, 3) + 10 * mob_xp(4, 3)
    assert kill_xp({"level": 4, "minLevel": 2, "kills": []}, 3) == 0


def test_estimate_levels_leaves_class_quests_out():
    from pipeline.generate.xpsim import estimate_levels

    table = {5: [0, 0, 0, 0, 0, 450]}
    quests = {1: {"level": 5, "minLevel": 1, "classes": ["Mage"]}, 2: {"level": 5, "minLevel": 1}}
    route = {"levelRange": [1, 30], "steps": [
        _step("t1", "turnin", 1), _step("a", "travel"), _step("t2", "turnin", 2), _step("end", "travel")]}
    levels = estimate_levels(route, quests, table)
    assert (levels["a"], levels["end"]) == (1, 2)
