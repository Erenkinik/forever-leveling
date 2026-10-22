from pathlib import Path

import pytest

from pipeline.ingest.wago import (
    WAGO_TABLES,
    fetch_tables,
    load_quest_ids,
    load_uimaps,
    load_zone_to_uimap,
)

FIX = Path(__file__).parent / "fixtures" / "wago"


class _Resp:
    def __init__(self, status: int, body: bytes = b"ID\n1\n"):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_load_quest_ids():
    ids = load_quest_ids(FIX)
    assert 33 in ids and 783 in ids
    assert 99999 not in ids


def test_load_uimaps_has_zephras():
    assert load_uimaps(FIX)[2521] == "Zephras Isle"


def test_zone_to_uimap_elwynn():
    assert load_zone_to_uimap(FIX)[12] == 1429


def test_zone_to_uimap_picks_lowest_order_index(tmp_path):
    header = "ID,UiMapID,OrderIndex,AreaID\n"
    (tmp_path / "UiMapAssignment.csv").write_text(
        header + "1,500,2,12\n2,400,0,12\n3,600,1,12\n", encoding="utf-8"
    )
    (tmp_path / "AreaTable.csv").write_text("ID,ZoneName\n12,Elwynn\n", encoding="utf-8")
    assert load_zone_to_uimap(tmp_path) == {12: 400}


def test_fetch_refuses_partial_file(tmp_path):
    def opener(url, timeout=None):
        return _Resp(500)

    with pytest.raises(RuntimeError):
        fetch_tables("1.60.1.70532", tmp_path, opener=opener)
    out = tmp_path / "wago" / "1.60.1.70532"
    assert not list(out.glob("*.csv")) and not list(out.glob("*.part"))


def test_fetch_writes_all_tables(tmp_path):
    urls = []

    def opener(url, timeout=None):
        urls.append(url.full_url)
        return _Resp(200)

    fetch_tables("1.60.1.70532", tmp_path, opener=opener)
    out = tmp_path / "wago" / "1.60.1.70532"
    assert sorted(p.name for p in out.glob("*.csv")) == sorted(f"{t}.csv" for t in WAGO_TABLES)
    assert urls[0] == "https://wago.tools/db2/QuestV2/csv?build=1.60.1.70532"
