import json
from pathlib import Path

import pytest

from pipeline.canonical import load_spawns_canonical, load_uimaps_canonical
from pipeline.config import DATA_DIR
from pipeline.generate import GenerationError
from pipeline.generate.config import BETA_BLOCKING_RULES, GRIND_TRIGGER, QUEST_LOG_LIMIT
from pipeline.generate.steps import generate_route
from pipeline.generate.zone_order import ZoneOrder
from pipeline.ingest.wago import load_quest_xp
from pipeline.schema import validate as schema_validate
from pipeline.validate.semantic import LEVEL_SLACK as SEMANTIC_LEVEL_SLACK
from pipeline.validate.semantic import check_route

FIX = Path(__file__).parent / "fixtures" / "wago"
XP = load_quest_xp(FIX)
NOW = "2026-10-22T12:00:00Z"
ORDER = ZoneOrder("t", "Human", "Alliance", False, [10, 20])


def _npc(npc_id, x, y, map_id=10):
    return {"type": "npc", "id": npc_id, "name": None, "uiMapId": map_id, "x": x, "y": y}


def _q(qid, x=10.0, y=10.0, map_id=10, level=1, prereqs=(), units=(), items=(), objects=(),
       start=None, end=None, confidence="unverified"):
    start = start or _npc(1000 + qid, x, y, map_id)
    return {
        "id": qid, "name": f"Q{qid}", "level": level, "minLevel": level, "races": None,
        "prereqs": list(prereqs), "start": start, "end": end or dict(start),
        "objectives": {"units": list(units), "items": list(items), "objects": list(objects)},
        "inForever": True, "confidence": confidence,
    }


def _quests(*qs):
    return {q["id"]: q for q in qs}


def _spawns(units=None, objects=None, items=None):
    return {
        "units": {str(k): {"name": None, "points": v} for k, v in (units or {}).items()},
        "objects": {str(k): {"points": v} for k, v in (objects or {}).items()},
        "items": {str(k): {"units": u, "objects": o} for k, (u, o) in (items or {}).items()},
    }


def _gen(quests, spawns=None, tier="beta", order=ORDER, reach_cap=False):
    return generate_route(order, quests, spawns or _spawns(), XP, tier, "1.60.1.70532", NOW, reach_cap=reach_cap)


def _ids(route):
    return [s["id"] for s in route["steps"]]


def _step(route, sid):
    return next(s for s in route["steps"] if s["id"] == sid)


def test_route_header_and_report():
    route, report = _gen(_quests(_q(1)))
    assert schema_validate("route", route) == []
    assert {k: route[k] for k in ("id", "race", "faction", "levelRange", "releaseTier", "reviewed",
                                  "generatedAt", "dataBuild")} == {
        "id": "t", "race": "Human", "faction": "Alliance", "levelRange": [1, 30], "releaseTier": "beta",
        "reviewed": False, "generatedAt": NOW, "dataBuild": "1.60.1.70532",
    }
    assert report["xpIsEstimate"] is True
    assert report["gaps"] == 0
    assert report["stepCounts"]["accept"] == 1 and report["stepCounts"]["turnin"] == 1
    assert report["stepCounts"]["gap"] == 0 and report["stepCounts"]["travel"] == 0
    assert report["questLevel"] == report["estimatedFinalLevel"] == 1


def test_report_counts_excluded_by_reason():
    other_zone = _q(2, map_id=99)
    orc_only = dict(_q(3), races=["Orc"])
    _, report = _gen(_quests(_q(1), other_zone, orc_only))
    assert report["excluded"] == {"zone": 1, "race": 1}


def test_invalid_tier_raises():
    with pytest.raises(GenerationError):
        _gen(_quests(_q(1)), tier="gold")


