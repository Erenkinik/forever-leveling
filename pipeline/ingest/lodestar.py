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

from pipeline.config import CLASS_BITS
from pipeline.ingest.pfquest import PfData

REPO = "danielcosta42/lodestar"
COMMIT = "5c5fa2346981eefe3f368f325b5ef80e2270d9de"  # pinned: the routes change with the guides
GUIDES = {
    "Alliance": "Guides/Leveling/Alliance/Zephras_Isle_5-12.lua",
    "Horde": "Guides/Leveling/Horde/Zephras_Isle_5-12.lua",
}
# Dungeon guides (Guides/Dungeons/<Faction>/<file>.lua) by the dungeon's Map id: only which quests belong to a
# dungeon is taken from them. Stockade has no Horde guide and Ragefire Chasm no Alliance one.
DUNGEON_GUIDES: dict[int, str] = {
    33: "Shadowfang_Keep", 34: "The_Stockade", 36: "The_Deadmines", 43: "Wailing_Caverns", 47: "Razorfen_Kraul",
    48: "Blackfathom_Deeps", 70: "Uldaman", 90: "Gnomeregan", 109: "The_Temple_of_AtalHakkar",
    129: "Razorfen_Downs", 189: "Scarlet_Monastery", 209: "ZulFarrak", 229: "Blackrock_Spire",
    230: "Blackrock_Depths", 289: "Scholomance", 329: "Stratholme", 349: "Maraudon", 389: "Ragefire_Chasm",
    429: "Dire_Maul",
    # raids
    249: "Onyxias_Lair", 309: "ZulGurub", 409: "Molten_Core", 469: "Blackwing_Lair", 509: "Ruins_of_AhnQiraj",
    531: "Temple_of_AhnQiraj",
    # new in Forever
    2959: "City_of_Dalaran", 2998: "Excavation_Site_Wetlands", 2999: "Ruins_of_Lordaeron", 3065: "The_Hall_of_Thanes",
}
NO_GUIDE = {("Horde", 34), ("Alliance", 389), ("Horde", 3065), ("Alliance", 2999)}
# The dungeons new in Forever, whose quests pfQuest does not have.
NEW_DUNGEONS = (2959, 2998, 2999, 3065)
# Attunement guides (Guides/Attunements/<path>.lua) by the Map id they open; a path under a faction folder is that
# faction's, the others are both factions'.
ATTUNEMENT_GUIDES: dict[int, list[str]] = {
    349: ["Maraudon_-_Scepter_of_Celebras"],
    249: ["Alliance/Onyxias_Lair_Alliance", "Horde/Onyxias_Lair_Horde"],
    409: ["Molten_Core_-_Attunement_to_the_Core"],
    469: ["Blackwing_Lair_-_Blackhands_Command"],
    229: ["Upper_Blackrock_Spire_-_Seal_of_Ascension"],
    531: ["AhnQiraj_-_Scepter_of_the_Shifting_Sands"],
}
# Class guides (Guides/Class/<Faction>/<Class>.lua) by faction. Only the quests in CLASS_QUESTS are taken from
# them: the class chains new in Forever, which pfQuest does not have.
CLASS_GUIDES: dict[str, tuple[str, ...]] = {"Alliance": ("Shaman",)}
CLASS_MASKS = {"Shaman": 64}
# Forever's Alliance (Dwarf) shaman totem chains: quest id -> (level, minimum level, the quest before it). The
# levels are Forever's own (forever.warcraftdb.com); the Water chain's are not published there, so they are
# estimated from the chain's minimum level 20.
CLASS_QUESTS: dict[int, tuple[int, int, int | None]] = {
    # Earth: Archaic Rune, then three Call of Earth
    98581: (1, 1, None), 94373: (4, 4, 98581), 94374: (4, 4, 94373), 94375: (4, 4, 94374),
    # Fire
    94449: (10, 10, None), 94465: (11, 10, 94449), 94466: (14, 10, 94465), 94467: (14, 10, 94466),
    94468: (14, 10, 94467),
    # Water
    94494: (20, 20, None), 94495: (20, 20, 94494), 94497: (21, 20, 94495), 94499: (21, 20, 94497),
    94500: (21, 20, 94499), 94501: (22, 20, 94500), 94502: (23, 20, 94501), 94503: (23, 20, 94502),
    94505: (23, 20, 94503),
    # Air
    94789: (30, 30, None),
}
# NPC ids from here up are new in Forever; a class chain's quest giver below it gets a stand-in id (_class_npc),
# above any item stand-in (minus the item id).
FOREVER_NPCS = 200_000
CLASS_NPC_BASE = 10_000_000
# Quests a class chain hands in at, or takes from, an object (the guide has no NPC for them): quest id -> (which
# end, the object's name, its zone, x, y). The route needs an NPC there, so the object gets a stand-in unit
# (minus CLASS_NPC_BASE plus the object id) where it stands.
CLASS_OBJECT_ENDS: dict[int, tuple[str, str, str, float, float]] = {
    94467: ("end", "Brazier of the Dormant Flame", "Loch Modan", 31.9, 64.5),
    94468: ("start", "Brazier of the Dormant Flame", "Loch Modan", 31.9, 64.5),
    94502: ("end", "Forgotten Shrine", "Westfall", 45.57, 59.88),
    94503: ("start", "Forgotten Shrine", "Westfall", 45.57, 59.88),
}
OBJECT_IDS = {"Brazier of the Dormant Flame": 61934, "Forgotten Shrine": 619896}
# The class guide is generated, and for items and NPCs the vanilla Horde quests also have it puts the point on the
# other faction's map. (id on the line, the guide's zone) -> where it is in Forever ("Zone x,y") and, for an item,
# who drops it there; from the public Forever guides (Warcraft Tavern's "Dwarf Shaman Totem Quests").
CLASS_POINT_FIXES: dict[tuple[int, str], tuple[str, str | None]] = {
    (5026, "The Barrens"): ("Loch Modan 35.6,20.2", "Tunnel Rat Geomancer"),  # Fire Tar
    (5026, "Durotar"): ("Loch Modan 35.6,20.2", "Tunnel Rat Geomancer"),
    (6652, "Durotar"): ("Loch Modan 31.0,77.4", "Stonesplinter Seer"),  # Reagent Pouch
    (6655, "Durotar"): ("Loch Modan 31.9,64.5", "Minor Manifestation of Fire"),  # Glowing Ember
    (94467, "Durotar"): ("Loch Modan 31.9,64.5", None),  # the Brazier of the Dormant Flame
    (61934, "Durotar"): ("Loch Modan 31.9,64.5", None),
    (94468, "Durotar"): ("Loch Modan 31.9,64.5", None),
    (7812, "Silverpine Forest"): ("Westfall 47.5,60.4", "Corrupt Minor Manifestation of Water"),  # Bracers
    (94503, "Silverpine Forest"): ("Westfall 47.5,60.4", None),  # the Minor Manifestation of Water
    (94505, "Silverpine Forest"): ("Westfall 47.5,60.4", None),
    (265748, "Wetlands"): ("Redridge Mountains 73.7,61.6", None),  # Full Red Waterskin: Stonewatch Falls
    (265773, "Wetlands"): ("Ashenvale 37.0,51.6", None),  # Full Blue Waterskin: the waters of Astranaar
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
    for faction in GUIDES:
        for map_id, stem in DUNGEON_GUIDES.items():
            if (faction, map_id) in NO_GUIDE:
                continue
            dest = base / "dungeons" / faction.lower() / f"{stem}.lua"
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + ".part")
            url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/Guides/Dungeons/{faction}/{stem}.lua"
            try:
                with opener(url, timeout=60) as resp:
                    part.write_bytes(resp.read())
            except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
                part.unlink(missing_ok=True)
                raise RuntimeError(f"failed to download {stem} ({faction}): {exc}") from exc
            part.replace(dest)
    for faction, classes in CLASS_GUIDES.items():
        for cls in classes:
            dest = base / "class" / faction.lower() / f"{cls}.lua"
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + ".part")
            url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/Guides/Class/{faction}/{cls}.lua"
            try:
                with opener(url, timeout=60) as resp:
                    part.write_bytes(resp.read())
            except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
                part.unlink(missing_ok=True)
                raise RuntimeError(f"failed to download class guide {cls} ({faction}): {exc}") from exc
            part.replace(dest)
    for paths in ATTUNEMENT_GUIDES.values():
        for rel in paths:
            dest = base / "attunements" / f"{rel}.lua"
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + ".part")
            url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/Guides/Attunements/{rel}.lua"
            try:
                with opener(url, timeout=60) as resp:
                    part.write_bytes(resp.read())
            except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
                part.unlink(missing_ok=True)
                raise RuntimeError(f"failed to download attunement {rel}: {exc}") from exc
            part.replace(dest)


