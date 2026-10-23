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
    # the world map (the home page's backdrop) is recorded unless a test gives its own entry for it
    maps = {str(cli.WORLD_MAP): None, **maps}
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


def test_maps_check_needs_the_world_map_for_the_home_page(tmp_path, monkeypatch, capsys):
    site = _env(tmp_path, monkeypatch, {"1429": None, "1436": None, "947": {"width": 1002, "height": 668}})
    assert cli.main(["maps", "--check"]) == 1
    assert "947" in capsys.readouterr().err
    (site / "public" / "maps" / "947.webp").write_bytes(b"x")
    assert cli.main(["maps", "--check"]) == 0


def test_maps_check_fails_for_a_map_never_built(tmp_path, monkeypatch, capsys):
    _env(tmp_path, monkeypatch, {"1429": None})
    assert cli.main(["maps", "--check"]) == 1
    assert "1436" in capsys.readouterr().err


def test_stitch_quad_places_four_tiles_and_trims_transparent_edges():
    from pipeline.export.maps import stitch_quad

    clear = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    solid = Image.new("RGBA", (4, 4), (200, 10, 10, 255))
    img = stitch_quad([clear, solid, clear, solid])  # right column only
    assert img.size == (4, 8)
    assert img.getpixel((0, 0)) == (200, 10, 10, 255)


def test_art_list_covers_every_route_race():
    from pipeline.export.maps import ART_QUADS
    from pipeline.generate.config import ROUTES

    assert {f"crest-{r}" for r in ROUTES} <= set(ART_QUADS)


def test_maps_check_needs_the_game_art_too(tmp_path, monkeypatch, capsys):
    site = _env(tmp_path, monkeypatch, {"1429": None, "1436": None})
    index = json.loads((site / "src" / "data" / "maps.json").read_text(encoding="utf-8"))
    index["art"] = ["parchment"]
    (site / "src" / "data" / "maps.json").write_text(json.dumps(index), encoding="utf-8")
    (site / "public" / "art").mkdir(parents=True)
    assert cli.main(["maps", "--check"]) == 1
    assert "parchment" in capsys.readouterr().err
    (site / "public" / "art" / "parchment.webp").write_bytes(b"x")
    assert cli.main(["maps", "--check"]) == 0


OVERLAY_TABLES = {
    **TABLES,
    "WorldMapOverlay": [
        {"ID": "7", "UiMapArtID": "50", "TextureWidth": "6", "TextureHeight": "3", "OffsetX": "2", "OffsetY": "1",
         "PlayerConditionID": "0"},
        {"ID": "8", "UiMapArtID": "50", "TextureWidth": "4", "TextureHeight": "4", "OffsetX": "0", "OffsetY": "0",
         "PlayerConditionID": "123"},  # conditional (phased) overlay: left out
        {"ID": "9", "UiMapArtID": "99", "TextureWidth": "4", "TextureHeight": "4", "OffsetX": "0", "OffsetY": "0",
         "PlayerConditionID": "0"},  # another map
    ],
    "WorldMapOverlayTile": [
        {"ID": "1", "RowIndex": "0", "ColIndex": "1", "LayerIndex": "0", "FileDataID": "701", "WorldMapOverlayID": "7"},
        {"ID": "2", "RowIndex": "0", "ColIndex": "0", "LayerIndex": "0", "FileDataID": "700", "WorldMapOverlayID": "7"},
        {"ID": "3", "RowIndex": "0", "ColIndex": "0", "LayerIndex": "0", "FileDataID": "800", "WorldMapOverlayID": "8"},
    ],
}


def test_map_art_carries_its_unconditional_explored_overlays():
    art = map_art(1429, OVERLAY_TABLES)
    assert [(o.x, o.y, o.width, o.height, o.tiles) for o in art.overlays] == [(2, 1, 6, 3, [(0, 0, 700), (0, 1, 701)])]


def test_overlay_is_pasted_at_its_offset_through_its_alpha():
    from pipeline.export.maps import paste_overlay

    base = Image.new("RGB", (10, 6), (10, 10, 10))
    left = Image.new("RGBA", (4, 4), (0, 200, 0, 255))
    right = Image.new("RGBA", (4, 4), (0, 0, 0, 0))  # transparent: base shows through
    paste_overlay(base, [(0, 0, left), (0, 1, right)], tile=4, x=2, y=1, width=6, height=3)
    assert base.getpixel((2, 1)) == (0, 200, 0)
    assert base.getpixel((7, 1)) == (10, 10, 10)
    assert base.getpixel((2, 4)) == (10, 10, 10)  # below the overlay's 3-pixel height


