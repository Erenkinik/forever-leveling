"""Hand-written patches applied on top of a generated route. Patches never edit the generated file."""
import copy
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from pipeline.config import ROOT

_SCHEMA = json.loads((ROOT / "schema" / "overrides.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft202012Validator(_SCHEMA)


def load_overrides(path: Path) -> list[dict]:
    """Read and schema-check an overrides file; a missing file means no patches."""
    path = Path(path)
    if not path.is_file():
        return []
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path.name}: invalid YAML: {' '.join(str(exc).split())}") from exc
    if doc is None:
        return []
    errors = sorted(_VALIDATOR.iter_errors(doc), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = [f"/{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors]
        raise ValueError(f"{path.name}: schema errors: " + "; ".join(msgs))
    return doc


def apply_overrides(route: dict, patches: list[dict]) -> tuple[dict, list[str]]:
    """Apply patches in order to a copy of the route; a failing patch is reported and not applied."""
    out = copy.deepcopy(route)
    steps: list[dict] = out["steps"]
    errors: list[str] = []

    def index(sid: str) -> int | None:
        return next((i for i, s in enumerate(steps) if s["id"] == sid), None)

    for i, patch in enumerate(patches):
        op = patch["op"]

        def missing(sid: str) -> None:
            errors.append(f"patch {i} ({op}): step {sid} not found")

        if op == "insertAfter":
            pos = index(patch["after"])
            if pos is None:
                missing(patch["after"])
            elif index(patch["step"]["id"]) is not None:
                errors.append(f"patch {i} ({op}): step {patch['step']['id']} already exists")
            else:
                steps.insert(pos + 1, copy.deepcopy(patch["step"]))
        elif op == "remove":
            pos = index(patch["id"])
            if pos is None:
                missing(patch["id"])
            else:
                del steps[pos]
        elif op == "move":
            src, dst = index(patch["id"]), index(patch["after"])
            if src is None:
                missing(patch["id"])
            elif dst is None:
                missing(patch["after"])
            elif src == dst:
                errors.append(f"patch {i} ({op}): step {patch['id']} cannot move after itself")
            else:
                step = steps.pop(src)
                steps.insert(index(patch["after"]) + 1, step)
        elif op == "setCoords":
            pos = index(patch["id"])
            if pos is None:
                missing(patch["id"])
            else:
                steps[pos].update(mapId=patch["mapId"], x=patch["x"], y=patch["y"])
        else:
            errors.append(f"patch {i} ({op}): unknown op")
    return out, errors
