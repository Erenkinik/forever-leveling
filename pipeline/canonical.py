"""Committed canonical facts (data/canonical/*.json) shared by the CLI and later stages."""
import json
from pathlib import Path

from pipeline.config import DATA_DIR


def load_uimaps_canonical(data_dir: Path = DATA_DIR) -> dict[int, str]:
    """UiMapID -> name from the committed uimaps.json."""
    doc = json.loads((Path(data_dir) / "canonical" / "uimaps.json").read_text(encoding="utf-8"))
    return {int(k): v for k, v in doc["maps"].items()}


def load_uimap_parents_canonical(data_dir: Path = DATA_DIR) -> dict[int, int]:
    """UiMapID -> ParentUiMapID from the committed uimaps.json; ValueError when the file predates parents."""
    doc = json.loads((Path(data_dir) / "canonical" / "uimaps.json").read_text(encoding="utf-8"))
    if "parents" not in doc:
        raise ValueError("uimaps.json has no parents (run normalize)")
    return {int(k): int(v) for k, v in doc["parents"].items()}


def load_questxp_canonical(data_dir: Path = DATA_DIR) -> dict[int, list[int]]:
    """Quest level -> [Difficulty_0 .. Difficulty_9] from the committed questxp.json."""
    doc = json.loads((Path(data_dir) / "canonical" / "questxp.json").read_text(encoding="utf-8"))
    return {int(k): list(v) for k, v in doc["levels"].items()}


def load_spawns_canonical(data_dir: Path = DATA_DIR) -> dict:
    """The committed spawns.json: build, units, objects, items, droppedPoints."""
    return json.loads((Path(data_dir) / "canonical" / "spawns.json").read_text(encoding="utf-8"))


def load_taxi_canonical(data_dir: Path = DATA_DIR) -> dict | None:
    """The committed taxi.json (flight masters, flights, zone map bounds), or None before normalize wrote it."""
    path = Path(data_dir) / "canonical" / "taxi.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