def test_hub_accepts_then_completes_then_turnins():
    quests = _quests(
        _q(1, 10, 10, units=[100], end=_npc(501, 12, 12)),
        _q(2, 11, 11, objects=[200]),
    )
    spawns = _spawns(units={100: [[10, 20.0, 20.0], [10, 22.0, 24.0]]}, objects={200: [[10, 30.0, 30.0]]})
    route, _ = _gen(quests, spawns)
    assert [s["type"] for s in route["steps"]] == ["accept", "accept", "complete", "complete", "turnin", "turnin"]
    accept1 = _step(route, "accept-1")
    assert (accept1["npcId"], accept1["mapId"], accept1["x"], accept1["y"]) == (1001, 10, 10, 10)
    complete1 = _step(route, "complete-1")
    assert (complete1["questId"], complete1["mapId"], complete1["x"], complete1["y"]) == (1, 10, 21.0, 22.0)
    turnin1 = _step(route, "turnin-1")
    assert (turnin1["npcId"], turnin1["x"], turnin1["y"]) == (501, 12, 12)
    assert accept1["confidence"] == "unverified"


def test_quest_without_objectives_gets_no_complete():
    route, _ = _gen(_quests(_q(1)))
    assert _ids(route) == ["accept-1", "turnin-1"]


def test_completes_follow_nearest_neighbour():
    quests = _quests(
        _q(1, 10, 10, units=[100]), _q(2, 11, 11, units=[101]), _q(3, 12, 12, units=[102]),
    )
    spawns = _spawns(units={100: [[10, 90.0, 90.0]], 101: [[10, 50.0, 50.0]], 102: [[10, 15.0, 15.0]]})
    route, _ = _gen(quests, spawns)
    assert [s["id"] for s in route["steps"] if s["type"] == "complete"] == ["complete-3", "complete-2", "complete-1"]


def test_complete_location_uses_start_map_points_else_busiest_map():
    quests = _quests(_q(1, units=[100, 101]), _q(2, 11, 11, units=[102]))
    spawns = _spawns(units={
        100: [[10, 40.0, 40.0], [30, 1.0, 1.0]],
        101: [[10, 60.0, 60.0]],
        102: [[30, 5.0, 5.0], [40, 1.0, 1.0], [40, 3.0, 3.0]],
    })
    wide = ZoneOrder("t", "Human", "Alliance", False, [10, 20, 30, 40])  # every map is on the route
    route, _ = _gen(quests, spawns, order=wide)
    c1, c2 = _step(route, "complete-1"), _step(route, "complete-2")
    assert (c1["mapId"], c1["x"], c1["y"]) == (10, 50.0, 50.0)
    assert (c2["mapId"], c2["x"], c2["y"]) == (40, 2.0, 2.0)


def test_complete_location_ignores_off_route_maps():
    # Map 99 has the most points but is not a route zone nor the quest's start/end map.
    quests = _quests(_q(1, units=[100]))
    spawns = _spawns(units={100: [[20, 5.0, 5.0], [99, 1.0, 1.0], [99, 3.0, 3.0], [99, 5.0, 5.0]]})
    route, _ = _gen(quests, spawns)
    c = _step(route, "complete-1")
    assert (c["mapId"], c["x"], c["y"]) == (20, 5.0, 5.0)


def test_complete_location_may_use_the_end_map_off_route():
    quests = _quests(_q(1, units=[100], end=_npc(9, 50, 50, map_id=77)))
    spawns = _spawns(units={100: [[77, 40.0, 40.0], [99, 1.0, 1.0], [99, 3.0, 3.0]]})
    route, _ = _gen(quests, spawns)
    c = _step(route, "complete-1")
    assert (c["mapId"], c["x"], c["y"]) == (77, 40.0, 40.0)


def test_objective_located_only_off_route_becomes_gap():
    quests = _quests(_q(1), _q(2, 11, 11, units=[100], items=[300]))
    spawns = _spawns(units={100: [[99, 1.0, 1.0]], 101: [[98, 2.0, 2.0]]}, items={300: ([101], [])})
    route, report = _gen(quests, spawns)
    gap = _step(route, "gap-2")
    assert gap["reason"] == "quest 2: objective located only off-route"
    assert not {"accept-2", "complete-2", "turnin-2"} & set(_ids(route))
    assert report["gaps"] == 1


