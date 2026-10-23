import pytest

from pipeline.canonical import load_uimaps_canonical
from pipeline.config import DATA_DIR
from pipeline.generate.zone_order import load_zone_order

HUMAN = DATA_DIR / "zone-order" / "human.yaml"
UIMAPS = {1: "Alpha", 2: "Beta", 3: "Dup", 4: "Dup"}


def _write(tmp_path, text):
    p = tmp_path / "order.yaml"
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


def test_human_zone_order_loads():
    order = load_zone_order(HUMAN, load_uimaps_canonical())
    assert order.route == "human"
    assert order.race == "Human"
    assert order.faction == "Alliance"
    assert order.reviewed is False
    assert order.zones[0] == 1429
    assert order.zones[1] == 1436
    assert len(order.zones) == 11  # up to level 35


def test_unknown_zone_name_rejected(tmp_path):
    p = _write(tmp_path, "route: t\nrace: Human\nfaction: Alliance\nreviewed: false\nzones: [Alpha, Nowhere]\n")
    with pytest.raises(ValueError, match="Nowhere"):
        load_zone_order(p, UIMAPS)


def test_ambiguous_zone_name_rejected(tmp_path):
    p = _write(tmp_path, "route: t\nrace: Human\nfaction: Alliance\nreviewed: false\nzones: [Dup]\n")
    with pytest.raises(ValueError, match="Dup"):
        load_zone_order(p, UIMAPS)


def test_duplicate_zone_rejected(tmp_path):
    p = _write(tmp_path, "route: t\nrace: Human\nfaction: Alliance\nreviewed: false\nzones: [Alpha, Beta, Alpha]\n")
    with pytest.raises(ValueError, match="Alpha"):
        load_zone_order(p, UIMAPS)


def test_schema_rejects_missing_faction(tmp_path):
    p = _write(tmp_path, "route: t\nrace: Human\nreviewed: false\nzones: [Alpha]\n")
    with pytest.raises(ValueError, match="faction"):
        load_zone_order(p, UIMAPS)


def test_invalid_yaml_is_a_value_error_naming_the_file(tmp_path):
    p = _write(tmp_path, "route: t\nzones: [Alpha\n")
    with pytest.raises(ValueError, match=r"^order\.yaml: invalid YAML: "):
        load_zone_order(p, UIMAPS)


def test_a_name_several_maps_share_means_the_one_with_a_parent(tmp_path):
    p = _write(tmp_path, "route: t\nrace: Skyborne\nfaction: Alliance\nreviewed: false\nzones: [Zephras Isle]\n")
    maps = {2521: "Zephras Isle", 2665: "Zephras Isle"}
    assert load_zone_order(p, maps, {2521: 947, 2665: 0}).zones == [2521]
    with pytest.raises(ValueError, match="several"):
        load_zone_order(p, maps)
