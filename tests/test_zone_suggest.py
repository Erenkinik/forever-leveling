import pytest

from pipeline.generate.zone_suggest import ZoneStat, render_yaml, suggest_zones

EK, KAL = 1415, 1414
NAMES = {
    EK: "Eastern Kingdoms", KAL: "Kalimdor",
    1: "Elwynn Forest", 2: "Westfall", 3: "Darkshore", 4: "Redridge Mountains", 5: "Ashenvale",
    6: "Stormwind City", 7: "Dun Morogh", 8: "Tiny Zone", 9: "Thousand Needles", 10: "Searing Gorge",
}
PARENTS = {1: EK, 2: EK, 3: KAL, 4: EK, 5: KAL, 6: EK, 7: EK, 8: EK, 9: KAL, 10: EK}


def _quests(spec):
    """spec: {map_id: [levels]} -> canonical-like quest dicts open to every race and faction."""
    out, qid = {}, 0
    for map_id, levels in spec.items():
        for level in levels:
            qid += 1
            out[qid] = {
                "id": qid, "level": level, "minLevel": max(1, level - 3), "races": None, "classes": None,
                "factions": None, "prereqs": [], "inForever": True, "start": {"uiMapId": map_id},
            }
    return out


def test_start_zone_first_then_by_median_level_with_continent_grouping():
    quests = _quests({
        1: [5] * 10, 2: [14] * 10, 3: [16] * 10, 4: [18] * 10, 5: [24] * 10,
    })
    stats = suggest_zones(quests, NAMES, PARENTS, "Human", "Alliance")
    assert [s.name for s in stats] == [
        "Elwynn Forest", "Westfall", "Redridge Mountains", "Darkshore", "Ashenvale",
    ]
    assert stats[1] == ZoneStat(2, "Westfall", 14, 10, "Eastern Kingdoms")


def test_continent_switch_costs_levels_and_zones_left_behind_are_dropped():
    names = {**NAMES, 11: "Teldrassil"}
    parents = {**PARENTS, 11: KAL}
    quests = _quests({11: [6] * 10, 2: [13] * 10, 3: [17] * 10, 9: [24] * 10, 4: [18] * 10})
    stats = suggest_zones(quests, names, parents, "Night Elf", "Alliance")
    # Westfall (13, other continent) costs 13 + 5 > Darkshore 17; once level 17 is reached Westfall is
    # more than ZONE_BEHIND below it and is dropped. Redridge (18 + 5 = 23) still beats Needles (24).
    assert [s.name for s in stats] == ["Teldrassil", "Darkshore", "Redridge Mountains", "Thousand Needles"]


def test_cities_other_start_zones_small_and_high_zones_are_left_out():
    quests = _quests({
        1: [5] * 10, 6: [20] * 20, 7: [6] * 20, 8: [15] * 9, 9: [30] * 10, 10: [29] * 10,
    })
    names = [s.name for s in suggest_zones(quests, NAMES, PARENTS, "Human", "Alliance")]
    assert names == ["Elwynn Forest", "Searing Gorge"]


def test_other_faction_and_class_quests_do_not_count():
    quests = _quests({1: [5] * 10, 2: [14] * 10})
    for qid in (11, 12):
        quests[qid]["factions"] = ["Horde"]
    quests[13]["classes"] = ["Mage"]
    assert [s.name for s in suggest_zones(quests, NAMES, PARENTS, "Human", "Alliance")] == ["Elwynn Forest"]


def test_unknown_race_is_an_error():
    with pytest.raises(ValueError, match="no start zone"):
        suggest_zones(_quests({1: [5] * 10}), NAMES, PARENTS, "Skyborne", "Alliance")


def test_start_zone_without_enough_quests_is_an_error():
    with pytest.raises(ValueError, match="Elwynn Forest"):
        suggest_zones(_quests({1: [5] * 3, 2: [14] * 10}), NAMES, PARENTS, "Human", "Alliance")


def test_render_yaml_is_a_loadable_unreviewed_draft(tmp_path):
    from pipeline.generate.zone_order import load_zone_order

    stats = [ZoneStat(1, "Elwynn Forest", 5, 10, "Eastern Kingdoms"), ZoneStat(3, "Darkshore", 16.5, 12, "Kalimdor")]
    text = render_yaml("human", "Human", "Alliance", stats)
    assert "reviewed: false" in text and "median 16.5" in text
    path = tmp_path / "human.yaml"
    path.write_text(text, encoding="utf-8")
    order = load_zone_order(path, NAMES)
    assert order.zones == [1, 3] and order.reviewed is False and order.faction == "Alliance"
