"""Zone map images for the site: the game's own map art from wago.tools, stitched from its tiles.

Map art is © Blizzard Entertainment (see THIRD_PARTY.md). Raw tiles are cached under raw/mapart and never
committed; the stitched WebP images go to site/public/maps/<uiMapId>.webp.
"""
import csv
import io
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image

from pipeline.ingest.wago import USER_AGENT, fetch_tables

MAP_TABLES = ("UiMapXMapArt", "UiMapArt", "UiMapArtStyleLayer", "UiMapArtTile", "WorldMapOverlay",
              "WorldMapOverlayTile")
# Explored-area overlays (towns, landmarks) are made of 256px tiles.
OVERLAY_TILE = 256
CASC_URL = "https://wago.tools/api/casc/{fdid}?download"
WEBP_QUALITY = 82


@dataclass(frozen=True)
class Overlay:
    """An explored-area drawing: placed at (x, y) on the map, width x height, from 256px tiles."""
    x: int
    y: int
    width: int
    height: int
    tiles: list[tuple[int, int, int]]  # (row, col, FileDataID)


@dataclass(frozen=True)
class MapArt:
    width: int
    height: int
    tile_width: int
    tile_height: int
    tiles: list[tuple[int, int, int]]  # (row, col, FileDataID), base layer only
    overlays: list[Overlay] = field(default_factory=list)  # the map as fully explored


def load_map_tables(wago_dir: Path) -> dict[str, list[dict]]:
    out = {}
    for table in MAP_TABLES:
        with open(Path(wago_dir) / f"{table}.csv", encoding="utf-8", newline="") as fh:
            out[table] = list(csv.DictReader(fh))
    return out


def map_art(uimap_id: int, tables: dict[str, list[dict]]) -> MapArt | None:
    """The unphased (PhaseID 0) art of a UiMap with its base layer (LayerIndex 0) and its unconditional
    explored overlays; None when it has none."""
    art_id = next((r["UiMapArtID"] for r in tables["UiMapXMapArt"]
                   if int(r["UiMapID"]) == uimap_id and r["PhaseID"] == "0"), None)
    if art_id is None:
        return None
    style = next((r["UiMapArtStyleID"] for r in tables["UiMapArt"] if r["ID"] == art_id), None)
    layer = next((r for r in tables["UiMapArtStyleLayer"]
                  if r["UiMapArtStyleID"] == style and r["LayerIndex"] == "0"), None)
    tiles = sorted((int(r["RowIndex"]), int(r["ColIndex"]), int(r["FileDataID"])) for r in tables["UiMapArtTile"]
                   if r["UiMapArtID"] == art_id and r["LayerIndex"] == "0")
    if layer is None or not tiles:
        return None
    overlays = []
    for o in tables.get("WorldMapOverlay", []):
        if o["UiMapArtID"] != art_id or o["PlayerConditionID"] != "0":
            continue  # other maps, and overlays that need a player condition (phases)
        o_tiles = sorted((int(t["RowIndex"]), int(t["ColIndex"]), int(t["FileDataID"]))
                         for t in tables.get("WorldMapOverlayTile", [])
                         if t["WorldMapOverlayID"] == o["ID"] and t["LayerIndex"] == "0")
        if o_tiles:
            overlays.append(Overlay(int(o["OffsetX"]), int(o["OffsetY"]), int(o["TextureWidth"]),
                                    int(o["TextureHeight"]), o_tiles))
    return MapArt(int(layer["LayerWidth"]), int(layer["LayerHeight"]), int(layer["TileWidth"]),
                  int(layer["TileHeight"]), tiles, overlays)


def compose(tiles: list[tuple[int, int, Image.Image]], tile_w: int, tile_h: int, width: int,
            height: int) -> Image.Image:
    """Paste tiles at (col * tile_w, row * tile_h) on a black canvas cropped to width x height."""
    canvas = Image.new("RGB", (width, height))
    for row, col, tile in tiles:
        canvas.paste(tile.convert("RGB"), (col * tile_w, row * tile_h))
    return canvas


def paste_overlay(base: Image.Image, tiles: list[tuple[int, int, Image.Image]], tile: int, x: int, y: int,
                  width: int, height: int) -> None:
    """Draw an overlay's tiles onto base at (x, y), clipped to width x height, through their alpha."""
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for row, col, image in tiles:
        layer.paste(image.convert("RGBA"), (col * tile, row * tile))
    base.paste(layer, (x, y), layer)


def _tile(fdid: int, cache: Path, opener: Callable) -> Image.Image:
    path = cache / f"{fdid}.blp"
    if not path.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(CASC_URL.format(fdid=fdid), headers={"User-Agent": USER_AGENT})
        with opener(req, timeout=60) as resp:
            data = resp.read()
        if not data.startswith(b"BLP"):
            raise RuntimeError(f"map tile {fdid}: not a BLP file")
        path.write_bytes(data)
    return Image.open(io.BytesIO(path.read_bytes()))


