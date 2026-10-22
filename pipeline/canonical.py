"""Committed canonical facts (data/canonical/*.json) shared by the CLI and later stages."""
import json
from pathlib import Path

from pipeline.config import DATA_DIR


def load_uimaps_canonical(data_dir: Path = DATA_DIR) -> dict[int, str]:
    """UiMapID -> name from the committed uimaps.json."""
    doc = json.loads((Path(data_dir) / "canonical" / "uimaps.json").read_text(encoding="utf-8"))
    return {int(k): v for k, v in doc["maps"].items()}
