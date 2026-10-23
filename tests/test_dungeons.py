import csv
from pathlib import Path

from pipeline.export.site import route_dungeons
from pipeline.normalize.dungeons import build_dungeons

FIX = Path(__file__).parent / "fixtures" / "wago"
MAPS = {947: "Azeroth", 1415: "Eastern Kingdoms", 1429: "Elwynn Forest"}
PARENTS = {947: 0, 1415: 947, 1429: 1415}


def _rows(table):
    with open(FIX / f"{table}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _map_row(map_id, name, x, y, instance="1", continent="0"):
    return {"ID": str(map_id), "MapName_lang": name, "InstanceType": instance, "CorpseMapID": continent,
            "Corpse_0": str(x), "Corpse_1": str(y)}


def test_dungeon_entrances_land_on_their_zone_map_with_their_quests():
    rows = [
        _map_row(36, "Test Mine", -9460, 62),               # in Elwynn's bounds
        _map_row(37, "Far Keep", 5000, 5000),               # on no known zone map
        _map_row(38, "<unused> Hall", -9460, 62),           # unused
        _map_row(39, "Battleground", -9460, 62, instance="3"),
        _map_row(40, "No Entrance", 0, 0),
    ]
    doc = build_dungeons(rows, _rows("UiMapAssignment"), MAPS, PARENTS, {36: {"Alliance": [7, 8]}})
    assert doc["dungeons"] == [{"id": 36, "name": "Test Mine", "uiMapId": 1429, "x": 42.5, "y": 65.7,
                                "quests": {"Alliance": [7, 8]}}]


def test_route_dungeons_list_the_quests_the_route_can_take():
    def q(qid, **kw):
        return {"id": qid, "name": f"Q{qid}", "level": 20, "minLevel": 18, "races": None, "factions": None,
                "classes": None, "inForever": True,
                "start": {"type": "npc", "id": 9, "name": "Giver", "uiMapId": 1436, "x": 50.0, "y": 50.0}, **kw}
    quests = {1: q(1), 2: q(2, level=24), 3: q(3, factions=["Horde"]), 4: q(4, classes=["Shaman"])}
    dungeons = [{"id": 36, "name": "Deadmines", "uiMapId": 1436, "x": 38.0, "y": 77.0,
                 "quests": {"Alliance": [2, 1, 3, 4, 99]}},
                {"id": 33, "name": "Elsewhere", "uiMapId": 1421, "x": 1.0, "y": 1.0, "quests": {}}]
    route = {"race": "Human", "faction": "Alliance", "steps": [
        {"id": "accept-1", "type": "accept", "mapId": 1436, "x": 50, "y": 50, "questId": 1}]}
    out = route_dungeons(route, quests, dungeons, {1436: "Westfall"})
    assert [d["name"] for d in out] == ["Deadmines"]  # only entrances on the route's maps
    d = out[0]
    assert d["levels"] == [20, 24]
    assert [(e["questId"], e["step"], e["zoneName"]) for e in d["quests"]] == [
        (1, "accept-1", "Westfall"), (2, None, "Westfall")]  # Horde, Shaman and unknown quests left out
