from pipeline.config import DATA_BUILD
from pipeline.ingest.pfquest import PfData
from pipeline.normalize.quests import build_canonical, confidence_for, races_from_mask
from pipeline.schema import validate

Z = {12: 1429}


def _pf(quests=None, units=None, objects=None):
    return PfData(quests=quests or {}, units=units or {}, objects=objects or {})


def _unit(name, *coords):
    return {"coords": list(coords), "fac": "A", "name": name}


def _one(pf, forever=frozenset(), zones=Z, manual=None, qid=1):
    out = build_canonical(pf, frozenset(forever), zones, manual or {})
    return {r["id"]: r for r in out}[qid]


def test_confidence_rules():
    assert confidence_for({"blizzard-client", "vanilla-emu"}, []) == "cross-checked"
    assert confidence_for({"vanilla-emu"}, []) == "unverified"
    assert confidence_for({"community", "wowhead"}, []) == "unverified"
    assert confidence_for({"blizzard-client", "vanilla-emu"}, ["level"]) == "unverified"
    assert confidence_for({"vanilla-emu", "ingame"}, []) == "verified-ingame"


def test_races_from_mask():
    assert races_from_mask(77) == ["Human", "Dwarf", "Night Elf", "Gnome"]
    assert races_from_mask(255) is None
    assert races_from_mask(None) is None
    assert races_from_mask(0) is None


def test_unknown_race_bit_kept():
    assert "unknown-bit-256" in races_from_mask(1 | 256)


def test_wolves_across_the_border_canonical():
    # Mirrors the real pfQuest record for quest 33 / unit 196 (raw/pfquest).
    pf = _pf(
        {33: {"end": {"U": [196]}, "lvl": 2, "min": 1, "obj": {"I": [750]}, "pre": [5261],
              "start": {"U": [196]}, "name": "Wolves Across the Border"}},
        {196: _unit("Eagan Peltskinner", (48.9, 40.2, 12))},
    )
    q = _one(pf, {33}, qid=33)
    assert q["start"]["type"] == "npc" and q["start"]["id"] == 196 and q["start"]["uiMapId"] == 1429
    assert q["start"]["name"] == "Eagan Peltskinner" and (q["start"]["x"], q["start"]["y"]) == (48.9, 40.2)
    assert q["confidence"] == "unverified"  # DB2 only confirms existence; pfQuest is the sole value source
    assert q["prereqs"] == [5261]
    assert q["inForever"] is True and q["sources"] == ["wago-db2", "pfquest"]
    assert q["objectives"] == {"units": [], "items": [750], "objects": []}
    assert q["seenInBuild"] == DATA_BUILD


def test_quest_started_by_item():
    pf = _pf({1: {"lvl": 4, "min": 1, "start": {"I": [6497]}, "end": {"U": [5]}, "name": "Q"}},
             {5: _unit("N", (1.0, 2.0, 12))})
    q = _one(pf, {1})
    assert q["start"] == {"type": "item", "id": 6497, "name": None, "uiMapId": None, "x": None, "y": None}
    assert q["end"]["type"] == "npc"


def test_quest_started_by_object():
    pf = _pf({1: {"start": {"O": [77]}, "name": "Q"}}, objects={77: {"coords": [(1.0, 2.0, 12)], "fac": None}})
    q = _one(pf)
    assert q["start"]["type"] == "object" and q["start"]["id"] == 77 and q["start"]["x"] is None
    assert validate("quest", q) == []


def test_npc_without_coords_marks_conflict():
    pf = _pf({1: {"start": {"U": [5]}, "end": {"U": [6]}, "name": "Q"}},
             {5: _unit("NoCoords"), 6: _unit("E", (1.0, 2.0, 12))})
    q = _one(pf, {1})
    assert q["start"]["type"] == "npc" and q["start"]["id"] == 5
    assert q["start"]["x"] is None and q["start"]["y"] is None and q["start"]["uiMapId"] is None
    assert "start.coords" in q["conflicts"] and "end.coords" not in q["conflicts"]
    assert q["confidence"] == "unverified"


def test_npc_missing_from_units_marks_conflict():
    q = _one(_pf({1: {"start": {"U": [999]}, "name": "Q"}}))
    assert q["start"]["id"] == 999 and "start.coords" in q["conflicts"]