def build_maps(map_ids: list[int], build: str, raw_dir: Path, out_dir: Path,
               opener: Callable = urllib.request.urlopen) -> dict[str, dict | None]:
    """Write <out_dir>/<id>.webp for every map with art; the result maps id -> size, or None (no art)."""
    wago = Path(raw_dir) / "wago" / build
    if not all((wago / f"{t}.csv").is_file() for t in MAP_TABLES):
        fetch_tables(build, raw_dir, opener, tables=MAP_TABLES)
    tables = load_map_tables(wago)
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, dict | None] = {}
    for map_id in sorted(set(map_ids)):
        art = map_art(map_id, tables)
        if art is None:
            result[str(map_id)] = None
            continue
        tiles = [(r, c, _tile(fdid, Path(raw_dir) / "mapart", opener)) for r, c, fdid in art.tiles]
        image = compose(tiles, art.tile_width, art.tile_height, art.width, art.height)
        for o in art.overlays:
            o_tiles = [(r, c, _tile(fdid, Path(raw_dir) / "mapart", opener)) for r, c, fdid in o.tiles]
            paste_overlay(image, o_tiles, OVERLAY_TILE, o.x, o.y, o.width, o.height)
        image.save(out_dir / f"{map_id}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
        result[str(map_id)] = {"width": art.width, "height": art.height}
    return result


# Race crests from the game's credits screens: four 1024px tiles each (FileDataIDs base..base+3, row by row).
# Human and Gnome share the Alliance crest, Orc uses the Horde banner, Undead the Forsaken crest.
ART_QUADS: dict[str, int] = {
    "crest-human": 131223,
    "crest-gnome": 131223,
    "crest-dwarf": 131459,
    "crest-night-elf": 131581,
    "crest-orc": 131507,
    "crest-troll": 131777,
    "crest-undead": 131487,
    "crest-tauren": 131715,
}
# The quest frame parchment (interface/questframe/questbg.blp): the page is the top-left 300x335 of the texture.
PARCHMENT = (530420, (0, 0, 300, 335))
CREST_MAX = 640
# Map and step icons from the minimap object icon atlas (interface/minimap/objecticons.blp): 32px cells,
# (column, row). The same "!" and "?" the game shows over quest givers.
ICON_ATLAS = 136435
ICON_SIZE = 32
ATLAS_ICONS: dict[str, tuple[int, int]] = {
    "accept": (1, 1),   # yellow !
    "turnin": (2, 1),   # yellow ?
    "kill": (4, 5),     # crossed swords
    "collect": (1, 2),  # loot sack
    "use": (1, 4),      # gear
    "grind": (5, 3),    # skull
}


def stitch_quad(tiles: list[Image.Image]) -> Image.Image:
    """Four equal tiles as a 2x2 image (top-left, top-right, bottom-left, bottom-right), trimmed to the opaque part."""
    w, h = tiles[0].size
    canvas = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    for i, tile in enumerate(tiles):
        canvas.paste(tile.convert("RGBA"), ((i % 2) * w, (i // 2) * h))
    box = canvas.getchannel("A").getbbox()
    return canvas.crop(box) if box else canvas


def atlas_icon(atlas: Image.Image, col: int, row: int) -> Image.Image:
    return atlas.convert("RGBA").crop((col * ICON_SIZE, row * ICON_SIZE, (col + 1) * ICON_SIZE, (row + 1) * ICON_SIZE))


def build_art(raw_dir: Path, out_dir: Path, opener: Callable = urllib.request.urlopen) -> list[str]:
    """Write <out_dir>/<name>.webp for the race crests, the quest parchment and the icons; returns the names."""
    cache = Path(raw_dir) / "art"
    out_dir.mkdir(parents=True, exist_ok=True)
    stitched: dict[int, Image.Image] = {}
    names = []
    for name, base in ART_QUADS.items():
        if base not in stitched:
            crest = stitch_quad([_tile(base + i, cache, opener) for i in range(4)])
            crest.thumbnail((CREST_MAX, CREST_MAX))
            stitched[base] = crest
        stitched[base].save(out_dir / f"{name}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
        names.append(name)
    fdid, box = PARCHMENT
    _tile(fdid, cache, opener).convert("RGB").crop(box).save(out_dir / "parchment.webp", "WEBP",
                                                             quality=WEBP_QUALITY, method=6)
    names.append("parchment")
    atlas = _tile(ICON_ATLAS, cache, opener)
    for name, (col, row) in ATLAS_ICONS.items():
        atlas_icon(atlas, col, row).save(out_dir / f"icon-{name}.webp", "WEBP", lossless=True)
        names.append(f"icon-{name}")
    return names


def item_icon_ids(item_ids: list[int], item_rows: list[dict]) -> dict[str, int | None]:
    """Item id -> its icon FileDataID from the Item table; None when the item is unknown or has no icon."""
    icons = {r["ID"]: int(r["IconFileDataID"]) for r in item_rows}
    return {str(i): (icons.get(str(i)) or None) for i in item_ids}


def build_item_icons(item_ids: list[int], build: str, raw_dir: Path, out_dir: Path,
                     opener: Callable = urllib.request.urlopen) -> dict[str, int | None]:
    """Write <out_dir>/<iconFileDataID>.webp for the items' icons; returns item id -> icon id (or None)."""
    wago = Path(raw_dir) / "wago" / build
    if not (wago / "Item.csv").is_file():
        fetch_tables(build, raw_dir, opener, tables=("Item",))
    with open(wago / "Item.csv", encoding="utf-8", newline="") as fh:
        index = item_icon_ids(item_ids, list(csv.DictReader(fh)))
    out_dir.mkdir(parents=True, exist_ok=True)
    for fdid in sorted({f for f in index.values() if f}):
        _tile(fdid, Path(raw_dir) / "icons", opener).convert("RGBA").save(out_dir / f"{fdid}.webp", "WEBP",
                                                                          quality=90)
    return index