def test_quest_without_start_coords_becomes_gap():
    no_coords = _q(2, start={"type": "npc", "id": 1002, "name": None, "uiMapId": 10, "x": None, "y": None},
                   end=_npc(1002, 11, 11))
    route, report = _gen(_quests(_q(1), no_coords))
    gap = _step(route, "gap-2")
    assert "start location unknown" in gap["reason"] and "2" in gap["reason"]
    assert gap["questId"] == 2 and gap["confidence"] == "unverified"
    assert not {"accept-2", "complete-2", "turnin-2"} & set(_ids(route))
    assert report["gaps"] == 1
    with pytest.raises(GenerationError):
        _gen(_quests(_q(1), no_coords), tier="full")


def test_gap_location_is_last_step_in_zone():
    # The start-less quest joins the level-3 hub; its gap sits at the last step on that map
    # (turnin-1 at 30,40), not at the hub centre (90,90).
    no_coords = _q(2, level=3,
                   start={"type": "npc", "id": 1002, "name": None, "uiMapId": 10, "x": None, "y": None})
    route, _ = _gen(_quests(_q(1, 30, 40), no_coords, _q(3, 90, 90, level=3)))
    gap = _step(route, "gap-2")
    assert _ids(route).index("gap-2") == _ids(route).index("turnin-1") + 1
    assert (gap["mapId"], gap["x"], gap["y"]) == (10, 30, 40)


def test_gap_location_falls_back_to_hub_centre():
    no_coords = _q(2, map_id=20, start={"type": "npc", "id": 1002, "name": None, "uiMapId": 20, "x": None, "y": None})
    route, _ = _gen(_quests(_q(1, 30, 40), no_coords, _q(3, 60, 70, map_id=20)))
    gap = _step(route, "gap-2")
    assert (gap["mapId"], gap["x"], gap["y"]) == (20, 60, 70)
    assert _ids(route) == ["accept-1", "turnin-1", "travel-10-20", "gap-2", "accept-3", "turnin-3"]


@pytest.mark.parametrize("objectives,spawns", [
    ({"units": [100]}, _spawns()),                                    # unit absent
    ({"units": [100]}, _spawns(units={100: []})),                     # unit with empty points
    ({"objects": [200]}, _spawns(objects={200: []})),                 # object with empty points
    ({"items": [300]}, _spawns()),                                    # item absent
    ({"items": [300]}, _spawns(items={300: ([], [])})),               # item with no sources
    ({"items": [300]}, _spawns(units={100: []}, items={300: ([100], [])})),  # dropper not located
])
def test_objective_without_location_becomes_gap(objectives, spawns):
    quests = _quests(_q(1), _q(2, 11, 11, **objectives))
    route, _ = _gen(quests, spawns)
    gap = _step(route, "gap-2")
    assert "location unknown" in gap["reason"] and "2" in gap["reason"]
    assert not {"accept-2", "complete-2", "turnin-2"} & set(_ids(route))
    assert schema_validate("route", route) == []


def test_item_objective_located_through_its_droppers():
    quests = _quests(_q(1, items=[300]))
    spawns = _spawns(units={100: [[10, 20.0, 20.0]]}, objects={200: [[10, 40.0, 40.0]]},
                     items={300: ([100], [200])})
    route, _ = _gen(quests, spawns)
    c = _step(route, "complete-1")
    assert (c["x"], c["y"]) == (30.0, 30.0)


@pytest.mark.parametrize("start,end,phrase", [
    ({"type": "object", "id": 7, "name": None, "uiMapId": 10, "x": 11, "y": 11}, None, "start"),
    ({"type": "item", "id": 7, "name": None, "uiMapId": 10, "x": 11, "y": 11}, None, "start"),
    (None, {"type": "object", "id": 7, "name": None, "uiMapId": 10, "x": 11, "y": 11}, "end"),
    (None, {"type": None, "id": None, "name": None, "uiMapId": None, "x": None, "y": None}, "end"),
    (None, {"type": "npc", "id": 7, "name": None, "uiMapId": None, "x": None, "y": None}, "end"),
])
def test_non_npc_or_unlocated_start_or_end_becomes_gap(start, end, phrase):
    route, _ = _gen(_quests(_q(1), _q(2, 11, 11, start=start, end=end)))
    gap = _step(route, "gap-2")
    assert phrase in gap["reason"] and "2" in gap["reason"]
    assert not {"accept-2", "turnin-2"} & set(_ids(route))


