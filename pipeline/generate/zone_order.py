"""Zone order files: ordered zone names resolved to UiMapIDs."""
import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from pipeline.config import ROOT

_SCHEMA = json.loads((ROOT / "schema" / "zone-order.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft202012Validator(_SCHEMA)


@dataclass
class ZoneOrder:
    route: str
    race: str
    faction: str
    reviewed: bool
    zones: list[int]


def load_zone_order(path: Path, uimaps: dict[int, str], parents: dict[int, int] | None = None) -> ZoneOrder:
    """Load and validate a zone order file; names must match exactly one UiMap name. With `parents`, a name shared
    by several maps means the one that has a parent map (the game also lists a parentless Zephras Isle)."""
    path = Path(path)
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path.name}: invalid YAML: {' '.join(str(exc).split())}") from exc
    errors = sorted(_VALIDATOR.iter_errors(doc), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = [f"/{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors]
        raise ValueError(f"{path.name}: schema errors: " + "; ".join(msgs))

    by_name: dict[str, list[int]] = {}
    for map_id, name in uimaps.items():
        by_name.setdefault(name, []).append(map_id)

    ids: list[int] = []
    for name in doc["zones"]:
        matches = by_name.get(name, [])
        if len(matches) > 1 and parents is not None:
            matches = [m for m in matches if parents.get(m)] or matches
        if not matches:
            raise ValueError(f"{path.name}: unknown zone name {name!r}")
        if len(matches) > 1:
            raise ValueError(f"{path.name}: zone name {name!r} matches several UiMapIDs {sorted(matches)}")
        if matches[0] in ids:
            raise ValueError(f"{path.name}: duplicate zone {name!r}")
        ids.append(matches[0])
    return ZoneOrder(doc["route"], doc["race"], doc["faction"], doc["reviewed"], ids)
