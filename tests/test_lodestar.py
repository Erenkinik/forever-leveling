from pipeline.ingest.lodestar import load_lodestar, merge, parse_guide
from pipeline.ingest.pfquest import PfData

MAPS = {"Zephras Isle": 2521, "Stormwind City": 1453}
AREAS = {2521: 16593, 1453: 1519}

# A made-up guide in Lodestar's format: the parser keeps ids, names, coordinates, counts and conditions only.
GUIDE = """ns:RegisterGuide("Leveling/Alliance/Test", {}, [[
step
  only level>=1
  talk Giver##100
  accept First##1 |goto Zephras Isle 40.0,20.0
step
  only haveq(1)
  note Some advice that is not taken.
  kill Wolf##200 |q 1 |goto Zephras Isle 45.0,25.0
  collect 6 Pelt##300 |q 1 |goto Zephras Isle 46.0,26.0 |tip {dropsfrom}Wolf
  collect 2 Shard##301 |q 1 |goto Zephras Isle 47.0,27.0 |tip {dropsfrom}Crystal Golem
  click Totem##400 |q 1 |goto Zephras Isle 48.0,28.0
step
  talk Taker##101
  turnin First##1 |goto Zephras Isle 41.0,21.0
step
  only completed(1) level>=3
  talk Taker##101
  accept Second##2 |goto Zephras Isle 41.0,21.0
step
  only Skyborne
  talk King##102
  accept Royal##3 |goto Stormwind City 80.0,38.0
]])
"""


def test_parse_guide_keeps_the_facts():
    g = parse_guide(GUIDE, MAPS)
    assert g["order"] == [1, 2, 3]
    first = g["quests"][1]
    assert (first["name"], first["start"], first["end"], first["min"], first["pre"]) == ("First", 100, 101, 1, [])
    assert first["U"] == {200: None} and first["I"] == {300: 6, 301: 2} and first["O"] == {400: None}
    assert g["quests"][2]["pre"] == [1] and g["quests"][2]["min"] == 3
    assert g["quests"][3]["skyborne"] and not first["skyborne"]
    assert g["units"][200]["points"] == [(2521, 45.0, 25.0)]
    assert g["items"][300]["droppers"] == {"Wolf"}


def test_load_lodestar_gives_pfquest_shaped_data(tmp_path):
    (tmp_path / "zephras-alliance.lua").write_text(GUIDE, encoding="utf-8")
    pf = load_lodestar(tmp_path, MAPS, AREAS)
    q1 = pf.quests[1]
    assert q1["source"] == "lodestar" and q1["factions"] == ["Alliance"] and q1["races"] is None
    assert q1["obj"] == {"U": [200], "I": [300, 301], "O": [400]}
    assert q1["objectiveText"] == "6 Pelt; 2 Shard"
    assert pf.quests[3]["races"] == ["Skyborne"]
    assert pf.units[200]["coords"] == [(45.0, 25.0, 16593)]
    assert pf.items[300]["units"] == [200]  # dropped by a mob the guide names and places
    assert pf.items[301]["units"] == [-301]  # no such mob: a stand-in where the guide collects it
    assert pf.units[-301] == {"name": "Crystal Golem", "coords": [(47.0, 27.0, 16593)], "fac": None}
    assert pf.quests[1]["lvl"] < pf.quests[3]["lvl"]  # levels spread over the guide in order
    assert load_lodestar(tmp_path / "missing", MAPS, AREAS) == PfData(quests={}, units={}, objects={}, items={})


def test_merge_keeps_pfquest_where_both_have_a_quest():
    base = PfData(quests={1: {"name": "pf"}}, units={}, objects={}, items={})
    extra = PfData(quests={1: {"name": "lode"}, 2: {"name": "new"}}, units={5: {}}, objects={}, items={})
    merged = merge(base, extra)
    assert merged.quests == {1: {"name": "pf"}, 2: {"name": "new"}} and 5 in merged.units
