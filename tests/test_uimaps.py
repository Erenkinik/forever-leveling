import json

import pipeline.__main__ as cli
from pipeline.canonical import load_uimaps_canonical
from pipeline.config import DATA_DIR


def test_uimaps_has_known_zones():
    maps = load_uimaps_canonical()
    assert maps[1429] == "Elwynn Forest"
    assert maps[2521] == "Zephras Isle"


def test_uimaps_file_shape_is_sorted_numeric():
    doc = json.loads((DATA_DIR / "canonical" / "uimaps.json").read_text(encoding="utf-8"))
    assert set(doc) == {"build", "maps"}
    keys = [int(k) for k in doc["maps"]]
    assert keys == sorted(keys)


def test_validate_all_runs_without_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RAW_DIR", tmp_path / "empty-raw")
    assert cli.main(["validate", "--all"]) == 0


def test_records_use_seen_in_build():
    quests = json.loads((DATA_DIR / "canonical" / "quests.json").read_text(encoding="utf-8"))
    assert quests
    for q in quests:
        assert "seenInBuild" in q and "verifiedBuild" not in q
