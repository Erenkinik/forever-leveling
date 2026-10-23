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


def test_parse_guide_reads_class_conditions_and_not_completed_is_no_prerequisite():
    g = parse_guide("""x
step
  only Shaman not completed(1516) not completed(1519) not haveq(1516)
  talk Boro##100
  accept Earth##10 |goto Zephras Isle 40.0,20.0
step
  only not completed(96627) not completed(96628)
  talk Aetheen##101
  accept Adventurer##11 |goto Zephras Isle 41.0,21.0
step
  only Hunter completed(10)
  talk Aetheen##101
  accept Hunt##12 |goto Zephras Isle 41.0,21.0
step
  only not Druid not Hunter not Paladin not Priest not Rogue not Shaman not Warlock not Warrior
  talk Belann##102
  accept Arcane##13 |goto Zephras Isle 42.0,22.0
""", MAPS)
    q = g["quests"]
    assert (q[10]["pre"], q[10]["class"]) == ([], 64)
    assert (q[11]["pre"], q[11]["class"]) == ([], None)
    assert (q[12]["pre"], q[12]["class"]) == ([10], 4)
    assert q[13]["class"] == 128  # every class it does not name: Mage


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


CLASS_MAPS = {"Dun Morogh": 1426, "Loch Modan": 1432, "Durotar": 1411}
CLASS_AREAS = {1426: 1, 1432: 38, 1411: 14}
# A made-up class guide: a quest pfQuest has (179) is not taken, the chain's quests are; a point the guide puts on
# the other faction's map is moved to where the quest is done.
CLASS_GUIDE = """ns:RegisterGuide("Class/Alliance/Shaman", {}, [[
step
  talk Sten Stoutarm##658
  accept Dwarven Outfitters##179 |goto Dun Morogh 29.93,71.2
step
  only not Human not NightElf not Skyborne Shaman
  talk Teo Hammerstorm##257446
  accept Call of Earth##94373 |goto Dun Morogh 28.79,66.18
step
  collect 2 Iceclaw Bear Pendant##264356 |q 94373 |goto Dun Morogh 26.84,79.92 |tip {dropsfrom}Frostmane Troll Whelp
step
  talk Teo Hammerstorm##257446
  turnin Call of Earth##94373 |goto Dun Morogh 28.79,66.18
step
  talk Minor Manifestation of Earth##5891
  turnin Call of Earth##94374 |goto Dun Morogh 24.84,61.86
step
  talk Braldir Ashmantle##257808
  accept Call of Fire##94466 |goto Loch Modan 32.17,65.97
step
  collect 1 Fire Tar##5026 |q 94466 |goto Durotar 54.94,26.74 |tip {dropsfrom}Razormane Geomancer
]])
"""


def test_class_guide_gives_the_class_chain(tmp_path):
    (tmp_path / "class" / "alliance").mkdir(parents=True)
    (tmp_path / "class" / "alliance" / "Shaman.lua").write_text(CLASS_GUIDE, encoding="utf-8")
    pf = load_lodestar(tmp_path, CLASS_MAPS, CLASS_AREAS)
    assert 179 not in pf.quests
    earth = pf.quests[94373]
    assert (earth["class"], earth["factions"], earth["lvl"], earth["min"]) == (64, ["Alliance"], 4, 4)
    assert earth["pre"] == [98581] and earth["obj"] == {"I": [264356]}
    assert pf.quests[94466]["pre"] == [94465]
    # the Fire Tar is got in Loch Modan, not where the guide's generator put it
    assert pf.units[-5026]["coords"] == [(35.6, 20.2, 38)]
    assert pf.units[-5026]["name"] == "Tunnel Rat Geomancer"
    # an NPC new in Forever keeps its id; a vanilla one gets a stand-in, so the vanilla quests keep pfQuest's place
    assert earth["start"] == {"U": [257446]}
    assert pf.quests[94466]["start"] == {"U": [257808]}
    assert pf.quests[94374]["end"] == {"U": [-10_005_891]} and 5891 not in pf.units
    assert pf.units[-10_005_891]["coords"] == [(24.84, 61.86, 1)]


def test_class_quest_at_an_object_gets_a_stand_in_npc(tmp_path):
    (tmp_path / "class" / "alliance").mkdir(parents=True)
    (tmp_path / "class" / "alliance" / "Shaman.lua").write_text("""ns:RegisterGuide("Class/Alliance/Shaman", {}, [[
step
  talk Braldir Ashmantle##257808
  accept Call of Fire##94467 |goto Loch Modan 32.17,65.97
step
  turnin Call of Fire##94467 |goto Durotar 38.96,58.22
]])
""", encoding="utf-8")
    pf = load_lodestar(tmp_path, CLASS_MAPS, CLASS_AREAS)
    assert pf.quests[94467]["end"] == {"U": [-10_061_934]}
    assert pf.units[-10_061_934] == {"name": "Brazier of the Dormant Flame", "coords": [(31.9, 64.5, 38)], "fac": None}


def test_merge_adds_stand_in_droppers_to_an_item_both_have():
    base = PfData(quests={}, units={}, objects={},
                  items={7: {"name": "Tar", "units": [9], "objects": [], "chances": {}}})
    extra = PfData(quests={}, units={}, objects={},
                   items={7: {"name": "Tar", "units": [-7], "objects": [], "chances": {}}})
    merged = merge(base, extra)
    assert merged.items[7]["units"] == [9, -7]
    assert base.items[7]["units"] == [9]  # base is not changed
