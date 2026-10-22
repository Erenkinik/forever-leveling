"""Crosscheck report: confidence counts and the manual-entry backlog."""
from collections import Counter
from dataclasses import dataclass


@dataclass
class Summary:
    total: int
    by_confidence: dict[str, int]
    not_in_forever: int
    needs_manual: list[int]
    conflicts: dict[str, int]
    in_scope: int
    in_scope_known: int
    in_scope_unknown_level: int
    needs_manual_unknown_level: int


def summarize(quests: list[dict], level_max: int = 30) -> Summary:
    by_confidence: Counter = Counter()
    conflicts: Counter = Counter()
    needs_manual: list[int] = []
    not_in_forever = 0
    in_scope = 0
    in_scope_known = 0
    in_scope_unknown_level = 0
    needs_manual_unknown_level = 0
    for quest in quests:
        by_confidence[quest["confidence"]] += 1
        conflicts.update(quest["conflicts"])
        if not quest["inForever"]:
            not_in_forever += 1
            continue
        min_level = quest["minLevel"]
        if min_level is None:
            in_scope_unknown_level += 1
        elif min_level <= level_max:
            in_scope_known += 1
        if min_level is None or min_level <= level_max:
            in_scope += 1
        if set(quest["sources"]) == {"wago-db2"}:
            needs_manual.append(quest["id"])
            if min_level is None:
                needs_manual_unknown_level += 1
    return Summary(
        total=len(quests),
        by_confidence=dict(by_confidence),
        not_in_forever=not_in_forever,
        needs_manual=sorted(needs_manual),
        conflicts=dict(conflicts),
        in_scope=in_scope,
        in_scope_known=in_scope_known,
        in_scope_unknown_level=in_scope_unknown_level,
        needs_manual_unknown_level=needs_manual_unknown_level,
    )


def render_markdown(s: Summary, build: str) -> str:
    lines = [
        f"# Crosscheck report (build {build})",
        "",
        f"- total quests: {s.total}",
        f"- not in Forever: {s.not_in_forever}",
        f"- inForever, level known and within range: {s.in_scope_known}",
        f"- inForever, level unknown (upper bound: some may be outside the level range): {s.in_scope_unknown_level}",
        f"- in_scope total (known + unknown level, upper bound): {s.in_scope}",
        f"- needs manual entry: {len(s.needs_manual)}",
        f"- needs manual entry, level unknown (upper bound: some may be outside the level range): "
        f"{s.needs_manual_unknown_level}",
        "",
        "## Confidence",
        "",
        "| confidence | count |",
        "|---|---|",
    ]
    for key, count in sorted(s.by_confidence.items()):
        lines.append(f"| {key} | {count} |")
    lines += ["", "## Conflicts", "", "| field | count |", "|---|---|"]
    for key, count in sorted(s.conflicts.items()):
        lines.append(f"| {key} | {count} |")
    lines += ["", "## Needs manual entry (quest ids)", ""]
    lines.append(", ".join(str(i) for i in s.needs_manual) if s.needs_manual else "none")
    return "\n".join(lines) + "\n"
