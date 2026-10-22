import pytest

from pipeline.canonical import load_uimaps_canonical
from pipeline.config import DATA_DIR
from pipeline.generate import GenerationError
from pipeline.generate.graph import Selection, build_graph, select_quests
from pipeline.generate.zone_order import ZoneOrder, load_zone_order

HUMAN = DATA_DIR / "zone-order" / "human.yaml"
ORDER = ZoneOrder("t", "Human", "Alliance", False, [10, 20])


def _q(qid, min_level=1, races=None, prereqs=(), map_id=10, in_forever=True, level=None, classes=None,
       factions=None):
    q = {
        "id": qid, "minLevel": min_level, "races": races, "classes": classes, "factions": factions,
        "prereqs": list(prereqs),
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


def test_class_quest_is_kept_when_the_race_can_play_one_of_its_classes():
    # ORDER is a Human route: Humans play Warlocks and Warriors, never Shamans or Druids.
    quests = {
        1: _q(1, classes=["Warlock"]),
        2: _q(2, classes=["Warrior", "unknown-bit-32"]),
        3: _q(3, classes=None),
        4: _q(4, races=["Orc"], classes=["Mage"]),  # race is checked first
        5: _q(5, classes=["Shaman"], map_id=99),  # class is checked before zone
        6: _q(6, classes=["Shaman", "Druid"]),
        7: _q(7, classes=["unknown-bit-32"]),
    }
    sel = select_quests(quests, ORDER)
    assert list(sel.quests) == [1, 2, 3]
    assert sel.excluded == {"class": [5, 6, 7], "race": [4]}


def test_exclusion_reasons_and_precedence():
    quests = {
        1: _q(1, in_forever=False, min_level=None, races=["Orc"], map_id=99),
        2: _q(2, min_level=None, races=["Orc"], map_id=99),
        3: _q(3, min_level=31, races=["Orc"], map_id=99),
        4: _q(4, races=["Orc"], map_id=99),
        5: _q(5, map_id=99),
        6: _q(6, min_level=30),
        7: _q(7, classes=["Shaman"], map_id=99),
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
        12: _q(12, classes=["Druid"], level=28),
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


def test_other_faction_quest_excluded():
    quests = {
        1: _q(1, factions=["Horde"]),
        2: _q(2, factions=["Alliance"]),
        3: _q(3, factions=None),
        4: _q(4, factions=[]),
        5: _q(5, races=["Orc"], factions=["Horde"]),  # race is checked first
        6: _q(6, factions=["Horde"], classes=["Mage"]),  # faction is checked before class
    }
    sel = select_quests(quests, ORDER)
    assert sorted(sel.quests) == [2, 3]
    assert sel.excluded["faction"] == [1, 4, 6]
    assert sel.excluded["race"] == [5]


def _located(q, map_id, x=50.0, y=50.0):
    q["start"] = {"uiMapId": map_id, "x": x, "y": y}
    return q


def test_located_prereq_starting_off_route_is_pulled_in():
    quests = {
        1: _q(1, prereqs=[2]),                        # on route (map 10)
        2: _located(_q(2, map_id=99, prereqs=[3]), 99),  # off route, located: pulled
        3: _located(_q(3, map_id=98), 98),             # prereq of a pulled quest: pulled too
        4: _q(4, prereqs=[5]),
        5: _q(5, map_id=None),                        # start unknown: stays out
        6: _q(6, prereqs=[7]),
        7: _located(_q(7, map_id=99, races=["Orc"]), 99),  # excluded for race: stays out
        8: _located(_q(8, map_id=97), 97),             # off route, nobody needs it: stays out
    }
    sel = select_quests(quests, ORDER)
    assert sel.pulled == {2, 3}
    assert {2, 3} <= set(sel.quests) and not {5, 7, 8} & set(sel.quests)
    assert sel.excluded["zone"] == [5, 8] and sel.excluded["race"] == [7]


def test_drop_pulled_also_drops_pulled_prereqs_nobody_needs_any_more():
    from pipeline.generate.graph import drop_pulled

    quests = {1: _q(1, prereqs=[2]), 2: _located(_q(2, map_id=99, prereqs=[3]), 99), 3: _located(_q(3, map_id=98), 98)}
    sel = select_quests(quests, ORDER)
    assert sel.pulled == {2, 3}
    after = drop_pulled(sel, {2})
    assert after.pulled == set() and sorted(after.quests) == [1]
    assert after.excluded["zone"] == [2, 3]
    assert sel.pulled == {2, 3}  # input untouched


def test_prereq_on_another_continent_or_an_island_is_not_pulled_in():
    quests = {
        1: _q(1, prereqs=[2]), 2: _located(_q(2, map_id=99), 99),    # other continent
        3: _q(3, prereqs=[4]), 4: _located(_q(4, map_id=1438), 1438),  # island
        5: _q(5, prereqs=[6]), 6: _located(_q(6, map_id=97), 97),      # same continent: pulled
    }
    continents = {10: 1415, 20: 1415, 97: 1415, 99: 1414, 1438: 1414}
    sel = select_quests(quests, ORDER, continents)
    assert sel.pulled == {6}


def test_alternative_prereqs_use_the_one_on_the_route():
    # Quest 1 needs 2 or 3 (prereqsAny); 3 is on the route, so 2 (off route, located) is not pulled in.
    quests = {
        1: {**_q(1, prereqs=[2, 3]), "prereqsAny": True},
        2: _located(_q(2, map_id=99), 99),
        3: _q(3),
    }
    sel = select_quests(quests, ORDER)
    assert sel.quests[1]["prereqs"] == [3] and sel.pulled == set()
    assert quests[1]["prereqs"] == [2, 3]  # the canonical record is untouched


def test_alternative_prereqs_pull_one_when_none_is_on_the_route():
    quests = {
        1: {**_q(1, prereqs=[2, 3]), "prereqsAny": True},
        2: _located(_q(2, map_id=99), 99),
        3: _located(_q(3, map_id=98), 98),
    }
    sel = select_quests(quests, ORDER)
    assert sel.quests[1]["prereqs"] == [2] and sel.pulled == {2}


def test_required_prereqs_are_all_kept():
    quests = {1: _q(1, prereqs=[2, 3]), 2: _q(2), 3: _q(3)}
    assert select_quests(quests, ORDER).quests[1]["prereqs"] == [2, 3]


def test_alternative_class_versions_on_the_route_all_stay():
    # "Vile Familiars": one version for every class but Warlock, one for Warlocks; each class does its own.
    quests = {
        1: {**_q(1, prereqs=[2, 3]), "prereqsAny": True},
        2: _q(2, classes=["Warrior", "Rogue", "Priest", "Mage"]),
        3: _q(3, classes=["Warlock"]),
    }
    sel = select_quests(quests, ORDER)
    assert sel.quests[1]["prereqs"] == [2, 3] and {2, 3} <= set(sel.quests)
