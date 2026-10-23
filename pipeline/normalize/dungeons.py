"""Dungeons on the zone maps: where each entrance is (the Map table's corpse point, where a ghost is sent back to
the instance) and which quests belong to it (from Lodestar's dungeon guides), for the site's map."""
from pipeline.config import DATA_BUILD
from pipeline.normalize.taxi import map_bounds, to_map, zone_for

# Map.InstanceType: 1 dungeon, 2 raid.
INSTANCE_KINDS = {"1": "dungeon", "2": "raid"}
# The zone each entrance is in. Zone map bounds are rectangles that overlap their neighbours, so the corpse point
# alone would put Wailing Caverns on the Durotar map; the zone's name picks the right one.
DUNGEON_ZONES: dict[int, str] = {
    33: "Silverpine Forest", 34: "Stormwind City", 36: "Westfall", 43: "The Barrens", 47: "The Barrens",
    48: "Ashenvale", 70: "Badlands", 90: "Dun Morogh", 109: "Swamp of Sorrows", 129: "The Barrens",
    189: "Tirisfal Glades", 209: "Tanaris", 229: "Burning Steppes", 230: "Searing Gorge", 289: "Western Plaguelands",
    329: "Eastern Plaguelands", 349: "Desolace", 389: "Orgrimmar", 429: "Feralas",
    249: "Dustwallow Marsh", 309: "Stranglethorn Vale", 409: "Searing Gorge", 469: "Burning Steppes",
    509: "Silithus", 531: "Silithus", 2784: "Ashenvale",
}


def build_dungeons(map_rows: list[dict], assignments: list[dict], uimaps: dict[int, str], parents: dict[int, int],
                   quests_by_dungeon: dict[int, dict[str, list[int]]],
                   attunements: dict[int, dict[str, list[int]]] | None = None, pois: list[dict] | None = None,
                   guide_entrances: dict[int, tuple[int, float, float]] | None = None) -> dict:
    """Dungeons and raids with a known entrance on a zone map, with their quests and attunement quests by faction.

    The entrance is the Map table's corpse point; for Forever's new dungeons, which have none, an AreaPOI of the same
    name (the world map's dungeon point) or the way in that a dungeon guide goes to (guide_entrances).
    """
    bounds = map_bounds(assignments, uimaps)
    poi_by_name = {p["Name_lang"]: p for p in pois or []}
    out = []
    for r in map_rows:
        kind = INSTANCE_KINDS.get(r["InstanceType"])
        if kind is None or r["MapName_lang"].startswith("<"):  # "<unused> Monastery"
            continue
        map_id = int(r["ID"])
        zone = DUNGEON_ZONES.get(map_id, r["MapName_lang"])
        xw, yw, continent = float(r["Corpse_0"]), float(r["Corpse_1"]), int(r["CorpseMapID"])
        place = None
        if continent >= 0 and (xw, yw) != (0, 0):
            ui = zone_for(zone, xw, yw, continent, bounds, uimaps, parents)
            place = (ui, *to_map(xw, yw, bounds[ui])) if ui is not None else None
        elif r["MapName_lang"] in poi_by_name:
            p = poi_by_name[r["MapName_lang"]]
            xw, yw, continent = float(p["Pos_0"]), float(p["Pos_1"]), int(p["ContinentID"])
            ui = zone_for(zone, xw, yw, continent, bounds, uimaps, parents)
            place = (ui, *to_map(xw, yw, bounds[ui])) if ui is not None else None
        elif guide_entrances and map_id in guide_entrances:
            place = guide_entrances[map_id]
        if place is None:
            continue
        ui, x, y = place
        out.append({"id": map_id, "name": r["MapName_lang"], "kind": kind, "uiMapId": ui, "x": round(x, 1),
                    "y": round(y, 1), "quests": quests_by_dungeon.get(map_id, {}),
                    "attunement": (attunements or {}).get(map_id, {})})
    return {"build": DATA_BUILD, "dungeons": sorted(out, key=lambda d: d["id"])}
