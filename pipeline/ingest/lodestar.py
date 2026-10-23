"""Facts from Lodestar's (MIT) Zephras Isle leveling guides, the Skyborne start that pfQuest does not have.

Only facts are taken: quest, NPC, object and item ids and names, map coordinates, objective counts, which quest a
step needs done ("only completed(...)") and the minimum level it states. The guides' notes and tips (their text)
are not used. The result has pfQuest's shape (PfData), so normalize merges it like pfQuest; pfQuest wins where both
have a quest.
"""
import http.client
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from pipeline.ingest.pfquest import PfData

REPO = "danielcosta42/lodestar"
COMMIT = "5c5fa2346981eefe3f368f325b5ef80e2270d9de"  # pinned: the routes change with the guides
GUIDES = {
    "Alliance": "Guides/Leveling/Alliance/Zephras_Isle_5-12.lua",
    "Horde": "Guides/Leveling/Horde/Zephras_Isle_5-12.lua",
}
# The guides start at level 1 and end at 12; quest levels are not in them, so they are spread over this range
# in guide order (an estimate).
LEVELS = (1, 12)

_REF = r"(?:(\d+) )?(.+?)##(-?\d+)"  # "[count] Name##id"
_GOTO = re.compile(r"\|goto (.+?) (\d+(?:\.\d+)?),(\d+(?:\.\d+)?)")
_QUEST = re.compile(r"\|q (\d+)")
_DROPS = re.compile(r"\{dropsfrom\}([^|]+)")


def fetch_lodestar(raw_dir: Path, opener: Callable = urllib.request.urlopen) -> None:
    """Download the pinned guide files into raw_dir/lodestar; never leaves a partial file."""
    base = Path(raw_dir) / "lodestar"
    base.mkdir(parents=True, exist_ok=True)
    for faction, path in GUIDES.items():
        dest = base / f"zephras-{faction.lower()}.lua"
        part = dest.with_name(dest.name + ".part")
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{path}"
        try:
            with opener(url, timeout=60) as resp:
                part.write_bytes(resp.read())
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            part.unlink(missing_ok=True)
            raise RuntimeError(f"failed to download {path}: {exc}") from exc
        part.replace(dest)


def _goto(line: str, map_ids: dict[str, int]) -> tuple[int, float, float] | None:
    m = _GOTO.search(line)
    if not m or m.group(1) not in map_ids:
        return None
    return map_ids[m.group(1)], float(m.group(2)), float(m.group(3))


def parse_guide(text: str, map_ids: dict[str, int]) -> dict:
    """One guide's facts: {"quests": {id: {...}}, "units", "objects", "items", "order": [quest ids]}.

    map_ids maps a guide's zone name ("Zephras Isle") to its UiMap id; points on other maps are left out.
    """
    quests: dict[int, dict] = {}
    units: dict[int, dict] = {}
    objects: dict[int, dict] = {}
    items: dict[int, dict] = {}
    order: list[int] = []

    def quest(qid: int) -> dict:
        if qid not in quests:
            quests[qid] = {"start": None, "end": None, "U": {}, "I": {}, "O": {}, "pre": [], "min": None,
                           "skyborne": False}
            order.append(qid)
        return quests[qid]

    def place(table: dict, eid: int, name: str, point) -> None:
        rec = table.setdefault(eid, {"name": name, "points": []})
        if point and point not in rec["points"]:
            rec["points"].append(point)

    for block in text.split("\nstep\n")[1:]:
        lines = [ln.strip() for ln in block.splitlines()]
        only = " ".join(ln for ln in lines if ln.startswith("only "))
        needs = [int(q) for group in re.findall(r"completed\(([\d, ]+)\)", only) for q in re.findall(r"\d+", group)]
        min_level = max((int(n) for n in re.findall(r"level>=(\d+)", only)), default=None)
        npc = None
        for ln in lines:
            verb, _, rest = ln.partition(" ")
            point = _goto(ln, map_ids)
            ref = re.match(_REF, rest.split(" |")[0]) if rest else None
            if not ref:
                continue
            count, name, eid = (int(ref.group(1)) if ref.group(1) else None), ref.group(2), int(ref.group(3))
            qm = _QUEST.search(ln)
            if verb == "talk":
                npc = (eid, name)
                place(units, eid, name, point)
            elif verb in ("accept", "turnin"):
                q = quest(eid)
                q["name"] = name
                if npc:
                    q["start" if verb == "accept" else "end"] = npc[0]
                    place(units, npc[0], npc[1], point)
                if verb == "accept":
                    q["pre"] = sorted(set(q["pre"]) | set(needs))
                    q["min"] = min_level
                    q["skyborne"] = bool(re.search(r"\bSkyborne\b", only))  # "only Skyborne": the race's own
            elif verb == "kill" and qm:
                quest(int(qm.group(1)))["U"][eid] = count
                place(units, eid, name, point)
            elif verb == "click" and qm:
                quest(int(qm.group(1)))["O"][eid] = count
                place(objects, eid, name, point)
            elif verb in ("collect", "use") and qm:
                quest(int(qm.group(1)))["I"][eid] = count if verb == "collect" else None
                drops = _DROPS.search(ln)
                item = items.setdefault(eid, {"name": name, "droppers": set(), "points": []})
                if drops:
                    item["droppers"].update(d.strip() for d in drops.group(1).split(","))
                if point and point not in item["points"]:
                    item["points"].append(point)
    return {"quests": quests, "units": units, "objects": objects, "items": items, "order": order}


