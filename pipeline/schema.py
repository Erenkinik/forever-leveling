"""JSON schema validation for canonical quests and routes."""
import json
from typing import Literal

from jsonschema import Draft202012Validator

from pipeline.config import ROOT

_VALIDATORS: dict[str, Draft202012Validator] = {}
for _kind in ("quest", "route"):
    _schema = json.loads((ROOT / "schema" / f"{_kind}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(_schema)
    _VALIDATORS[_kind] = Draft202012Validator(_schema)


def validate(kind: Literal["quest", "route"], obj: dict) -> list[str]:
    """Return error messages (with JSON-pointer paths); empty list means valid."""
    if kind not in _VALIDATORS:
        raise ValueError(f"unknown schema kind: {kind!r}")
    errors = sorted(_VALIDATORS[kind].iter_errors(obj), key=lambda e: list(e.absolute_path))
    return [f"/{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors]
