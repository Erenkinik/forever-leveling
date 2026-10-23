"""Dungeons on the zone maps: where each entrance is (the Map table's corpse point, where a ghost is sent back to
the instance) and which quests belong to it (from Lodestar's dungeon guides), for the site's map."""
from pipeline.config import DATA_BUILD
from pipeline.normalize.taxi import map_bounds, to_map, zone_for

DUNGEON_INSTANCE_TYPE = "1"
# The zone each entrance is in. Zone map bounds are rectangles that overlap their neighbours, so the corpse point
# alone would put Wailing Caverns on the Durotar map; the zone's name picks the right one.
DUNGEON_ZONES: dict[int, str] = {
    33: "Silverpine Forest", 34: "Stormwind City", 36: "Westfall", 43: "The Barrens", 47: "The Barrens",
    48: "Ashenvale", 70: "Badlands", 90: "Dun Morogh", 109: "Swamp of Sorrows", 129: "The Barrens",
    189: "Tirisfal Glades", 209: "Tanaris", 229: "Burning Steppes", 230: "Searing Gorge", 289: "Western Plaguelands",
    329: "Eastern Plaguelands", 349: "Desolace", 389: "Orgrimmar", 429: "Feralas",
}


def build_dungeons(map_rows: list[dict], assignments: list[dict], uimaps: dict[int, str], parents: dict[int, int],
                   quests_by_dungeon: dict[int, dict[str, list[int]]]) -> dict:
    """Dungeons with a known entrance on a zone map, with their quests by faction ({} when none are known)."""
    bounds = map_bounds(assignments, uimaps)
    out = []
    for r in map_rows:
        if (r["InstanceType"] != DUNGEON_INSTANCE_TYPE or int(r["CorpseMapID"]) < 0
                or r["MapName_lang"].startswith("<")):  # "<unused> Monastery"
            continue
        xw, yw = float(r["Corpse_0"]), float(r["Corpse_1"])
        if xw == 0 and yw == 0:
            continue
        zone = DUNGEON_ZONES.get(int(r["ID"]), r["MapName_lang"])
        ui = zone_for(zone, xw, yw, int(r["CorpseMapID"]), bounds, uimaps, parents)
        if ui is None:
            continue
        x, y = to_map(xw, yw, bounds[ui])
        map_id = int(r["ID"])
        out.append({"id": map_id, "name": r["MapName_lang"], "uiMapId": ui, "x": round(x, 1), "y": round(y, 1),
                    "quests": quests_by_dungeon.get(map_id, {})})
    return {"build": DATA_BUILD, "dungeons": sorted(out, key=lambda d: d["id"])}