def load_attunements(src_dir: Path) -> dict[int, dict[str, list[int]]]:
    """Map id -> faction -> the quests of its attunement (both factions for a guide outside a faction folder)."""
    out: dict[int, dict[str, list[int]]] = {}
    for map_id, paths in ATTUNEMENT_GUIDES.items():
        for rel in paths:
            path = Path(src_dir) / "attunements" / f"{rel}.lua"
            if not path.is_file():
                continue
            owner = rel.split("/")[0] if "/" in rel else None
            for faction in GUIDES:
                if owner in (None, faction):
                    have = out.setdefault(map_id, {}).setdefault(faction, [])
                    have += [q for q in dungeon_quests(path.read_text(encoding="utf-8")) if q not in have]
    return out


def guide_entrances(src_dir: Path, map_ids: dict[str, int]) -> dict[int, tuple[int, float, float]]:
    """Map id -> (UiMap id, x, y) of a dungeon guide's step that only goes somewhere ("goto Zone x,y"): the way
    in, for dungeons whose entrance the game data does not give."""
    out: dict[int, tuple[int, float, float]] = {}
    for map_id, stem in DUNGEON_GUIDES.items():
        for faction in GUIDES:
            path = Path(src_dir) / "dungeons" / faction.lower() / f"{stem}.lua"
            if map_id in out or not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                # a step line "goto Zone x,y" (not a "|goto" on a quest line)
                if line.strip().startswith("goto ") and (point := _goto("|" + line.strip(), map_ids)):
                    out[map_id] = point
                    break
    return out


