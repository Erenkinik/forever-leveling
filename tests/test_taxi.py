import csv
from pathlib import Path

import pytest

from pipeline.normalize.taxi import build_taxi, map_bounds, to_map, to_world

FIX = Path(__file__).parent / "fixtures" / "wago"
MAPS = {947: "Azeroth", 1415: "Eastern Kingdoms", 1429: "Elwynn Forest"}
PARENTS = {947: 0, 1415: 947, 1429: 1415}


def _rows(table):
    with open(FIX / f"{table}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_map_coordinates_round_trip_through_world_yards():
    b = map_bounds(_rows("UiMapAssignment"), MAPS)[1429]
    assert b == [-10254.166015625, -1935.4166259766, -7939.5830078125, 1535.4166259766, 0]
    x, y = to_map(-9460, 62, b)
    assert (round(x, 1), round(y, 1)) == (42.5, 65.7)
    assert to_world(x, y, b) == pytest.approx((-9460, 62))


def test_build_taxi_keeps_faction_nodes_on_their_zone_map_and_their_flights():
    taxi = build_taxi(_rows("TaxiNodes"), _rows("TaxiPath"), _rows("UiMapAssignment"), MAPS, PARENTS)
    assert list(taxi["nodes"]) == ["90", "91"]  # the boat (no faction flag) and the retired zzOLD node are left out
    goldshire = taxi["nodes"]["90"]
    assert goldshire == {"name": "Goldshire, Elwynn", "factions": ["Alliance"], "uiMapId": 1429, "x": 42.5,
                         "y": 65.7, "continent": 0, "world": [-9460.0, 62.0]}
    assert taxi["paths"] == [[90, 91], [91, 90]]  # the flight to the dropped boat node goes too
    assert list(taxi["bounds"]) == ["1429"]