def test_dependents_of_gap_quest_become_gap():
    root = _q(1, start={"type": "npc", "id": 1001, "name": None, "uiMapId": 10, "x": None, "y": None})
    quests = _quests(root, _q(2, prereqs=[1]), _q(3, prereqs=[2]), _q(4))
    route, report = _gen(quests)
    assert "prereq 1 is a gap" in _step(route, "gap-2")["reason"]
    assert "prereq 2 is a gap" in _step(route, "gap-3")["reason"]
    assert [s["id"] for s in route["steps"] if s.get("questId") in (1, 2, 3)] == ["gap-1", "gap-2", "gap-3"]
    assert report["gaps"] == 3


def test_prereq_outside_route_is_gap_with_missing_id():
    route, _ = _gen(_quests(_q(1, prereqs=[777]), _q(2, prereqs=[1])))
    assert "777" in _step(route, "gap-1")["reason"]
    assert "prereq 1 is a gap" in _step(route, "gap-2")["reason"]


def test_zone_change_emits_travel():
    quests = _quests(_q(1, 10, 10, map_id=10), _q(2, 70, 80, map_id=20))
    route, _ = _gen(quests)
    assert _ids(route) == ["accept-1", "turnin-1", "travel-10-20", "accept-2", "turnin-2"]
    travel = _step(route, "travel-10-20")
    assert travel == {"id": "travel-10-20", "type": "travel", "mapId": 20, "x": 70, "y": 80,
                      "mode": "walk", "radius": 5, "confidence": "unverified"}


def test_off_map_turnin_of_a_needed_quest_happens_at_once():
    # Quest 3 needs quest 1, so quest 1 is turned in on map 20 before the route goes on.
    quests = _quests(_q(1, 10, 10, end=_npc(9, 50, 50, map_id=20)), _q(2, 90, 90, level=2),
                     _q(3, 92, 92, level=3, prereqs=[1]))
    route, _ = _gen(quests)
    assert _ids(route)[:5] == ["accept-1", "travel-10-20", "turnin-1", "travel-20-10", "accept-2"]


def test_off_map_turnin_of_a_leaf_quest_waits_until_the_zone_is_left():
    quests = _quests(_q(1, 10, 10, end=_npc(9, 50, 50, map_id=99)), _q(2, 90, 90, level=2),
                     _q(3, 10, 10, map_id=20, level=3))
    route, report = _gen(quests)
    assert _ids(route) == ["accept-1", "accept-2", "turnin-2", "travel-10-99", "turnin-1", "travel-99-20",
                           "accept-3", "turnin-3"]
    assert report["stepCounts"]["travel"] == 2


def test_deferred_turnin_is_done_when_the_route_reaches_that_map_anyway():
    # Quest 1 ends in zone 20, which the route visits next: no extra trip before leaving zone 10.
    quests = _quests(_q(1, 10, 10, end=_npc(9, 50, 50, map_id=20)), _q(2, 10, 10, map_id=20, level=2))
    route, _ = _gen(quests)
    assert _ids(route) == ["accept-1", "travel-10-20", "turnin-1", "accept-2", "turnin-2"]


def test_grind_inserted_when_underleveled():
    # The level-8 chunk needs minLevel 8 - GRIND_TRIGGER = 6; the grind sits at its first quest's start.
    quests = _quests(_q(1, 10, 10, level=1), _q(2, 80, 80, level=8), _q(3, 82, 82, level=8))
    route, report = _gen(quests)
    assert _ids(route)[:4] == ["accept-1", "turnin-1", "grind-10-6", "accept-2"]
    grind = _step(route, "grind-10-6")
    assert (grind["untilLevel"], grind["mapId"], grind["x"], grind["y"]) == (6, 10, 80, 80)
    assert grind["confidence"] == "unverified"
    # After the grind the state is (6, 0); two level-8 quests give 2 * 700 XP, below the 3600 needed.
    assert report["questLevel"] == 6


def test_no_grind_when_level_is_close():
    quests = _quests(_q(1, 10, 10, level=1), _q(2, 80, 80, level=3))
    route, _ = _gen(quests)
    assert not any(s["type"] == "grind" for s in route["steps"])


