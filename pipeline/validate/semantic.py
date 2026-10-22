"""Semantic route validation and the release-tier gate."""
from collections.abc import Callable
from dataclasses import dataclass

from pipeline.schema import validate as schema_validate

LEVEL_SLACK = 3
TRUSTED = ("cross-checked", "verified-ingame")


@dataclass(frozen=True)
class Issue:
    rule: str
    stepId: str | None
    message: str


def check_route(
    route: dict,
    quests: dict[int, dict],
    known_maps: frozenset[int],
    xp_reaches_target: Callable[[dict], bool] | None = None,
    levels: dict[str, int] | None = None,
) -> list[Issue]:
    """Semantic rules over a route. `levels` (step id -> estimated level, from
    pipeline.generate.xpsim.estimate_levels) drives the over-level rule; without it the level only
    follows grind steps."""
    errors = schema_validate("route", route)
    if errors:
        # Semantic rules assume a structurally valid route.
        return [Issue("schema", None, e) for e in errors]

    issues: list[Issue] = []
    full = route["releaseTier"] == "full"
    level = route["levelRange"][0]
    seen_ids: set[str] = set()
    accepted: dict[int, str] = {}  # questId -> accept stepId
    turned_in: set[int] = set()

    for step in route["steps"]:
        sid, kind, qid = step["id"], step["type"], step.get("questId")
        quest = quests.get(qid) if qid is not None else None

        if sid in seen_ids:
            issues.append(Issue("duplicate-step-id", sid, f"step id {sid!r} is used more than once"))
        seen_ids.add(sid)

        if step["mapId"] not in known_maps:
            issues.append(Issue("unknown-map", sid, f"mapId {step['mapId']} is not a known UiMap"))

        if levels is not None:
            level = levels.get(sid, level)
        elif kind == "grind":
            level = step["untilLevel"]

        if qid is not None:
            if quest is None:
                # Cannot judge level or confidence; never pass silently.
                issues.append(Issue("unknown-quest", sid, f"quest {qid} is not in the canonical data"))
            elif quest.get("inForever") is False:
                issues.append(Issue("not-in-forever", sid, f"quest {qid} is not in Forever"))
            elif quest["minLevel"] is None:
                issues.append(Issue("level-unknown", sid, f"quest {qid} level unknown"))
            elif kind != "gap" and quest["minLevel"] > level + LEVEL_SLACK:  # a gap quest is not taken
                issues.append(Issue(
                    "over-level", sid,
                    f"quest {qid} needs level {quest['minLevel']}, estimated level is {level}",
                ))

        if kind == "accept":
            if quest is not None:
                prereqs = quest.get("prereqs", [])
                if quest.get("prereqsAny") and prereqs:
                    # Alternatives: any one turned in is enough.
                    if not any(pre in turned_in for pre in prereqs):
                        issues.append(Issue(
                            "prereq-not-done", sid,
                            f"quest {qid} requires one of quests {', '.join(map(str, prereqs))} turned in first",
                        ))
                else:
                    for pre in prereqs:
                        if pre not in turned_in:
                            issues.append(Issue(
                                "prereq-not-done", sid, f"quest {qid} requires quest {pre} turned in first"
                            ))
            accepted.setdefault(qid, sid)
        elif kind == "complete":
            if qid not in accepted:
                issues.append(Issue("complete-before-accept", sid, f"quest {qid} completed before it is accepted"))
        elif kind == "turnin":
            if qid not in accepted:
                issues.append(Issue("turnin-before-accept", sid, f"quest {qid} turned in before it is accepted"))
            if qid in accepted:
                turned_in.add(qid)

        if full:
            if kind == "gap":
                issues.append(Issue("tier-full-requires-cross-checked", sid, "gap step in a full-tier route"))
            elif step["confidence"] not in TRUSTED:
                issues.append(Issue(
                    "tier-full-requires-cross-checked", sid, f"step confidence is {step['confidence']!r}"
                ))
            elif quest is not None and quest["confidence"] not in TRUSTED:
                issues.append(Issue(
                    "tier-full-requires-cross-checked", sid,
                    f"quest {qid} confidence is {quest['confidence']!r}",
                ))
            elif quest is None and qid is not None:
                issues.append(Issue(
                    "tier-full-requires-cross-checked", sid, f"quest {qid} confidence unknown"
                ))

    for qid, sid in accepted.items():
        if qid not in turned_in:
            issues.append(Issue("accepted-never-closed", sid, f"quest {qid} is accepted but never turned in"))

    if xp_reaches_target is not None and not xp_reaches_target(route):
        issues.append(Issue("xp-target", None, "route does not reach its target level by XP"))
    return issues
