import copy
import json
from pathlib import Path

import pytest

from pipeline.config import ROOT, SOURCE_LINEAGE
from pipeline.schema import validate

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_quest():
    point = {"type": "npc", "id": 823, "name": "Deputy Willem", "uiMapId": 1429, "x": 48.2, "y": 41.7}
    return {
        "id": 783, "name": "A Threat Within", "level": 1, "minLevel": 1, "races": None, "classes": None,
        "prereqs": [], "start": dict(point), "end": dict(point),
        "objectives": {"units": [], "items": [], "objects": []},
        "inForever": True, "sources": ["wago-db2", "pfquest"], "lineages": ["blizzard-client", "vanilla-emu"],
        "conflicts": [], "confidence": "cross-checked", "seenInBuild": None,
    }


def test_valid_route_passes():
    assert validate("route", load("route_valid.json")) == []


def test_unknown_step_type_rejected():
    errs = validate("route", load("route_invalid_steptype.json"))
    assert any("/steps/0" in e for e in errs)


def test_gap_step_requires_reason():
    r = load("route_valid.json")
    r["steps"].append({"id": "g1", "type": "gap", "mapId": 1429, "x": 1, "y": 1, "confidence": "unverified"})
    assert validate("route", r) != []


def test_gap_step_with_reason_passes():
    r = load("route_valid.json")
    r["steps"].append({"id": "g1", "type": "gap", "mapId": 1429, "x": 1, "y": 1,
                       "confidence": "unverified", "reason": "no data"})
    assert validate("route", r) == []


@pytest.mark.parametrize("axis,value", [("x", 101), ("y", -0.5)])
def test_coords_out_of_range_rejected(axis, value):
    r = load("route_valid.json")
    r["steps"][0][axis] = value
    errs = validate("route", r)
    assert any(f"/steps/0/{axis}" in e for e in errs)


def test_travel_requires_mode_and_radius():
    r = load("route_valid.json")
    r["steps"].append({"id": "t1", "type": "travel", "mapId": 1429, "x": 5, "y": 5, "confidence": "unverified"})
    assert validate("route", r) != []
    r["steps"][-1].update(mode="walk", radius=10)
    assert validate("route", r) == []


def test_valid_quest_passes():
    assert validate("quest", make_quest()) == []


def test_quest_unknown_source_rejected():
    q = make_quest()
    q["sources"] = ["not-a-source"]
    assert validate("quest", q) != []


def test_quest_source_enum_matches_config():
    schema = json.loads((ROOT / "schema" / "quest.schema.json").read_text(encoding="utf-8"))
    assert set(schema["properties"]["sources"]["items"]["enum"]) == set(SOURCE_LINEAGE)


def test_quest_bad_confidence_rejected():
    q = copy.deepcopy(make_quest())
    q["confidence"] = "sure"
    assert validate("quest", q) != []


def test_unknown_kind_raises():
    with pytest.raises(ValueError):
        validate("nope", {})


def test_quest_requires_classes():
    q = make_quest()
    del q["classes"]
    assert any("classes" in e for e in validate("quest", q))
    q["classes"] = ["Warlock"]
    assert validate("quest", q) == []
    q["classes"] = "Warlock"
    assert validate("quest", q) != []
