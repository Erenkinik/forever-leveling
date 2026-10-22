from pathlib import Path

import pytest
import yaml

from pipeline.ingest.manual import load_manual

FIX = Path(__file__).parent / "fixtures" / "manual" / "quests.yaml"
URL = "https://www.wowhead.com/forever/quest=1"


def _write(tmp_path, entries):
    p = tmp_path / "quests.yaml"
    p.write_text(yaml.safe_dump(entries), encoding="utf-8")
    return p


def _entry(**over):
    e = {"id": 1, "name": "Q", "level": 1, "minLevel": 1, "wowheadUrl": URL, "checkedOn": "2026-10-22"}
    e.update(over)
    return e


def test_manual_entry_loads():
    quests = load_manual(FIX)
    assert set(quests) == {90001, 90002}
    q = quests[90001]
    assert q["source"] == "wowhead-manual"
    assert q["name"] == "Test Forever Quest"
    assert q["level"] == 5 and q["minLevel"] == 3
    assert q["races"] == ["Human", "Dwarf"]
    assert q["prereqs"] == [90000]
    assert q["start"]["id"] == 1234 and q["start"]["x"] == 45.2
    assert q["end"]["name"] == "Test Receiver"
    assert q["wowheadUrl"].startswith("https://www.wowhead.com/forever/quest=")
    assert q["checkedOn"] == "2026-10-22"  # unquoted YAML date normalised to ISO string
    assert quests[90002]["checkedOn"] == "2026-10-21"
    assert "start" not in quests[90002]


def test_manual_requires_wowhead_url(tmp_path):
    e = _entry(id=777)
    del e["wowheadUrl"]
    with pytest.raises(ValueError, match="777"):
        load_manual(_write(tmp_path, [e]))


def test_manual_rejects_non_forever_url(tmp_path):
    e = _entry(id=778, wowheadUrl="https://www.wowhead.com/classic/quest=778")
    with pytest.raises(ValueError, match="778"):
        load_manual(_write(tmp_path, [e]))


def test_manual_duplicate_id_rejected(tmp_path):
    with pytest.raises(ValueError, match="779"):
        load_manual(_write(tmp_path, [_entry(id=779), _entry(id=779)]))


def test_manual_requires_checked_on(tmp_path):
    e = _entry(id=780)
    del e["checkedOn"]
    with pytest.raises(ValueError, match="780"):
        load_manual(_write(tmp_path, [e]))


def test_manual_rejects_bad_checked_on(tmp_path):
    with pytest.raises(ValueError, match="781"):
        load_manual(_write(tmp_path, [_entry(id=781, checkedOn="22/10/2026")]))


@pytest.mark.parametrize("content", ["", "[]\n"])
def test_manual_empty_is_empty_dict(tmp_path, content):
    p = tmp_path / "quests.yaml"
    p.write_text(content, encoding="utf-8")
    assert load_manual(p) == {}


def test_manual_non_list_rejected(tmp_path):
    p = tmp_path / "quests.yaml"
    p.write_text("id: 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_manual(p)
