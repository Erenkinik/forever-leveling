"""Zone map images for the site: the game's own map art from wago.tools, stitched from its tiles.

Map art is © Blizzard Entertainment (see THIRD_PARTY.md). Raw tiles are cached under raw/mapart and never
committed; the stitched WebP images go to site/public/maps/<uiMapId>.webp.
"""
import csv
import io
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from pipeline.ingest.wago import USER_AGENT, fetch_tables

MAP_TABLES = ("UiMapXMapArt", "UiMapArt", "UiMapArtStyleLayer", "UiMapArtTile")
CASC_URL = "https://wago.tools/api/casc/{fdid}?download"
WEBP_QUALITY = 82


@dataclass(frozen=True)
class MapArt:
    width: int
    height: int
    tile_width: int
    tile_height: int
    tiles: list[tuple[int, int, int]]  # (row, col, FileDataID), base layer only


def load_map_tables(wago_dir: Path) -> dict[str, list[dict]]:
    out = {}
    for table in MAP_TABLES:
        with open(Path(wago_dir) / f"{table}.csv", encoding="utf-8", newline="") as fh:
            out[table] = list(csv.DictReader(fh))
    return out


def map_art(uimap_id: int, tables: dict[str, list[dict]]) -> MapArt | None:
    """The unphased (PhaseID 0) art of a UiMap with its base layer (LayerIndex 0); None when it has none."""
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
    return MapArt(int(layer["LayerWidth"]), int(layer["LayerHeight"]), int(layer["TileWidth"]),
                  int(layer["TileHeight"]), tiles)


def compose(tiles: list[tuple[int, int, Image.Image]], tile_w: int, tile_h: int, width: int,
            height: int) -> Image.Image:
    """Paste tiles at (col * tile_w, row * tile_h) on a black canvas cropped to width x height."""
    canvas = Image.new("RGB", (width, height))
    for row, col, tile in tiles:
        canvas.paste(tile.convert("RGB"), (col * tile_w, row * tile_h))
    return canvas


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
        image.save(out_dir / f"{map_id}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
        result[str(map_id)] = {"width": art.width, "height": art.height}
    return result
