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