def test_quest_log_limit_splits_hub():
    n = QUEST_LOG_LIMIT + 5
    quests = _quests(*(_q(i, 10, 10) for i in range(1, n + 1)))
    route, _ = _gen(quests)
    types = [s["type"] for s in route["steps"]]
    limit = QUEST_LOG_LIMIT
    assert types == ["accept"] * limit + ["turnin"] * limit + ["accept"] * 5 + ["turnin"] * 5
    open_quests = peak = 0
    for t in types:
        open_quests += {"accept": 1, "turnin": -1}[t]
        peak = max(peak, open_quests)
    assert peak == QUEST_LOG_LIMIT


def test_prereq_in_same_hub_is_turned_in_before_dependent_accept():
    quests = _quests(_q(1, 10, 10), _q(2, 11, 11, prereqs=[1]), _q(3, 12, 12))
    route, _ = _gen(quests)
    assert _ids(route) == ["accept-1", "accept-3", "turnin-1", "turnin-3", "accept-2", "turnin-2"]


def test_step_ids_are_stable():
    def quests(extra):
        qs = [
            _q(1, 10, 10, end=_npc(9, 50, 50, map_id=20)),
            _q(2, 90, 90, level=2, end=_npc(9, 50, 50, map_id=20)),
            _q(4, 30, 90, level=4, prereqs=[1, 2]),  # needs both, so their turn-ins are not deferred
        ]
        return _quests(*qs, *extra)

    route, _ = _gen(quests([]))
    assert _ids(route)[:7] == [
        "accept-1", "travel-10-20", "turnin-1", "travel-20-10", "accept-2", "travel-10-20-2", "turnin-2",
    ]
    assert route == _gen(quests([]))[0]
    # A quest in an unrelated later hub does not renumber the existing steps.
    bigger, _ = _gen(quests([_q(3, 60, 60, map_id=20, level=3)]))
    assert _ids(bigger)[:7] == _ids(route)[:7]


def test_step_confidence_follows_quest():
    route, _ = _gen(_quests(_q(1, units=[100], confidence="cross-checked")),
                    _spawns(units={100: [[10, 5.0, 5.0]]}))
    assert {s["confidence"] for s in route["steps"]} == {"cross-checked"}


def test_full_tier_without_gaps_generates():
    route, report = _gen(_quests(_q(1)), tier="full")
    assert route["releaseTier"] == "full" and report["gaps"] == 0


def test_generated_elwynn_route_passes_beta_blocking_rules():
    quests = {q["id"]: q for q in json.loads((DATA_DIR / "canonical" / "quests.json").read_text(encoding="utf-8"))}
    uimaps = load_uimaps_canonical()
    elwynn = next(i for i, n in uimaps.items() if n == "Elwynn Forest")
    order = ZoneOrder("human", "Human", "Alliance", False, [elwynn])
    route, report = generate_route(order, quests, load_spawns_canonical(), XP, "beta", "1.60.1.70532", NOW)
    assert report["stepCounts"]["accept"] > 20
    issues = check_route(route, quests, frozenset(uimaps))
    blocking = [i for i in issues if i.rule in BETA_BLOCKING_RULES]
    assert blocking == []


def test_min_level_gate_grinds_before_chunk_with_high_quest():
    # One chunk; the minLevel-6 quest needs 6 - GRIND_TRIGGER = 4 before the chunk is accepted.
    quests = _quests(_q(1, 10, 10), _q(2, 11, 11), _q(3, 12, 12), _q(4, 13, 13, level=6))
    route, report = _gen(quests)
    assert GRIND_TRIGGER == 2 and GRIND_TRIGGER < SEMANTIC_LEVEL_SLACK  # stricter than the validator
    assert _ids(route)[:2] == ["grind-10-4", "accept-1"]
    grind = _step(route, "grind-10-4")
    assert (grind["untilLevel"], grind["mapId"], grind["x"], grind["y"]) == (4, 10, 10.0, 10.0)
    assert grind["confidence"] == "unverified"
    over = [i for i in check_route(route, quests, frozenset({10, 20})) if i.rule == "over-level"]
    assert over == []


def test_min_level_gate_does_not_grind_when_close_enough():
    quests = _quests(_q(1, 10, 10), _q(2, 11, 11, level=3))
    route, _ = _gen(quests)
    assert not any(s["type"] == "grind" for s in route["steps"])