def test_coord_prefers_zone_of_other_end():
    pf = _pf({1: {"start": {"U": [5]}, "end": {"U": [6]}, "name": "Q"}},
             {5: _unit("S", (1.0, 1.0, 99), (2.0, 2.0, 12)), 6: _unit("E", (3.0, 3.0, 12))})
    q = _one(pf, zones={12: 1429, 99: 1})
    assert (q["start"]["x"], q["start"]["uiMapId"]) == (2.0, 1429)


def test_coord_falls_back_to_first_when_no_shared_zone():
    pf = _pf({1: {"start": {"U": [5]}, "end": {"U": [6]}, "name": "Q"}},
             {5: _unit("S", (1.0, 1.0, 99), (2.0, 2.0, 12)), 6: _unit("E", (3.0, 3.0, 40))})
    q = _one(pf, zones={12: 1429, 99: 1, 40: 3})
    assert (q["start"]["x"], q["start"]["uiMapId"]) == (1.0, 1)


def test_unmapped_zone_marks_conflict():
    pf = _pf({1: {"start": {"U": [5]}, "name": "Q"}}, {5: _unit("S", (1.0, 1.0, 777))})
    q = _one(pf)
    assert q["start"]["uiMapId"] is None and "start.coords" in q["conflicts"]
    assert q["start"]["x"] is None and q["start"]["y"] is None


def test_quest_missing_from_forever_flagged():
    pf = _pf({1: {"lvl": 3, "min": 1, "name": "Q"}})
    q = _one(pf, forever={2})
    assert q["inForever"] is False and q["sources"] == ["pfquest"]
    assert q["confidence"] == "unverified" and q["seenInBuild"] is None


def test_forever_only_quest_kept():
    out = build_canonical(_pf(), frozenset({55}), Z, {})
    assert [r["id"] for r in out] == [55]
    r = out[0]
    assert r["inForever"] is True and r["sources"] == ["wago-db2"] and r["name"] is None
    assert validate("quest", r) == []


def _manual(**over):
    m = {"id": 1, "name": "Manual Name", "level": 5, "minLevel": 3, "wowheadUrl": "u",
         "checkedOn": "2026-10-22", "source": "wowhead-manual"}
    m.update(over)
    return m


def test_manual_overrides_pfquest_and_records_conflict():
    pf = _pf({1: {"lvl": 4, "min": 3, "name": "Pf Name"}})
    q = _one(pf, {1}, manual={1: _manual()})
    assert q["name"] == "Manual Name" and q["level"] == 5 and q["minLevel"] == 3
    assert q["conflicts"] == ["level", "name"]
    assert q["sources"] == ["wago-db2", "pfquest", "wowhead-manual"]
    assert q["confidence"] == "unverified"
    assert "wowheadUrl" not in q and "checkedOn" not in q
    assert validate("quest", q) == []


def test_manual_agreeing_with_pfquest_has_no_conflict():
    pf = _pf({1: {"lvl": 5, "min": 3, "name": "Manual Name"}})
    q = _one(pf, {1}, manual={1: _manual()})
    assert q["conflicts"] == [] and q["confidence"] == "unverified"  # manual is capped


def test_manual_only_quest_with_points_and_races():
    m = _manual(id=9, races=["Human"], prereqs=[2],
                start={"type": "npc", "id": 4, "name": "S", "uiMapId": 1429, "x": 1.5, "y": 2.5})
    q = _one(_pf(), manual={9: m}, qid=9)
    assert q["sources"] == ["wowhead-manual"] and q["races"] == ["Human"] and q["prereqs"] == [2]
    assert q["start"]["uiMapId"] == 1429 and q["end"]["type"] is None
    assert validate("quest", q) == []


def test_output_sorted_by_id_and_all_valid():
    pf = _pf({5: {"name": "b"}, 2: {"name": "a", "race": 77, "lvl": 1, "min": 1}})
    out = build_canonical(pf, frozenset({9}), Z, {})
    assert [r["id"] for r in out] == [2, 5, 9]


def test_manual_in_db2_without_pfquest_is_unverified():
    q = _one(_pf(), {1}, manual={1: _manual()})
    assert q["sources"] == ["wago-db2", "wowhead-manual"] and q["conflicts"] == []
    assert q["confidence"] == "unverified"


