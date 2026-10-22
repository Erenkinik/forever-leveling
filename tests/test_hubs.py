import json

import pytest

from pipeline.canonical import load_uimaps_canonical
from pipeline.config import DATA_DIR
from pipeline.generate.graph import QuestGraph, Selection, build_graph, select_quests
from pipeline.generate.hubs import build_hubs, unplaced
from pipeline.generate.zone_order import load_zone_order


def _q(qid, x, y, map_id=10, level=1, prereqs=()):
    return {
        "id": qid, "level": level, "minLevel": level, "prereqs": list(prereqs),
        "start": {"uiMapId": map_id, "x": x, "y": y},
    }


def _quests(*qs):
    return {q["id"]: q for q in qs}


def _graph(quests, order=None):
    return QuestGraph(order or sorted(quests), {})


def test_nearby_starts_form_one_hub():
    quests = _quests(_q(1, 10, 10), _q(2, 12, 11), _q(3, 40, 40))
    hubs = build_hubs(quests, _graph(quests), [10])
    assert len(hubs) == 2
    assert hubs[0].quests == [1, 2]
    assert (hubs[0].x, hubs[0].y) == (11.0, 10.5)


def test_single_link_chains_through_intermediate_points():
    quests = _quests(_q(1, 0, 0), _q(2, 5, 0), _q(3, 10, 0))
    assert len(build_hubs(quests, _graph(quests), [10])) == 1


def test_radius_is_inclusive():
    quests = _quests(_q(1, 0, 0), _q(2, 6, 0), _q(3, 20, 0), _q(4, 26.01, 0))
    assert [h.quests for h in build_hubs(quests, _graph(quests), [10])] == [[1, 2], [3], [4]]


def test_hubs_follow_zone_order():
    quests = _quests(_q(1, 10, 10, map_id=20, level=1), _q(2, 10, 10, map_id=10, level=9))
    hubs = build_hubs(quests, _graph(quests), [10, 20])
    assert [h.mapId for h in hubs] == [10, 20]


def test_hubs_sorted_by_avg_level_within_zone():
    quests = _quests(_q(1, 10, 10, level=8), _q(2, 50, 50, level=2), _q(3, 90, 90, level=5))
    hubs = build_hubs(quests, _graph(quests), [10])
    assert [h.quests for h in hubs] == [[2], [3], [1]]
    assert [h.avgLevel for h in hubs] == [2, 5, 8]


def test_close_levels_pick_nearest_to_previous_hub():
    quests = _quests(
        _q(1, 10, 10, level=1), _q(2, 90, 90, level=1.5), _q(3, 20, 20, level=2.0),
    )
    hubs = build_hubs(quests, _graph(quests), [10])
    assert [h.quests for h in hubs] == [[1], [3], [2]]


def test_level_window_is_relative_to_lowest_remaining():
    # After hub 1, lowest remaining is level 1 (hub 2). Hub 3 (level 2.0) is within 1.0 and nearer
    # to hub 1 than hub 2 is. Hub 4 (level 2.5) is outside the window although it is nearest.
    quests = _quests(_q(1, 0, 0, level=1), _q(2, 80, 0, level=1), _q(3, 50, 0, level=2.0), _q(4, 10, 0, level=2.5))
    hubs = build_hubs(quests, _graph(quests), [10])
    assert [h.quests for h in hubs] == [[1], [3], [2], [4]]


def test_prereq_never_after_dependent():
    # Quest 2 (low level hub) needs quest 1 (high level hub): 2 moves to 1's hub.
    quests = _quests(_q(1, 80, 80, level=9), _q(2, 10, 10, level=1, prereqs=[1]))
    graph = build_graph(Selection(quests, {}), "beta")
    hubs = build_hubs(quests, graph, [10])
    assert [h.quests for h in hubs] == [[1, 2]]


def test_prereq_in_later_zone_moves_quest_there():
    quests = _quests(_q(1, 10, 10, map_id=20), _q(2, 10, 10, map_id=10, prereqs=[1]))
    graph = build_graph(Selection(quests, {}), "beta")
    hubs = build_hubs(quests, graph, [10, 20])
    assert [(h.mapId, h.quests) for h in hubs] == [(20, [1, 2])]