def test_hub_with_high_avg_level_but_low_min_levels_gets_no_grind():
    # Quest level 10 (hub avgLevel 10) but minLevel 1: only minLevel decides a grind.
    quests = _quests(*(dict(_q(i, 10 + i, 10, level=10), minLevel=1) for i in range(1, 4)))
    route, report = _gen(quests)
    assert not any(s["type"] == "grind" for s in route["steps"])
    assert route["steps"][0]["id"] == "accept-1"


def test_report_lists_ids_for_class_and_zone_outlier_only():
    quests = _quests(*(_q(i, level=5) for i in range(1, 6)), _q(6, level=28),
                     dict(_q(8), classes=["Mage"]), dict(_q(7), classes=["Rogue"]), _q(9, map_id=99))
    _, report = _gen(quests)
    assert report["excluded"] == {"class": 2, "zone": 1, "zone-outlier": 1}
    assert report["excludedIds"] == {"class": [7, 8], "zone-outlier": [6]}


def test_estimate_levels_matches_generator_on_real_route():
    from pipeline.generate.xpsim import estimate_levels

    quests = {q["id"]: q for q in json.loads((DATA_DIR / "canonical" / "quests.json").read_text(encoding="utf-8"))}
    uimaps = load_uimaps_canonical()
    zones = [i for i, n in uimaps.items() if n in ("Elwynn Forest", "Westfall")]
    order = ZoneOrder("human", "Human", "Alliance", False, zones)
    from pipeline.canonical import load_questxp_canonical

    xp = load_questxp_canonical()
    route, report = generate_route(order, quests, load_spawns_canonical(), xp, "beta", "1.60.1.70532", NOW)
    levels = estimate_levels(route, quests, xp)
    assert set(levels) == {s["id"] for s in route["steps"]}
    assert all(levels[s["id"]] < s["untilLevel"] for s in route["steps"] if s["type"] == "grind")
    issues = check_route(route, quests, frozenset(uimaps), levels=levels)
    assert [i for i in issues if i.rule == "over-level"] == []
    final = estimate_levels({**route, "steps": route["steps"] + [
        {"id": "end", "type": "travel", "mapId": zones[0], "x": 1.0, "y": 1.0, "confidence": "unverified"}]},
        quests, xp)["end"]
    assert final == report["estimatedFinalLevel"] == 30


def test_route_ends_with_grind_to_cap_when_quests_fall_short():
    route, report = _gen(_quests(_q(1, 10, 10), _q(2, 30, 40)), reach_cap=True)
    last = route["steps"][-1]
    assert last["id"] == "grind-10-30" and last["type"] == "grind" and last["untilLevel"] == 30
    assert (last["mapId"], last["x"], last["y"]) == (10, 30, 40)  # where the route ended
    assert report["questLevel"] == 1 and report["estimatedFinalLevel"] == 30
    assert report["stepCounts"]["grind"] == 1


def test_no_final_grind_when_quests_reach_cap():
    rich = {1: [10 ** 7] * 10}
    route, report = generate_route(ORDER, _quests(_q(1)), _spawns(), rich, "beta", "1.60.1.70532", NOW)
    assert not any(s["type"] == "grind" for s in route["steps"])
    assert report["questLevel"] == report["estimatedFinalLevel"] == 30


def test_off_route_prereq_is_done_before_its_dependent():
    quests = _quests(_q(1, 10, 10, prereqs=[2]), _q(2, 40, 40, map_id=99))
    route, report = _gen(quests)
    ids = _ids(route)
    assert ids == ["accept-2", "turnin-2", "travel-99-10", "accept-1", "turnin-1"]
    assert report["pulledIn"] == [2]
    assert report["gaps"] == 0


def test_pulled_prereq_that_is_itself_a_gap_is_dropped_again():
    # Quest 2 starts off route but its objective has no known location: pulling it in buys nothing.
    quests = _quests(_q(1, 10, 10, prereqs=[2]), _q(2, 40, 40, map_id=99, units=[555]))
    route, report = _gen(quests)
    assert [s["id"] for s in route["steps"]] == ["gap-1"]
    assert _step(route, "gap-1")["reason"] == "quest 1: prereq 2 not in route"
    assert report["pulledIn"] == []


