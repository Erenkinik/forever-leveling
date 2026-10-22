import pytest

from pipeline.ingest.pfquest import PfData
from pipeline.normalize.kills import kill_plan, objective_count, unit_level


@pytest.mark.parametrize("text, name, count", [
    ("Kill 10 Kobold Vermin, then return to Marshal McBride.", "Kobold Vermin", 10),
    ("Bring 8 Red Burlap Bandanas to Deputy Willem.", "Red Burlap Bandana", 8),
    ("Bring 4 Chunks of Boar Meat to Auntie Bernice.", "Chunk of Boar Meat", 4),
    ("Chef Breanna wants five pieces of Tough Condor Meat.", "Tough Condor Meat", 5),
    ("Kill 7 Tidehunters, 7 Warriors and 9 Oracles.", "Murloc Oracle", 9),
    ("Kill 15 Defias Highwaymen and 5 Defias Pathstalkers.", "Defias Highwayman", 15),
    ("Kill Garrick Padfoot and bring his head to Deputy Willem.", "Garrick Padfoot", 1),  # no number: one
    ("Kill 12 Bluegill Murlocs. Slay Gobbler and take his head.", "Gobbler", 1),  # named without a number
    ("Gather 10 Lean Wolf Flanks and the herbs.", "Stormwind Seasoning Herbs", None),
    ("Bring 6000 gold.", "Gold", None),  # not an objective count
    (None, "Kobold Vermin", None),
])
def test_objective_count_reads_how_many_the_text_asks_for(text, name, count):
    assert objective_count(text, name) == count


def test_unit_level_is_the_mean_of_a_range():
    assert unit_level("1-2") == 1.5
    assert unit_level("12") == 12.0
    assert unit_level(None) is None


def test_kill_plan_lists_counts_drop_chances_and_mob_levels():
    pf = PfData(
        quests={},
        units={6: {"name": "Kobold Vermin", "lvl": "1-2"}, 38: {"name": "Defias Thug", "lvl": "3"},
               40: {"name": "Kobold Miner", "lvl": "5"}},
        objects={},
        items={752: {"name": "Red Burlap Bandana", "units": [38, 40], "objects": [], "chances": {38: 80, 40: 10}},
               99: {"name": "Shiny Rock", "units": [], "objects": [7], "chances": {}}},
    )
    pq = {"obj": {"U": [6], "I": [752, 99]}, "objectiveText": "Kill 10 Kobold Vermin, bring 8 Red Burlap Bandanas "
                                                             "and a Shiny Rock."}
    assert kill_plan(pq, pf) == [
        {"kind": "kill", "id": 6, "count": 10, "chance": None, "level": 1.5},
        {"kind": "collect", "id": 752, "count": 8, "chance": 80.0, "level": 3.0},  # the best dropper
        {"kind": "collect", "id": 99, "count": 1, "chance": 0.0, "level": None},  # only from objects: no kills
    ]
    assert kill_plan({}, pf) == []
