import json

import pytest
from PIL import Image

import pipeline.__main__ as cli
from pipeline.config import DATA_BUILD
from pipeline.export.maps import compose, map_art

TABLES = {
    "UiMapXMapArt": [
        {"ID": "1", "PhaseID": "0", "UiMapArtID": "50", "UiMapID": "1429"},
        {"ID": "2", "PhaseID": "7", "UiMapArtID": "51", "UiMapID": "1429"},  # phased art is ignored
    ],
    "UiMapArt": [{"ID": "50", "HighlightFileDataID": "0", "HighlightAtlasID": "0", "UiMapArtStyleID": "1"}],
    "UiMapArtStyleLayer": [{"ID": "1", "LayerIndex": "0", "LayerWidth": "1002", "LayerHeight": "668",
                            "TileWidth": "256", "TileHeight": "256", "UiMapArtStyleID": "1"}],
    "UiMapArtTile": [
        {"ID": "10", "RowIndex": "0", "ColIndex": "0", "LayerIndex": "0", "FileDataID": "900", "UiMapArtID": "50"},
        {"ID": "11", "RowIndex": "0", "ColIndex": "1", "LayerIndex": "0", "FileDataID": "901", "UiMapArtID": "50"},
        {"ID": "12", "RowIndex": "1", "ColIndex": "0", "LayerIndex": "1", "FileDataID": "902", "UiMapArtID": "50"},
    ],
}


def test_map_art_picks_the_unphased_art_and_its_base_layer_tiles():
    art = map_art(1429, TABLES)
    assert art.width == 1002 and art.height == 668 and (art.tile_width, art.tile_height) == (256, 256)
    assert art.tiles == [(0, 0, 900), (0, 1, 901)]
    assert map_art(9999, TABLES) is None


def test_compose_places_tiles_by_row_and_column_and_crops_to_layer_size():
    red, blue = Image.new("RGB", (4, 4), "red"), Image.new("RGB", (4, 4), "blue")
    img = compose([(0, 0, red), (1, 1, blue)], tile_w=4, tile_h=4, width=7, height=6)
    assert img.size == (7, 6)
    assert img.getpixel((0, 0)) == (255, 0, 0)
    assert img.getpixel((5, 5)) == (0, 0, 255)
    assert img.getpixel((5, 0)) == (0, 0, 0)  # missing tile stays black


def _env(tmp_path, monkeypatch, maps):
    data = tmp_path / "data"
    (data / "routes").mkdir(parents=True)
    (data / "routes" / "t.json").write_text(json.dumps({"steps": [
        {"id": "a", "mapId": 1429}, {"id": "b", "mapId": 1436}]}), encoding="utf-8")
    site = tmp_path / "site"
    (site / "public" / "maps").mkdir(parents=True)
    (site / "src" / "data").mkdir(parents=True)
    (site / "src" / "data" / "maps.json").write_text(json.dumps({"build": DATA_BUILD, "maps": maps}), encoding="utf-8")
    monkeypatch.setattr(cli, "DATA_DIR", data)
    return site


def test_maps_check_needs_an_image_or_a_recorded_absence_for_every_route_map(tmp_path, monkeypatch, capsys):
    site = _env(tmp_path, monkeypatch, {"1429": {"width": 1002, "height": 668}, "1436": None})
    (site / "public" / "maps" / "1429.webp").write_bytes(b"x")
    assert cli.main(["maps", "--check"]) == 0
    (site / "public" / "maps" / "1429.webp").unlink()
    assert cli.main(["maps", "--check"]) == 1
    assert "1429" in capsys.readouterr().err


def test_maps_check_fails_for_a_map_never_built(tmp_path, monkeypatch, capsys):
    _env(tmp_path, monkeypatch, {"1429": None})
    assert cli.main(["maps", "--check"]) == 1
    assert "1436" in capsys.readouterr().err
