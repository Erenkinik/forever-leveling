"""Build the canonical quest database from pfQuest, wago DB2 ids and manual entries."""
from pipeline.config import DATA_BUILD, RACE_BITS, SOURCE_LINEAGE
from pipeline.ingest.pfquest import PfData
from pipeline.schema import validate

ALL_RACES = 255
_TRUSTED = {"blizzard-client", "vanilla-emu", "ingame"}
_TYPES = (("U", "npc"), ("O", "object"), ("I", "item"))  # precedence when several are present
_MANUAL_COMPARED = ("name", "level", "minLevel", "races", "prereqs")


def races_from_mask(mask: int | None) -> list[str] | None:
    if not mask or mask == ALL_RACES:
        return None
    races = [name for name, bit in RACE_BITS.items() if mask & bit]
    known = 0
    for bit in RACE_BITS.values():
        known |= bit
    rest = mask & ~known
    bit = 1
    while rest >= bit:
        if rest & bit:
            races.append(f"unknown-bit-{bit}")
        bit <<= 1
    return races


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
    point["x"], point["y"] = chosen[0], chosen[1]
    ui = zone_to_uimap.get(chosen[2])
    if ui is None:
        conflicts.append(f"{label}.coords")
    point["uiMapId"] = ui
    return point


def _objectives(raw: dict | None) -> dict:
    raw = raw or {}
    return {
        out: list(dict.fromkeys(raw.get(key, [])))
        for out, key in (("units", "U"), ("items", "I"), ("objects", "O"))
    }


def _manual_point(raw: dict | None) -> dict:
    raw = raw or {}
    return _point(*(raw.get(k) for k in ("type", "id", "name", "uiMapId", "x", "y")))


def _record(qid, pf, forever_ids, zone_to_uimap, manual) -> dict:
    pq = pf.quests.get(qid)
    conflicts: list[str] = []
    sources: list[str] = []
    if qid in forever_ids:
        sources.append("wago-db2")
    rec = {
        "id": qid, "name": None, "level": None, "minLevel": None, "races": None, "prereqs": [],
        "start": _point(), "end": _point(), "objectives": _objectives(None),
    }
    if pq is not None:
        sources.append("pfquest")
        s_ref, e_ref = _endpoint(pq.get("start")), _endpoint(pq.get("end"))
        rec.update(
            name=pq.get("name"), level=pq.get("lvl"), minLevel=pq.get("min"),
            races=races_from_mask(pq.get("race")), prereqs=list(pq.get("pre") or []),
            start=_build_point(pf, s_ref, _unit_zones(pf, e_ref), zone_to_uimap, conflicts, "start"),
            end=_build_point(pf, e_ref, _unit_zones(pf, s_ref), zone_to_uimap, conflicts, "end"),
            objectives=_objectives(pq.get("obj")),
        )
    m = manual.get(qid)
    if m is not None:
        sources.append("wowhead-manual")
        for field in _MANUAL_COMPARED:
            if field not in m:
                continue
            if pq is not None and rec[field] != m[field]:
                conflicts.append(field)
            rec[field] = m[field]
        for label in ("start", "end"):
            if label in m:
                theirs = _manual_point(m[label])
                if pq is not None and (rec[label]["type"], rec[label]["id"]) != (theirs["type"], theirs["id"]):
                    conflicts.append(label)
                if pq is not None:  # manual point replaces pfQuest's, so its coords problems no longer apply
                    conflicts[:] = [c for c in conflicts if c != f"{label}.coords"]
                rec[label] = theirs
    lineages = sorted({SOURCE_LINEAGE[s] for s in sources})
    conflicts = sorted(set(conflicts))
    in_forever = qid in forever_ids
    rec.update(
        inForever=in_forever, sources=sources, lineages=lineages, conflicts=conflicts,
        confidence=confidence_for(set(lineages), conflicts),
        verifiedBuild=DATA_BUILD if in_forever else None,
    )
    return rec


def build_canonical(
    pf: PfData, forever_ids: frozenset[int], zone_to_uimap: dict[int, int], manual: dict[int, dict]
) -> list[dict]:
    ids = sorted(set(pf.quests) | set(manual) | set(forever_ids))
    return [_record(q, pf, forever_ids, zone_to_uimap, manual) for q in ids]


def validation_errors(records: list[dict]) -> list[str]:
    return [f"quest {r['id']}: {e}" for r in records for e in validate("quest", r)]
