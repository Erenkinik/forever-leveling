"""Canonical data must validate in CI. No skip path: missing data is a failure."""
import json

from pipeline.config import ROOT, SOURCE_LINEAGE
from pipeline.schema import validate

QUESTS = ROOT / "data" / "canonical" / "quests.json"


def _has_forbidden_key(value) -> bool:
    if isinstance(value, dict):
        return any(k in ("D", "O") or _has_forbidden_key(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_has_forbidden_key(v) for v in value)
    return False


def test_canonical_data_valid():
    assert QUESTS.is_file(), f"missing canonical data: {QUESTS}"
    quests = json.loads(QUESTS.read_text(encoding="utf-8"))
    assert quests, "quests.json is empty"
    problems = []
    for q in quests:
        qid = q.get("id")
        problems += [f"{qid}: {e}" for e in validate("quest", q)]
        bad = set(q.get("sources", [])) - set(SOURCE_LINEAGE)
        if bad:
            problems.append(f"{qid}: unknown sources {sorted(bad)}")
        if _has_forbidden_key(q):
            problems.append(f"{qid}: forbidden D/O key")
    assert not problems, f"{len(problems)} problems, first 10: {problems[:10]}"