def dungeon_quests(text: str) -> list[int]:
    """The quests a dungeon guide accepts, in guide order."""
    return list(dict.fromkeys(int(q) for q in re.findall(r"^\s*accept .+?##(\d+)", text, re.M)))


def load_dungeon_quests(src_dir: Path) -> dict[int, dict[str, list[int]]]:
    """Dungeon Map id -> faction -> its quests, from the downloaded dungeon guides (absent files are skipped)."""
    out: dict[int, dict[str, list[int]]] = {}
    for map_id, stem in DUNGEON_GUIDES.items():
        for faction in GUIDES:
            path = Path(src_dir) / "dungeons" / faction.lower() / f"{stem}.lua"
            if path.is_file():
                out.setdefault(map_id, {})[faction] = dungeon_quests(path.read_text(encoding="utf-8"))
    return out


def _goto(line: str, map_ids: dict[str, int]) -> tuple[int, float, float] | None:
    m = _GOTO.search(line)
    if not m or m.group(1) not in map_ids:
        return None
    return map_ids[m.group(1)], float(m.group(2)), float(m.group(3))


def _class_npc(uid: int | None) -> int | None:
    """The unit id a class chain's quest giver gets: its own for an NPC new in Forever, else a stand-in (minus
    CLASS_NPC_BASE plus the id), because Forever put the vanilla NPC somewhere else and the vanilla quests keep
    pfQuest's place for it."""
    return uid if uid is None or uid >= FOREVER_NPCS else -(CLASS_NPC_BASE + uid)


