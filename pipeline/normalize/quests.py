"""Build the canonical quest database from pfQuest, wago DB2 ids and manual entries."""
from pipeline.config import CLASS_BITS, DATA_BUILD, RACE_BITS, RACE_FACTION, SOURCE_LINEAGE
from pipeline.ingest.pfquest import PfData
from pipeline.normalize.kills import kill_plan
from pipeline.schema import validate

ALL_RACES = 255
_TRUSTED = {"blizzard-client", "vanilla-emu", "ingame"}
_TYPES = (("U", "npc"), ("O", "object"), ("I", "item"))  # precedence when several are present
# Sources that only confirm a quest exists and supply no values (docs/spike-wago.md).
PRESENCE_ONLY_SOURCES = frozenset({"wago-db2"})
_MANUAL_COMPARED = ("name", "level", "minLevel", "races", "prereqs")


def _names_from_mask(mask: int, bits: dict[str, int]) -> list[str]:
    """Names for the known bits, then "unknown-bit-<n>" for every other set bit."""
    names = [name for name, bit in bits.items() if mask & bit]
    known = 0
    for bit in bits.values():
        known |= bit
    rest = mask & ~known
    bit = 1
    while rest >= bit:
        if rest & bit:
            names.append(f"unknown-bit-{bit}")
        bit <<= 1
    return names


def races_from_mask(mask: int | None) -> list[str] | None:
    if not mask or mask == ALL_RACES:
        return None
    return _names_from_mask(mask, RACE_BITS)


def classes_from_mask(mask: int | None) -> list[str] | None:
    """pfQuest `class` mask -> class names; no mask means any class (None)."""
    if not mask:
        return None
    return _names_from_mask(mask, CLASS_BITS)


FACTIONS = ("Alliance", "Horde")
_FAC_CODES = {"A": {"Alliance"}, "H": {"Horde"}}  # pfQuest unit/object `fac`; "AH" or none = both


def factions_for(races: list[str] | None, endpoint_facs: list[str | None]) -> list[str] | None:
    """Factions that can do the quest: races mask ∩ start/end NPC or object faction.

    None means no restriction is known (both factions); [] means no faction can do both ends.
    """
    allowed = set(FACTIONS)
    if races is not None:
        known = {RACE_FACTION[r] for r in races if r in RACE_FACTION}
        if known:
            allowed &= known
    for fac in endpoint_facs:
        allowed &= _FAC_CODES.get(fac, set(FACTIONS))
    return None if allowed == set(FACTIONS) else [f for f in FACTIONS if f in allowed]


def _endpoint_fac(pf: PfData, raw: dict | None, point: dict) -> str | None:
    """pfQuest faction code for one quest end: the union over every NPC/object pfQuest lists for it.

    `raw` is None when a manual entry names the endpoint; then only that endpoint counts.
    """
    tables = {"npc": pf.units, "object": pf.objects}
    refs = [(type_, i) for key, type_ in _TYPES if type_ in tables for i in (raw or {}).get(key) or []]
    if raw is None or (point["type"], point["id"]) not in refs:
        refs = [(point["type"], point["id"])] if point["type"] in tables else []
    allowed: set[str] = set()
    for type_, i in refs:
        allowed |= _FAC_CODES.get(tables[type_].get(i, {}).get("fac"), set(FACTIONS))
    if not allowed:
        return None
    return {frozenset({"Alliance"}): "A", frozenset({"Horde"}): "H"}.get(frozenset(allowed), "AH")


def confidence_for(lineages: set[str], conflicts: list[str]) -> str:
    if "ingame" in lineages:
        return "verified-ingame"
    if len(lineages) >= 2 and not conflicts and lineages & _TRUSTED:
        return "cross-checked"
    return "unverified"


def _point(type_=None, id_=None, name=None, ui=None, x=None, y=None) -> dict:
    return {"type": type_, "id": id_, "name": name, "uiMapId": ui, "x": x, "y": y}


