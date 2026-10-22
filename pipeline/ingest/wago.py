"""Download and load wago.tools DB2 CSV exports for the Forever build."""
import csv
import http.client
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

USER_AGENT = "forever-leveling-pipeline/0.1"  # wago rejects urllib's default agent with 403
URL_TEMPLATE = "https://wago.tools/db2/{table}/csv?build={build}"
WAGO_TABLES = ("QuestV2", "UiMap", "UiMapAssignment", "AreaTable", "QuestXP", "TaxiNodes", "TaxiPath")


def fetch_tables(build: str, raw_dir: Path, opener: Callable = urllib.request.urlopen,
                 tables: tuple[str, ...] = WAGO_TABLES) -> None:
    """Download the wago tables into raw_dir/wago/<build>; never leaves a partial .csv."""
    out = Path(raw_dir) / "wago" / build
    out.mkdir(parents=True, exist_ok=True)
    for table in tables:
        dest = out / f"{table}.csv"
        part = dest.with_name(dest.name + ".part")
        try:
            req = urllib.request.Request(
                URL_TEMPLATE.format(table=table, build=build), headers={"User-Agent": USER_AGENT}
            )
            with opener(req, timeout=60) as resp:
                status = getattr(resp, "status", 200)
                if status != 200:
                    raise RuntimeError(f"HTTP {status}")
                part.write_bytes(resp.read())
        except (urllib.error.URLError, OSError, http.client.HTTPException, RuntimeError) as exc:
            part.unlink(missing_ok=True)
            raise RuntimeError(f"failed to download {table}: {exc}") from exc
        part.replace(dest)


def _rows(path: Path):
    with open(path, encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)


def load_quest_ids(dir: Path) -> frozenset[int]:
    return frozenset(int(r["ID"]) for r in _rows(Path(dir) / "QuestV2.csv"))


def load_uimaps(dir: Path) -> dict[int, str]:
    return {int(r["ID"]): r["Name_lang"] for r in _rows(Path(dir) / "UiMap.csv")}


def load_uimap_parents(dir: Path) -> dict[int, int]:
    """UiMapID -> ParentUiMapID (0 for the root)."""
    return {int(r["ID"]): int(r["ParentUiMapID"]) for r in _rows(Path(dir) / "UiMap.csv")}


def load_quest_xp(dir: Path) -> dict[int, list[int]]:
    """QuestXP ID (quest level) -> [Difficulty_0 .. Difficulty_9]."""
    return {
        int(r["ID"]): [int(r[f"Difficulty_{i}"]) for i in range(10)]
        for r in _rows(Path(dir) / "QuestXP.csv")
    }


def load_zone_to_uimap(dir: Path) -> dict[int, int]:
    """AreaTable ID -> UiMapID, using the matching assignment with the smallest OrderIndex."""
    best: dict[int, tuple[int, int]] = {}  # area -> (order, uimap)
    for r in _rows(Path(dir) / "UiMapAssignment.csv"):
        area, order, uimap = int(r["AreaID"]), int(r["OrderIndex"]), int(r["UiMapID"])
        if area not in best or order < best[area][0]:
            best[area] = (order, uimap)
    return {
        int(r["ID"]): best[int(r["ID"])][1]
        for r in _rows(Path(dir) / "AreaTable.csv")
        if int(r["ID"]) in best
    }