def test_travel_across_continents_is_a_boat_or_zeppelin():
    quests = _quests(_q(1, 10, 10), _q(2, 20, 20, map_id=20, level=2))
    continents = {10: 1415, 20: 1414}
    route, _ = generate_route(ORDER, quests, _spawns(), XP, "beta", "1.60.1.70532", NOW, reach_cap=False,
                              continents=continents)
    assert _step(route, "travel-10-20")["mode"] == "boat"
    horde = ZoneOrder("t", "Orc", "Horde", False, [10, 20])
    route, _ = generate_route(horde, quests, _spawns(), XP, "beta", "1.60.1.70532", NOW, reach_cap=False,
                              continents=continents)
    assert _step(route, "travel-10-20")["mode"] == "zeppelin"
    route, _ = generate_route(ORDER, quests, _spawns(), XP, "beta", "1.60.1.70532", NOW, reach_cap=False,
                              continents={10: 1415, 20: 1415})
    assert _step(route, "travel-10-20")["mode"] == "walk"


def test_travel_to_or_from_teldrassil_is_a_boat():
    order = ZoneOrder("t", "Night Elf", "Alliance", False, [1438, 20])
    quests = _quests(_q(1, 10, 10, map_id=1438), _q(2, 20, 20, map_id=20, level=2))
    route, _ = generate_route(order, quests, _spawns(), XP, "beta", "1.60.1.70532", NOW, reach_cap=False,
                              continents={1438: 1414, 20: 1414})
    assert _step(route, "travel-1438-20")["mode"] == "boat"


def test_complete_location_stays_on_the_quest_continent():
    # Map 20 (another continent) has more points, but the quest starts on map 10's continent.
    quests = _quests(_q(1, units=[100], end=_npc(9, 50, 50, map_id=30)))
    spawns = _spawns(units={100: [[20, 1.0, 1.0], [20, 3.0, 3.0], [40, 5.0, 5.0]]})
    wide = ZoneOrder("t", "Human", "Alliance", False, [10, 20, 40])
    route, _ = generate_route(wide, quests, spawns, XP, "beta", "1.60.1.70532", NOW, reach_cap=False,
                              continents={10: 1415, 30: 1415, 40: 1415, 20: 1414})
    c = _step(route, "complete-1")
    assert (c["mapId"], c["x"], c["y"]) == (40, 5.0, 5.0)
    # Only points on the other continent: a gap, not an ocean crossing.
    spawns = _spawns(units={100: [[20, 1.0, 1.0]]})
    route, _ = generate_route(wide, quests, spawns, XP, "beta", "1.60.1.70532", NOW, reach_cap=False,
                              continents={10: 1415, 30: 1415, 40: 1415, 20: 1414})
    assert _step(route, "gap-1")["reason"] == "quest 1: objective located only off-route"


def test_pulled_prereq_whose_dependents_are_all_gaps_is_dropped():
    # Quest 1 needs 2 (pulled from map 99) and 3, which is not on the route: 1 stays a gap, so the detour
    # to quest 2 buys nothing.
    quests = _quests(_q(1, 10, 10, prereqs=[2, 3]), _q(2, 40, 40, map_id=99), _q(3, 5, 5, map_id=98))
    quests[3]["start"]["uiMapId"] = None  # 3 cannot be pulled: start unknown
    route, report = _gen(quests)
    assert [s["id"] for s in route["steps"]] == ["gap-1"]
    assert report["pulledIn"] == []


def test_objective_of_an_island_quest_stays_on_the_island():
    order = ZoneOrder("t", "Night Elf", "Alliance", False, [1438, 20])
    quests = _quests(_q(1, 10, 10, map_id=1438, units=[100]))
    # The objective is only on map 20, across the water: a gap, not two boat trips.
    spawns = _spawns(units={100: [[20, 1.0, 1.0], [20, 3.0, 3.0]]})
    route, _ = generate_route(order, quests, spawns, XP, "beta", "1.60.1.70532", NOW, reach_cap=False,
                              continents={1438: 1414, 20: 1414})
    assert _step(route, "gap-1")["reason"] == "quest 1: objective located only off-route"