def _endpoint(raw: dict | None) -> tuple[str | None, int | None]:
    for key, type_ in _TYPES:
        ids = (raw or {}).get(key)
        if ids:
            return type_, ids[0]
    return None, None


def _is_multiple(raw: dict | None) -> bool:
    """True when pfQuest lists more than one distinct id or more than one type."""
    found = [(key, i) for key, _ in _TYPES for i in dict.fromkeys((raw or {}).get(key) or [])]
    return len(found) > 1


def _unit_zones(pf: PfData, ref: tuple[str | None, int | None]) -> set[int]:
    if ref[0] != "npc":
        return set()
    return {c[2] for c in pf.units.get(ref[1], {}).get("coords", [])}


def _build_point(pf: PfData, ref, other_zones: set[int], zone_to_uimap, conflicts: list[str], label: str) -> dict:
    type_, id_ = ref
    if type_ is None:
        return _point()
    if type_ != "npc":
        return _point(type_, id_)  # items/objects carry no coordinates
    unit = pf.units.get(id_, {})
    point = _point("npc", id_, unit.get("name"))
    coords = unit.get("coords", [])
    if not coords:
        conflicts.append(f"{label}.coords")
        return point
    chosen = next((c for c in coords if c[2] in other_zones), coords[0])
    ui = zone_to_uimap.get(chosen[2])
    if ui is None:
        conflicts.append(f"{label}.coords")
        return point
    point["x"], point["y"], point["uiMapId"] = chosen[0], chosen[1], ui
    return point


def _objectives(raw: dict | None) -> dict:
    raw = raw or {}
    return {
        out: list(dict.fromkeys(raw.get(key, [])))
        for out, key in (("units", "U"), ("items", "I"), ("objects", "O"))
    }


def _differs(field: str, ours, theirs) -> bool:
    if field == "prereqs":
        return sorted(ours or []) != sorted(theirs or [])
    return ours != theirs


