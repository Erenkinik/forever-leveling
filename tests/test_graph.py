import pytest

from pipeline.canonical import load_uimaps_canonical
from pipeline.config import DATA_DIR
from pipeline.generate import GenerationError
from pipeline.generate.graph import Selection, build_graph, select_quests
from pipeline.generate.zone_order import ZoneOrder, load_zone_order

HUMAN = DATA_DIR / "zone-order" / "human.yaml"
ORDER = ZoneOrder("t", "Human", "Alliance", False, [10, 20])


def _q(qid, min_level=1, races=None, prereqs=(), map_id=10, in_forever=True, level=None, classes=None):
    q = {
        "id": qid, "minLevel": min_level, "races": races, "classes": classes, "prereqs": list(prereqs),
        "start": {"uiMapId": map_id}, "inForever": in_forever,
    }
    if level is not None:
        q["level"] = level
    return q


def _sel(*quests):
    return Selection({q["id"]: q for q in quests}, {})


def test_selects_human_elwynn_quest_33():
    import json

    quests = {q["id"]: q for q in json.loads((DATA_DIR / "canonical" / "quests.json").read_text(encoding="utf-8"))}
    order = load_zone_order(HUMAN, load_uimaps_canonical())
    sel = select_quests(quests, order)
    assert 33 in sel.quests
    assert sum(len(v) for v in sel.excluded.values()) + len(sel.quests) == len(quests)


def test_race_restricted_quest_excluded():
    quests = {
        1: _q(1, races=["Orc"]),
        2: _q(2, races=["Human", "Dwarf"]),
        3: _q(3, races=["Human", "unknown-bit-9"]),
        4: _q(4, races=None),
    }
    sel = select_quests(quests, ORDER)
    assert sorted(sel.quests) == [2, 4]
    assert sel.excluded["race"] == [1, 3]


def test_class_restricted_quest_excluded():
    quests = {
        1: _q(1, classes=["Warlock"]),
        2: _q(2, classes=["Warrior", "unknown-bit-32"]),
        3: _q(3, classes=None),
        4: _q(4, races=["Orc"], classes=["Mage"]),  # race is checked first
        5: _q(5, classes=["Mage"], map_id=99),  # class is checked before zone
    }
    sel = select_quests(quests, ORDER)
    assert list(sel.quests) == [3]
    assert sel.excluded == {"class": [1, 2, 5], "race": [4]}


def test_exclusion_reasons_and_precedence():
    quests = {
        1: _q(1, in_forever=False, min_level=None, races=["Orc"], map_id=99),
        2: _q(2, min_level=None, races=["Orc"], map_id=99),
        3: _q(3, min_level=31, races=["Orc"], map_id=99),
        4: _q(4, races=["Orc"], map_id=99),
        5: _q(5, map_id=99),
        6: _q(6, min_level=30),
        7: _q(7, classes=["Warlock"], map_id=99),
    }
    sel = select_quests(quests, ORDER)
    assert sel.excluded == {
        "not-in-forever": [1], "level-unknown": [2], "over-cap": [3], "race": [4], "zone": [5], "class": [7],
    }
    assert list(sel.quests) == [6]


def test_level_over_cap_is_excluded_even_with_low_min_level():
    quests = {1: _q(1, min_level=1, level=60), 2: _q(2, min_level=1, level=30)}
    sel = select_quests(quests, ORDER)
    assert sel.excluded == {"over-cap": [1]}
    assert list(sel.quests) == [2]


def test_zone_level_outlier_is_excluded():
    quests = {i: _q(i, level=6) for i in range(1, 6)}
    quests[6] = _q(6, level=28)
    quests[7] = _q(7, level=12)  # median 6 + spread 6: still in
    quests[8] = _q(8, level=None)  # unknown level: ignored by the median, never an outlier
    quests[9] = _q(9, level=28, map_id=20)  # another zone has its own median
    sel = select_quests(quests, ORDER)
    assert sel.excluded == {"zone-outlier": [6]}
    assert sorted(sel.quests) == [1, 2, 3, 4, 5, 7, 8, 9]


def test_zone_outlier_is_the_last_reason_and_counts_sum_to_total():
    quests = {
        1: _q(1, in_forever=False),
        2: _q(2, min_level=None),
        3: _q(3, level=40),
        4: _q(4, races=["Orc"], level=28),
        5: _q(5, map_id=99, level=28),
        6: _q(6, level=28),
        **{i: _q(i, level=5) for i in range(7, 12)},
        12: _q(12, classes=["Mage"], level=28),
    }
    sel = select_quests(quests, ORDER)
    assert list(sel.excluded) == [
        "not-in-forever", "level-unknown", "over-cap", "race", "zone", "class", "zone-outlier",
    ]
    assert sel.excluded["zone-outlier"] == [6]
    assert sum(len(v) for v in sel.excluded.values()) + len(sel.quests) == len(quests)


def test_prereq_outside_route_is_gap_in_beta_error_in_full():
    sel = _sel(_q(1, prereqs=[999]), _q(2, prereqs=[1]))
    g = build_graph(sel, "beta")
    assert g.gaps == {1: "prereq 999 not in route"}
    assert g.order == [1, 2]
    with pytest.raises(GenerationError, match="999"):
        build_graph(sel, "full")


def test_prereq_cycle_raises():
    sel = _sel(_q(1, prereqs=[3]), _q(2, prereqs=[1]), _q(3, prereqs=[2]), _q(4, prereqs=[3]))
    for tier in ("beta", "full"):
        with pytest.raises(GenerationError) as ei:
            build_graph(sel, tier)
        assert "1" in str(ei.value) and "2" in str(ei.value) and "3" in str(ei.value)
        assert "4" not in str(ei.value).replace("tier", "")


def test_topological_order_is_deterministic():
    quests = [_q(5, 3), _q(4, 1, prereqs=[5]), _q(2, 2), _q(3, 1), _q(1, 2, prereqs=[3])]
    expected = [3, 1, 2, 5, 4]
    for perm in (quests, quests[::-1], quests[2:] + quests[:2]):
        assert build_graph(_sel(*perm), "beta").order == expected
