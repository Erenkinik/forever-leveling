import json
import shutil
from pathlib import Path

import pytest

import pipeline.__main__ as cli
from pipeline.canonical import load_spawns_canonical
from pipeline.config import DATA_BUILD
from pipeline.ingest.pfquest import PfData, load_pfquest
from pipeline.normalize.spawns import build_spawns

FIX = Path(__file__).parent / "fixtures"


def _quest(qid, start=None, end=None, units=(), items=(), objects=()):
    def pt(ref):
        return {"type": ref[0], "id": ref[1]} if ref else {"type": None, "id": None}

    return {"id": qid, "start": pt(start), "end": pt(end),
            "objectives": {"units": list(units), "items": list(items), "objects": list(objects)}}


def _pf(units=None, objects=None, items=None):
    return PfData(
        quests={},
        units={k: {"coords": v[1], "fac": None, "name": v[0]} for k, v in (units or {}).items()},
        objects={k: {"coords": v, "fac": None, "name": f"Object {k}"} for k, v in (objects or {}).items()},
        items=items or {},
    )


ZONES = {12: 1429, 14: 1411}


def test_spawns_only_referenced_entities():
    pf = _pf(
        units={1: ("Start", [(10.0, 20.0, 12, )]), 2: ("End", [(30.0, 40.0, 12)]),
               3: ("Kill", [(5.0, 6.0, 14)]), 99: ("Unused", [(1.0, 1.0, 12)])},
        objects={7: [(50.0, 60.0, 12)], 98: [(2.0, 2.0, 12)]},
    )
    q = _quest(1, start=("npc", 1), end=("npc", 2), units=[3], objects=[7])
    out = build_spawns(pf, [q], ZONES)
    assert sorted(out["units"], key=int) == ["1", "2", "3"]
    assert out["units"]["1"] == {"name": "Start", "points": [[1429, 10.0, 20.0]]}
    assert out["units"]["3"]["points"] == [[1411, 5.0, 6.0]]
    assert list(out["objects"]) == ["7"]
    assert out["objects"]["7"] == {"name": "Object 7", "points": [[1429, 50.0, 60.0]]}
    assert out["items"] == {} and out["droppedPoints"] == 0


def test_item_sources_listed():
    pf = _pf(
        units={5: ("Dropper", [(1.0, 2.0, 12)]), 6: ("Other", [(3.0, 4.0, 12)])},
        objects={8: [(7.0, 8.0, 12)]},
        items={750: {"units": [5], "objects": [8]}, 751: {"units": [6], "objects": []}},
    )
    q = _quest(2, end=("npc", 5), items=[750])
    out = build_spawns(pf, [q], ZONES)
    assert out["items"] == {"750": {"units": [5], "objects": [8], "name": None}}
    assert "8" in out["objects"] and out["objects"]["8"]["points"] == [[1429, 7.0, 8.0]]
    assert "6" not in out["units"]


def test_item_start_and_end_refs_included():
    pf = _pf(units={5: ("D", [(1.0, 2.0, 12)])}, items={6497: {"units": [5], "objects": []}})
    out = build_spawns(pf, [_quest(3, start=("item", 6497))], ZONES)
    assert out["items"] == {"6497": {"units": [5], "objects": [], "name": None}}
    assert "5" in out["units"]


def test_unmapped_zone_points_counted():
    pf = _pf(
        units={1: ("A", [(1.0, 1.0, 12), (2.0, 2.0, 9999), (3.0, 3.0, 8888)])},
        objects={7: [(4.0, 4.0, 9999)]},
    )
    out = build_spawns(pf, [_quest(4, start=("npc", 1), objects=[7])], ZONES)
    assert out["units"]["1"]["points"] == [[1429, 1.0, 1.0]]
    assert out["objects"]["7"]["points"] == []
    assert out["droppedPoints"] == 3


def test_duplicate_points_collapsed_and_ids_numeric_sorted():
    pf = _pf(units={10: ("B", [(1.0, 1.0, 12), (1.0, 1.0, 12)]), 2: ("A", [])})
    out = build_spawns(pf, [_quest(5, start=("npc", 10), end=("npc", 2))], ZONES)
    assert list(out["units"]) == ["2", "10"]
    assert out["units"]["10"]["points"] == [[1429, 1.0, 1.0]]