def _record(qid, pf, forever_ids, zone_to_uimap, manual) -> dict:
    pq = pf.quests.get(qid)
    conflicts: list[str] = []
    sources: list[str] = []
    if qid in forever_ids:
        sources.append("wago-db2")
    rec = {
        "id": qid, "name": None, "level": None, "minLevel": None, "races": None, "classes": None, "prereqs": [],
        "start": _point(), "end": _point(), "objectives": _objectives(None), "kills": [],
    }
    if pq is not None:
        sources.append(pq.get("source", "pfquest"))  # "lodestar" for the Zephras Isle facts
        s_ref, e_ref = _endpoint(pq.get("start")), _endpoint(pq.get("end"))
        for label in ("start", "end"):
            if _is_multiple(pq.get(label)):
                conflicts.append(f"{label}.multiple")
        rec.update(
            name=pq.get("name"), level=pq.get("lvl"), minLevel=pq.get("min"),
            races=pq["races"] if "races" in pq else races_from_mask(pq.get("race")),
            classes=classes_from_mask(pq.get("class")),
            prereqs=list(pq.get("pre") or []),
            start=_build_point(pf, s_ref, _unit_zones(pf, e_ref), zone_to_uimap, conflicts, "start"),
            end=_build_point(pf, e_ref, _unit_zones(pf, s_ref), zone_to_uimap, conflicts, "end"),
            objectives=_objectives(pq.get("obj")),
            kills=kill_plan(pq, pf),
        )
    m = manual.get(qid)
    if m is not None:
        sources.append("wowhead-manual")
        for field in _MANUAL_COMPARED:
            if field not in m:
                continue
            if pq is not None and _differs(field, rec[field], m[field]):
                conflicts.append(field)
            rec[field] = m[field]
        for label in ("start", "end"):
            if label not in m:
                continue
            given = m[label] or {}
            changed = ("type" in given and given["type"] != rec[label]["type"]) or (
                "id" in given and given["id"] != rec[label]["id"]
            )
            if changed and rec[label]["type"] is not None:
                # A different endpoint: pfQuest's name and position belong to the old one.
                rec[label] = {**rec[label], "name": None, "uiMapId": None, "x": None, "y": None}
                if not all(given.get(k) is not None for k in ("x", "y", "uiMapId")):
                    conflicts.append(f"{label}.coords")
            if pq is not None:
                if "type" in given or "id" in given:
                    theirs = (given.get("type", rec[label]["type"]), given.get("id", rec[label]["id"]))
                    if theirs != (rec[label]["type"], rec[label]["id"]):
                        conflicts.append(label)
                if all(k in given for k in ("x", "y", "uiMapId")):
                    conflicts[:] = [c for c in conflicts if c != f"{label}.coords"]
            rec[label] = {**rec[label], **{k: v for k, v in given.items() if k in rec[label]}}
    raw_ends = {
        label: None if m is not None and ({"type", "id"} & set(m.get(label) or {})) else (pq or {}).get(label)
        for label in ("start", "end")
    }
    rec["factions"] = factions_for(
        rec["races"], [_endpoint_fac(pf, raw_ends[label], rec[label]) for label in ("start", "end")]
    )
    if pq is not None and "factions" in pq:  # a source that knows the quest's faction (Lodestar's guides)
        rec["factions"] = pq["factions"]
    lineages = sorted({SOURCE_LINEAGE[s] for s in sources})
    conflicts = sorted(set(conflicts))
    in_forever = qid in forever_ids
    value_lineages = {SOURCE_LINEAGE[s] for s in sources if s not in PRESENCE_ONLY_SOURCES}
    confidence = confidence_for(value_lineages, conflicts)
    if "wowhead-manual" in sources and confidence == "cross-checked":
        confidence = "unverified"  # spec 8.2: manual entries never count as cross-checked
    rec.update(
        inForever=in_forever, sources=sources, lineages=lineages, conflicts=conflicts,
        confidence=confidence,
        seenInBuild=DATA_BUILD if in_forever else None,
    )
    return rec


def _no_objectives(q: dict) -> bool:
    return not any(q["objectives"].values())


def prereqs_are_alternatives(alternatives: list[dict]) -> bool:
    """True when a quest's prereqs are alternatives (any one is enough), not all required.

    Two patterns: versions of one quest (all share a name, e.g. the orc and troll "Vile Familiars"), and
    breadcrumbs from different places to the same NPC (no objectives, NPC starts on different maps, one end NPC,
    e.g. "The New Horde" from Orgrimmar and "Your Place In The World" in Durotar, both to Gornek).
    """
    if len(alternatives) < 2:
        return False
    if len({q["name"] for q in alternatives}) == 1:
        return True
    starts = [q["start"] for q in alternatives]
    return (all(_no_objectives(q) for q in alternatives)
            and all(s["type"] == "npc" and s["uiMapId"] is not None for s in starts)
            and len({s["uiMapId"] for s in starts}) == len(starts)
            and len({(q["end"]["type"], q["end"]["id"]) for q in alternatives}) == 1)


def build_canonical(
    pf: PfData, forever_ids: frozenset[int], zone_to_uimap: dict[int, int], manual: dict[int, dict]
) -> list[dict]:
    ids = sorted(set(pf.quests) | set(manual) | set(forever_ids))
    records = [_record(q, pf, forever_ids, zone_to_uimap, manual) for q in ids]
    by_id = {r["id"]: r for r in records}
    for r in records:
        known = [by_id[p] for p in r["prereqs"] if p in by_id]
        r["prereqsAny"] = len(known) == len(r["prereqs"]) and prereqs_are_alternatives(known)
    return records


def validation_errors(records: list[dict]) -> list[str]:
    return [f"quest {r['id']}: {e}" for r in records for e in validate("quest", r)]