def test_multiple_start_ids_and_types_flagged():
    pf = _pf({1: {"start": {"U": [5, 6]}, "end": {"U": [5], "O": [9]}, "name": "Q"}},
             {5: _unit("S", (1.0, 1.0, 12))})
    q = _one(pf, {1})
    assert q["start"]["id"] == 5 and q["end"]["type"] == "npc"
    assert "start.multiple" in q["conflicts"] and "end.multiple" in q["conflicts"]
    dup = _one(_pf({1: {"start": {"U": [5, 5]}, "name": "Q"}}, {5: _unit("S", (1.0, 1.0, 12))}), {1})
    assert "start.multiple" not in dup["conflicts"]


def test_partial_manual_endpoint_merges_over_pfquest():
    pf = _pf({1: {"start": {"U": [5]}, "name": "Q"}}, {5: _unit("S", (1.0, 2.0, 777))})
    q = _one(pf, {1}, manual={1: _manual(start={"type": "npc", "id": 5})})
    assert q["start"]["name"] == "S" and "start" not in q["conflicts"]
    assert "start.coords" in q["conflicts"]
    q = _one(pf, {1}, manual={1: _manual(start={"x": 3.0, "y": 4.0, "uiMapId": 1429})})
    assert q["start"] == {"type": "npc", "id": 5, "name": "S", "uiMapId": 1429, "x": 3.0, "y": 4.0}
    assert "start.coords" not in q["conflicts"]
    assert validate("quest", q) == []


def test_manual_prereq_order_is_not_a_conflict():
    pf = _pf({1: {"lvl": 5, "min": 3, "name": "Manual Name", "pre": [2, 3]}})
    q = _one(pf, manual={1: _manual(prereqs=[3, 2])})
    assert "prereqs" not in q["conflicts"]


def test_db2_presence_does_not_confirm_pfquest_values():
    pf = _pf({1: {"lvl": 5, "min": 3, "name": "Q"}})
    q = _one(pf, {1})
    assert q["sources"] == ["wago-db2", "pfquest"]
    assert q["lineages"] == ["blizzard-client", "vanilla-emu"]  # record fields unchanged
    assert q["conflicts"] == [] and q["confidence"] == "unverified"


def test_value_sources_from_two_lineages_still_cross_check():
    from pipeline.normalize.quests import confidence_for

    assert confidence_for({"vanilla-emu", "blizzard-client"}, []) == "cross-checked"


def test_manual_endpoint_changing_type_or_id_resets_pfquest_point():
    pf = _pf({1: {"start": {"U": [5]}, "name": "Q"}}, {5: _unit("S", (1.0, 2.0, 12))})
    q = _one(pf, {1}, manual={1: _manual(start={"type": "npc", "id": 7})})
    assert q["start"] == {"type": "npc", "id": 7, "name": None, "uiMapId": None, "x": None, "y": None}
    assert "start" in q["conflicts"] and "start.coords" in q["conflicts"]
    # a type change counts too, and full manual coordinates satisfy the .coords conflict
    full = {"type": "object", "id": 5, "name": "Obj", "uiMapId": 1429, "x": 3.0, "y": 4.0}
    q = _one(pf, {1}, manual={1: _manual(start=full)})
    assert q["start"] == full
    assert "start" in q["conflicts"] and "start.coords" not in q["conflicts"]
    assert validate("quest", q) == []
    # manual name only (no coords) for the new endpoint still leaves coords unresolved
    q = _one(pf, {1}, manual={1: _manual(start={"type": "npc", "id": 7, "name": "New"})})
    assert q["start"]["name"] == "New" and q["start"]["x"] is None
    assert "start.coords" in q["conflicts"]


def test_classes_from_mask():
    from pipeline.normalize.quests import classes_from_mask

    assert classes_from_mask(None) is None
    assert classes_from_mask(0) is None
    assert classes_from_mask(8) == ["Rogue"]
    assert classes_from_mask(1494) == ["Paladin", "Hunter", "Priest", "Shaman", "Mage", "Warlock", "Druid"]
    assert classes_from_mask(1 | 32 | 2048) == ["Warrior", "unknown-bit-32", "unknown-bit-2048"]


def test_class_mask_carried_into_canonical_classes():
    pf = _pf({1: {"name": "Q", "class": 256}, 2: {"name": "R"}})
    out = {r["id"]: r for r in build_canonical(pf, frozenset(), Z, {})}
    assert out[1]["classes"] == ["Warlock"]
    assert out[2]["classes"] is None
    assert validate("quest", out[1]) == [] and validate("quest", out[2]) == []
