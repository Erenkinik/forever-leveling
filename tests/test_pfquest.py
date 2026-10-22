import io
import urllib.error
from pathlib import Path

import pytest

from pipeline.ingest.pfquest import PfData, fetch_pfquest, load_pfquest

FIX = Path(__file__).parent / "fixtures" / "pfquest"


@pytest.fixture(scope="module")
def data() -> PfData:
    return load_pfquest(FIX)


def test_load_pfquest_joins_enus_name(data):
    assert data.quests[33]["name"] == "Wolves Across the Border"


def test_load_pfquest_drops_description_text(data):
    assert "D" not in data.quests[33]
    assert "O" not in data.quests[33]
    assert data.quests[33]["pre"] == [5261]


def test_item_started_quest(data):
    assert data.quests[1]["start"] == {"I": [6497]}
    assert data.quests[1]["name"] == 'The "Chow" Quest (123)aa'


def test_unit_coords_tuple(data):
    assert data.units[197]["coords"][0] == (48.9, 41.6, 12)
    assert data.units[197]["name"] == "Marshal McBride"
    assert data.units[197]["fac"] == "A"


def test_objects_without_coords(data):
    assert data.objects[4]["coords"] == []
    assert data.objects[31]["coords"] == [(84.5, 46.8, 44)]


def test_pfdata_is_frozen(data):
    with pytest.raises(Exception):
        data.quests = {}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_fetch_writes_all_files_and_no_part(tmp_path):
    fetch_pfquest(tmp_path, opener=lambda url: _Resp(b"pfDB = {}"))
    base = tmp_path / "pfquest"
    for rel in ("quests.lua", "units.lua", "objects.lua", "enUS/quests.lua", "enUS/units.lua"):
        assert (base / rel).read_bytes() == b"pfDB = {}"
    assert not list(base.rglob("*.part"))


def test_fetch_http_error_names_file_and_leaves_no_partial(tmp_path):
    def opener(url):
        if url.endswith("units.lua") and "enUS" not in url:
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        return _Resp(b"x")

    with pytest.raises(RuntimeError, match="units.lua"):
        fetch_pfquest(tmp_path, opener=opener)
    base = tmp_path / "pfquest"
    assert not (base / "units.lua").exists()
    assert not list(base.rglob("*.part"))