def test_atlas_icon_is_the_32px_cell_at_column_and_row():
    from pipeline.export.maps import ATLAS_ICONS, atlas_icon

    atlas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    atlas.paste(Image.new("RGBA", (32, 32), (255, 210, 0, 255)), (32, 32))  # column 1, row 1
    icon = atlas_icon(atlas, 1, 1)
    assert icon.size == (32, 32) and icon.getpixel((0, 0)) == (255, 210, 0, 255)
    assert set(ATLAS_ICONS) == {"accept", "turnin", "kill", "collect", "use", "grind", "flight"}


def _mark() -> Image.Image:
    """A 32px test mark: a yellow bar inside a black outline."""
    icon = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    icon.paste(Image.new("RGBA", (12, 28), (0, 0, 0, 255)), (10, 2))
    icon.paste(Image.new("RGBA", (8, 24), (255, 210, 0, 255)), (12, 4))
    return icon


def test_thin_icon_squeezes_the_mark_to_a_narrower_centred_one():
    from pipeline.export.maps import DERIVED_SIZE, thin_icon

    thin = thin_icon(_mark())
    box = thin.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()  # ignore resampling fringe
    assert thin.size == (DERIVED_SIZE, DERIVED_SIZE)
    assert box[2] - box[0] < 12 * 2 * 0.7  # the 12px-wide mark at 2x, now under 70% as wide
    assert abs((box[0] + box[2]) / 2 - DERIVED_SIZE / 2) <= 1


def test_hollow_icon_is_grey_with_an_empty_middle_and_a_kept_outline():
    from pipeline.export.maps import hollow_icon

    hollow = hollow_icon(_mark())
    assert hollow.getpixel((32, 32))[3] == 0  # the middle of the yellow bar is empty
    r, g, b, a = hollow.getpixel((25, 32))  # just inside the bar's left edge: grey rim
    assert a > 200 and r == g == b and r > 120
    assert max(hollow.getpixel((21, 32))[:3]) < 20  # the black outline stays


def test_item_icon_ids_maps_items_to_their_icon_file():
    from pipeline.export.maps import item_icon_ids

    rows = [{"ID": "750", "IconFileDataID": "133972"}, {"ID": "17", "IconFileDataID": "0"}, {"ID": "9", "IconFileDataID": "5"}]
    assert item_icon_ids([750, 17, 404], rows) == {"750": 133972, "17": None, "404": None}


def test_route_collect_items_are_the_collect_objectives_of_completed_quests(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "routes").mkdir(parents=True)
    (data / "canonical").mkdir()
    (data / "routes" / "t.json").write_text(json.dumps({"steps": [
        {"id": "complete-1", "type": "complete", "questId": 1, "mapId": 1429},
        {"id": "accept-2", "type": "accept", "questId": 2, "mapId": 1429}]}), encoding="utf-8")
    (data / "canonical" / "quests.json").write_text(json.dumps([
        {"id": 1, "objectives": {"units": [5], "items": [750, 751], "objects": []}},
        {"id": 2, "objectives": {"units": [], "items": [999], "objects": []}}]), encoding="utf-8")
    monkeypatch.setattr(cli, "DATA_DIR", data)
    assert cli._route_collect_items() == [750, 751]


def test_maps_check_needs_the_game_fonts(tmp_path, monkeypatch, capsys):
    site = _env(tmp_path, monkeypatch, {"1429": None, "1436": None})
    index = json.loads((site / "src" / "data" / "maps.json").read_text(encoding="utf-8"))
    index["fonts"] = ["frizqt"]
    (site / "src" / "data" / "maps.json").write_text(json.dumps(index), encoding="utf-8")
    assert cli.main(["maps", "--check"]) == 1
    assert "frizqt" in capsys.readouterr().err
    (site / "public" / "fonts").mkdir(parents=True)
    (site / "public" / "fonts" / "frizqt.ttf").write_bytes(b"x")
    assert cli.main(["maps", "--check"]) == 0