def _fix_class_points(text: str) -> str:
    """The class guide with CLASS_POINT_FIXES applied: a line naming the id with a goto in the given zone gets the
    fixed goto, and for an item its Forever dropper."""
    out = []
    for line in text.splitlines():
        for (eid, zone), (goto, dropper) in CLASS_POINT_FIXES.items():
            if f"##{eid} " in line and f"|goto {zone} " in line:
                line = re.sub(r"\|goto [^|]+?(?= \||$)", f"|goto {goto}", line)
                if dropper:
                    line = re.sub(r"\{dropsfrom\}[^|]+", f"{{dropsfrom}}{dropper}", line)
        out.append(line)
    return "\n".join(out)


def _class_mask(only: str) -> int | None:
    """The classes a step's "only" condition allows, as pfQuest's class mask: "only Shaman" is Shaman's bit, "only not
    Druid not Hunter ..." every class it does not name; None when it names no class."""
    named = {m.group(2): bool(m.group(1)) for m in re.finditer(rf"\b(not )?({'|'.join(CLASS_BITS)})\b", only)}
    allowed = [c for c, negated in named.items() if not negated]
    if allowed:
        return sum(CLASS_BITS[c] for c in allowed)
    if named:
        return sum(bit for c, bit in CLASS_BITS.items() if c not in named)
    return None


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
                           "skyborne": False, "class": None}
            order.append(qid)
        return quests[qid]

    def place(table: dict, eid: int, name: str, point) -> None:
        rec = table.setdefault(eid, {"name": name, "points": []})
        if point and point not in rec["points"]:
            rec["points"].append(point)

    for block in text.split("\nstep\n")[1:]:
        lines = [ln.strip() for ln in block.splitlines()]
        only = " ".join(ln for ln in lines if ln.startswith("only "))
        # "not completed(...)" is the opposite of a prerequisite: the step is for those who did not do it.
        needs = [int(q) for group in re.findall(r"(?<!not )completed\(([\d, ]+)\)", only)
                 for q in re.findall(r"\d+", group)]
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
                    q["class"] = _class_mask(only)
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
                **({"class": q["class"]} if q["class"] else {}),
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
    # Forever's new dungeons: their quests (name, giver and where) from the dungeon guides. The guides give no level,
    # so it stays unknown: the quests show in the dungeon's panel but no route takes them.
    for map_id in NEW_DUNGEONS:
        for faction in GUIDES:
            path = Path(src_dir) / "dungeons" / faction.lower() / f"{DUNGEON_GUIDES[map_id]}.lua"
            if not path.is_file():
                continue
            g = parse_guide(path.read_text(encoding="utf-8"), map_ids)
            for qid in g["order"]:
                q = g["quests"][qid]
                factions.setdefault(qid, set()).add(faction)
                if qid in quests or not q["start"]:
                    continue
                quests[qid] = {"name": q.get("name"), "lvl": None, "min": None, "pre": q["pre"],
                               "objectiveText": None, "start": {"U": [q["start"]]},
                               "end": {"U": [q["end"]]} if q["end"] else {}, "obj": {}, "source": "lodestar",
                               "races": None}
            for uid, u in g["units"].items():
                rec = units.setdefault(uid, {"name": u["name"], "coords": [], "fac": None})
                rec["coords"] += [c for c in coords(u["points"]) if c not in rec["coords"]]
    # The class chains new in Forever, from the class guides: only the quests in CLASS_QUESTS, with their levels and
    # chain order from there (the guides do not say which quest comes first).
    for faction, classes in CLASS_GUIDES.items():
        for cls in classes:
            path = Path(src_dir) / "class" / faction.lower() / f"{cls}.lua"
            if not path.is_file():
                continue
            g = parse_guide(_fix_class_points(path.read_text(encoding="utf-8")), map_ids)
            for qid in g["order"]:
                if qid not in CLASS_QUESTS or qid in quests:
                    continue
                q = g["quests"][qid]
                lvl, min_level, before = CLASS_QUESTS[qid]
                start, end = (_class_npc(q[k]) for k in ("start", "end"))
                if qid in CLASS_OBJECT_ENDS:
                    side, name, zone, x, y = CLASS_OBJECT_ENDS[qid]
                    stand_in = -(CLASS_NPC_BASE + OBJECT_IDS[name])
                    rec = units.setdefault(stand_in, {"name": name, "coords": [], "fac": None})
                    rec["coords"] += [c for c in coords([(map_ids[zone], x, y)] if zone in map_ids else [])
                                      if c not in rec["coords"]]
                    start, end = (stand_in, end) if side == "start" else (start, stand_in)
                factions.setdefault(qid, set()).add(faction)
                text = "; ".join(f"{c} {g['items'].get(i, {}).get('name')}" for i, c in q["I"].items() if c)
                quests[qid] = {
                    "name": q.get("name"), "lvl": lvl, "min": min_level, "pre": [before] if before else [],
                    "objectiveText": text or None, "class": CLASS_MASKS[cls],
                    "start": {"U": [start]} if start else {}, "end": {"U": [end]} if end else {},
                    "obj": {k: list(q[k]) for k in ("U", "I", "O") if q[k]}, "source": "lodestar", "races": None,
                }
            taken = {e for qid in quests if qid in CLASS_QUESTS for k in ("U", "I", "O")
                     for e in g["quests"].get(qid, {}).get(k, {})}
            ends = {e for qid in quests if qid in CLASS_QUESTS for e in (g["quests"].get(qid, {}).get("start"),
                                                                        g["quests"].get(qid, {}).get("end"))}
            for uid, u in g["units"].items():
                if uid in taken or uid in ends:
                    rec = units.setdefault(_class_npc(uid) if uid in ends else uid, {"name": u["name"], "coords": [], "fac": None})
                    rec["coords"] += [c for c in coords(u["points"]) if c not in rec["coords"]]
            for oid, o in g["objects"].items():
                if oid in taken:
                    rec = objects.setdefault(oid, {"name": o["name"], "coords": [], "fac": None})
                    rec["coords"] += [c for c in coords(o["points"]) if c not in rec["coords"]]
            for iid, it in g["items"].items():
                if iid not in taken:
                    continue
                rec = items.setdefault(iid, {"name": it["name"], "units": [], "objects": [], "chances": {}})
                if it["points"]:  # the guide's droppers are named only: a stand-in where it is got
                    units.setdefault(-iid, {"name": ", ".join(sorted(it["droppers"])) or it["name"], "coords": [],
                                            "fac": None})["coords"] += coords(it["points"])
                    rec["units"] = sorted(set(rec["units"]) | {-iid})
    # A quest in one faction's guide only is that faction's; in both, anyone's (None).
    for qid, q in quests.items():
        q["factions"] = None if len(factions[qid]) > 1 else sorted(factions[qid])
    return PfData(quests=quests, units=units, objects=objects, items=items)


def merge(base: PfData, extra: PfData) -> PfData:
    """`base` (pfQuest) with the quests, units, objects and items it lacks taken from `extra`; an item both have
    also gets extra's stand-in droppers (where a Forever quest gets it)."""
    items = {**extra.items, **base.items}
    for iid, it in base.items.items():
        stand_ins = [d for d in extra.items.get(iid, {}).get("units", []) if d < 0 and d not in it.get("units", [])]
        if stand_ins:
            items[iid] = {**it, "units": it.get("units", []) + stand_ins}
    return PfData(
        quests={**extra.quests, **base.quests},
        units={**extra.units, **base.units},
        objects={**extra.objects, **base.objects},
        items=items,
    )