def test_moves_repeat_until_stable():
    quests = _quests(
        _q(1, 80, 80, level=9),
        _q(2, 40, 40, level=5, prereqs=[1]),
        _q(3, 10, 10, level=1, prereqs=[2]),
    )
    graph = build_graph(Selection(quests, {}), "beta")
    assert [h.quests for h in build_hubs(quests, graph, [10])] == [[1, 2, 3]]


def test_no_coordinates_not_in_hubs_and_reported_unplaced():
    quests = _quests(_q(1, 10, 10), _q(2, None, None), _q(3, 10, None))
    graph = _graph(quests)
    hubs = build_hubs(quests, graph, [10])
    assert [q for h in hubs for q in h.quests] == [1]
    assert unplaced(quests, graph, [10]) == [2, 3]


def test_gap_quests_with_coordinates_are_placed():
    quests = _quests(_q(1, 10, 10))
    graph = QuestGraph([1], {1: "prereq 5 not in route"})
    assert build_hubs(quests, graph, [10])[0].quests == [1]


def test_hub_order_deterministic():
    quests = _quests(*[_q(i, (i * 37) % 100, (i * 53) % 100, level=1 + i % 3) for i in range(1, 30)])
    graph = _graph(quests)
    a = build_hubs(quests, graph, [10])
    b = build_hubs(dict(reversed(list(quests.items()))), graph, [10])
    assert a == b


def test_ties_fall_back_to_smallest_first_quest_id():
    quests = _quests(_q(5, 50, 0, level=1), _q(3, 0, 50, level=1), _q(9, 0, 0, level=1))
    hubs = build_hubs(quests, _graph(quests, [5, 3, 9]), [10])
    # No previous hub for the first pick, so equal levels fall back to the smallest first-quest id.
    assert hubs[0].quests == [3]
    # Then 9 (distance 50) beats 5 (distance ~70.7) by proximity.
    assert [h.quests for h in hubs] == [[3], [9], [5]]


def test_human_selection_prereqs_precede_dependents():
    quests = {q["id"]: q for q in json.loads((DATA_DIR / "canonical" / "quests.json").read_text(encoding="utf-8"))}
    order = load_zone_order(DATA_DIR / "zone-order" / "human.yaml", load_uimaps_canonical())
    sel = select_quests(quests, order)
    graph = build_graph(sel, "beta")
    hubs = build_hubs(sel.quests, graph, order.zones)
    seq = [q for h in hubs for q in h.quests]
    pos = {q: i for i, q in enumerate(seq)}
    assert len(seq) == len(pos)
    assert set(seq) | set(unplaced(sel.quests, graph, order.zones)) == set(graph.order)
    for q in seq:
        for p in sel.quests[q]["prereqs"]:
            if p in pos:
                assert pos[p] < pos[q]


def test_quest_on_map_outside_zones_is_unplaced():
    quests = _quests(_q(1, 10, 10), _q(2, 10, 10, map_id=99, prereqs=[1]), _q(3, 5, 5, map_id=None))
    graph = _graph(quests)
    hubs = build_hubs(quests, graph, [10])
    placed = [q for h in hubs for q in h.quests]
    assert placed == [1]
    assert unplaced(quests, graph, [10]) == [2, 3]
    assert sorted(placed + unplaced(quests, graph, [10])) == sorted(graph.order)


def test_prereq_outside_zones_does_not_move_quest():
    quests = _quests(_q(1, 10, 10, map_id=99), _q(2, 10, 10, prereqs=[1]))
    hubs = build_hubs(quests, _graph(quests), [10])
    assert [h.quests for h in hubs] == [[2]]


def test_missing_level_and_min_level_raises_value_error_with_id():
    q = _q(7, 10, 10)
    q["level"] = None
    q["minLevel"] = None
    with pytest.raises(ValueError, match="quest 7"):
        build_hubs(_quests(q), _graph(_quests(q)), [10])


def test_pulled_quest_joins_the_hub_of_its_first_dependent():
    quests = _quests(_q(1, 10, 10, prereqs=[3]), _q(2, 80, 80, level=5, prereqs=[3]), _q(3, 50, 50, map_id=99))
    graph = _graph(quests, [3, 1, 2])
    hubs = build_hubs(quests, graph, [10], pulled={3})
    assert [h.quests for h in hubs] == [[3, 1], [2]]
    assert unplaced(quests, graph, [10], pulled={3}) == []
    assert unplaced(quests, graph, [10]) == [3]