def load_lodestar(src_dir: Path, map_ids: dict[str, int], uimap_to_area: dict[int, int]) -> PfData:
    """Both factions' guide facts as PfData (pfQuest's shape); an empty PfData when the files are absent.

    Coordinates become pfQuest's (x, y, AreaID) through uimap_to_area. An item without a known dropper on the map
    gets a stand-in unit (id: minus the item id) where the guide collects it, so the route has a place to go.
    """
    guides = {}
    for faction in GUIDES:
        path = Path(src_dir) / f"zephras-{faction.lower()}.lua"
        if path.is_file():
            guides[faction] = parse_guide(path.read_text(encoding="utf-8"), map_ids)
    quests: dict[int, dict] = {}
    units: dict[int, dict] = {}
    objects: dict[int, dict] = {}
    items: dict[int, dict] = {}
    factions: dict[int, set[str]] = {}

    def coords(points):
        return [(x, y, uimap_to_area[m]) for m, x, y in points if m in uimap_to_area]

    for faction, g in guides.items():
        lo, hi = LEVELS
        n = max(1, len(g["order"]) - 1)
        for i, qid in enumerate(g["order"]):
            q = g["quests"][qid]
            factions.setdefault(qid, set()).add(faction)
            if qid in quests:
                continue
            text = "; ".join(f"{c} {g['units'].get(u, g['items'].get(u, {})).get('name')}"
                             for kind in ("U", "I") for u, c in q[kind].items() if c)
            quests[qid] = {
                "name": q.get("name"), "lvl": round(lo + (hi - lo) * i / n), "min": q["min"] or lo,
                "pre": q["pre"], "objectiveText": text or None,
                "start": {"U": [q["start"]]} if q["start"] else {},
                "end": {"U": [q["end"]]} if q["end"] else {},
                "obj": {k: list(q[k]) for k in ("U", "I", "O") if q[k]},
                "source": "lodestar",
                # Zephras Isle is the Skyborne start, and the guide marks the race's own quests elsewhere.
                "races": ["Skyborne"] if q["skyborne"] else None,
            }
        for uid, u in g["units"].items():
            rec = units.setdefault(uid, {"name": u["name"], "coords": [], "fac": None})
            rec["coords"] += [c for c in coords(u["points"]) if c not in rec["coords"]]
        for oid, o in g["objects"].items():
            rec = objects.setdefault(oid, {"name": o["name"], "coords": [], "fac": None})
            rec["coords"] += [c for c in coords(o["points"]) if c not in rec["coords"]]
        by_name = {u["name"]: uid for uid, u in g["units"].items()}
        for iid, it in g["items"].items():
            known = sorted(by_name[d] for d in it["droppers"] if d in by_name)
            if not known and it["points"]:
                stand_in = -iid
                units.setdefault(stand_in, {"name": ", ".join(sorted(it["droppers"])) or it["name"], "coords": [],
                                            "fac": None})["coords"] += coords(it["points"])
                known = [stand_in]
            rec = items.setdefault(iid, {"name": it["name"], "units": [], "objects": [], "chances": {}})
            rec["units"] = sorted(set(rec["units"]) | set(known))
    # A quest in one faction's guide only is that faction's; in both, anyone's (None).
    for qid, q in quests.items():
        q["factions"] = None if len(factions[qid]) > 1 else sorted(factions[qid])
    return PfData(quests=quests, units=units, objects=objects, items=items)


def merge(base: PfData, extra: PfData) -> PfData:
    """`base` (pfQuest) with the quests, units, objects and items it lacks taken from `extra`."""
    return PfData(
        quests={**extra.quests, **base.quests},
        units={**extra.units, **base.units},
        objects={**extra.objects, **base.objects},
        items={**extra.items, **base.items},
    )