def test_load_pfquest_reads_items():
    data = load_pfquest(FIX / "pfquest")
    assert data.items[750] == {"units": [197], "objects": [31], "name": "Tough Wolf Meat"}
    assert data.items[17] == {"units": [], "objects": [], "name": "Martin Fury"}
    assert data.items[6497] == {"units": [], "objects": [], "name": None}  # vendors ("V") are not drop sources
    assert data.objects[31]["name"] == "Old Lion Statue" and data.objects[4]["name"] is None


def test_pfdata_items_default_empty():
    assert PfData(quests={}, units={}, objects={}).items == {}


@pytest.fixture
def env(tmp_path, monkeypatch):
    raw, data = tmp_path / "raw", tmp_path / "data"
    shutil.copytree(FIX / "pfquest", raw / "pfquest")
    shutil.copytree(FIX / "wago", raw / "wago" / DATA_BUILD)
    (data / "manual").mkdir(parents=True)
    shutil.copy(FIX / "manual" / "quests.yaml", data / "manual" / "quests.yaml")
    monkeypatch.setattr(cli, "RAW_DIR", raw)
    monkeypatch.setattr(cli, "DATA_DIR", data)
    return raw, data


def test_normalize_writes_spawns_and_loader_reads_it(env):
    _, data = env
    assert cli.main(["normalize"]) == 0
    path = data / "canonical" / "spawns.json"
    assert b"\r\n" not in path.read_bytes()
    doc = load_spawns_canonical(data)
    assert doc["units"]["197"]["name"] == "Marshal McBride"
    assert doc["build"] == DATA_BUILD


def test_normalize_check_detects_spawns_drift(env, capsys):
    _, data = env
    assert cli.main(["normalize"]) == 0
    assert cli.main(["normalize", "--check"]) == 0
    path = data / "canonical" / "spawns.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["droppedPoints"] += 1
    path.write_text(json.dumps(doc), encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["normalize", "--check"]) == 1
    assert "spawns.json" in capsys.readouterr().err


def test_normalize_without_items_lua_is_a_clear_error(env, capsys):
    raw, _ = env
    (raw / "pfquest" / "items.lua").unlink()
    assert cli.main(["normalize"]) == 1
    assert "items.lua" in capsys.readouterr().err


def test_missing_and_empty_entities_reported():
    pf = _pf(units={1: ("A", []), 2: ("B", [(1.0, 1.0, 12)])}, objects={7: []},
             items={750: {"units": [2, 55], "objects": [9]}})
    q = _quest(6, start=("npc", 1), end=("npc", 404), units=[2], objects=[7, 808], items=[750, 751])
    out = build_spawns(pf, [q], ZONES)
    assert out["missingUnits"] == [55, 404]
    assert out["missingObjects"] == [9, 808]
    assert out["missingItems"] == [751]
    assert out["emptyPointUnits"] == 1 and out["emptyPointObjects"] == 1
    assert "404" not in out["units"] and "808" not in out["objects"]


def test_load_pfquest_require_items(tmp_path):
    import shutil as sh
    sh.copytree(FIX / "pfquest", tmp_path / "pf")
    (tmp_path / "pf" / "items.lua").unlink()
    assert load_pfquest(tmp_path / "pf").items == {}
    with pytest.raises(FileNotFoundError):
        load_pfquest(tmp_path / "pf", require_items=True)


@pytest.mark.parametrize("name_file", ["enUS/items.lua", "enUS/objects.lua"])
def test_require_items_also_requires_name_files(tmp_path, name_file):
    import shutil as sh
    sh.copytree(FIX / "pfquest", tmp_path / "pf")
    (tmp_path / "pf" / name_file).unlink()
    assert load_pfquest(tmp_path / "pf") is not None
    with pytest.raises(FileNotFoundError, match=name_file.split("/")[-1]):
        load_pfquest(tmp_path / "pf", require_items=True)


def test_spawns_carry_object_and_item_names():
    pf = _pf(units={5: ("Wolf", [(1.0, 2.0, 12)])}, objects={31: [(3.0, 4.0, 12)]},
             items={750: {"units": [5], "objects": [], "name": "Tough Wolf Meat"}})
    out = build_spawns(pf, [_quest(1, items=[750], objects=[31])], ZONES)
    assert out["objects"]["31"]["name"] == "Object 31"
    assert out["items"]["750"] == {"units": [5], "objects": [], "name": "Tough Wolf Meat"}
