"""CI snapshot tests over committed route files. They never read raw/."""
import json
import re

import pytest

from pipeline.__main__ import _json_text
from pipeline.canonical import load_questxp_canonical, load_spawns_canonical, load_uimaps_canonical
from pipeline.config import DATA_DIR, ROOT
from pipeline.export.lua import to_lua
from pipeline.export.site import to_site_json
from pipeline.generate.config import BETA_BLOCKING_RULES
from pipeline.generate.xpsim import estimate_levels
from pipeline.validate.semantic import check_route

ROUTES_DIR = DATA_DIR / "routes"


def _route_paths():
    paths = sorted(p for p in ROUTES_DIR.glob("*.json") if not p.name.endswith(".generated.json"))
    assert paths, f"no committed routes under {ROUTES_DIR}"
    return paths


def _quests():
    return {q["id"]: q for q in json.loads((DATA_DIR / "canonical" / "quests.json").read_text(encoding="utf-8"))}


def test_committed_routes_pass_beta_blocking_rules():
    quests = _quests()
    known_maps = frozenset(load_uimaps_canonical(DATA_DIR))
    for path in _route_paths():
        route = json.loads(path.read_text(encoding="utf-8"))
        levels = estimate_levels(route, quests, load_questxp_canonical(DATA_DIR))
        issues = check_route(route, quests, known_maps, levels=levels)
        blocking = [i for i in issues if i.rule in BETA_BLOCKING_RULES]
        assert blocking == [], f"{path.name}: {blocking}"


def test_committed_exports_match_routes():
    import pipeline.__main__ as cli

    quests = _quests()
    uimaps = load_uimaps_canonical(DATA_DIR)
    spawns = load_spawns_canonical(DATA_DIR)
    xp_table = load_questxp_canonical(DATA_DIR)
    for path in _route_paths():
        route = json.loads(path.read_text(encoding="utf-8"))
        site = ROOT / "site" / "src" / "data" / f"{path.stem}.json"
        lua = ROOT / "addon" / "ForeverXP" / "Data" / f"{path.stem}.lua"
        expected = to_site_json(route, quests, spawns, uimaps, estimate_levels(route, quests, xp_table),
                                cli._item_icons(ROOT))
        assert site.read_bytes() == _json_text(expected).encode("utf-8"), site
        assert lua.read_bytes() == to_lua(route).encode("utf-8"), lua


def test_human_route_shape():
    route = json.loads((ROUTES_DIR / "human.json").read_text(encoding="utf-8"))
    steps = route["steps"]
    assert steps[0]["type"] == "accept"
    assert steps[0]["mapId"] == 1429
    assert route["releaseTier"] == "beta"
    assert any(s["type"] == "travel" for s in steps)
    report = (DATA_DIR / "reports" / "route-human.md").read_text(encoding="utf-8")
    match = re.search(r"^- Boşluk \(gap\) adımı: (\d+)$", report, re.MULTILINE)
    assert match, "gap count line missing from report"
    assert sum(1 for s in steps if s["type"] == "gap") == int(match.group(1))


def test_committed_routes_are_regenerable(monkeypatch, tmp_path, capsys):
    """generate --check over every zone order: catches generator or canonical drift without raw/."""
    import pipeline.__main__ as cli

    monkeypatch.setattr(cli, "RAW_DIR", tmp_path / "no-raw")  # generate must not need raw/
    orders = sorted((DATA_DIR / "zone-order").glob("*.yaml"))
    assert orders, "no zone orders under data/zone-order"
    for order in orders:
        assert cli.main(["generate", order.stem, "--check"]) == 0, capsys.readouterr().err


def test_committed_routes_only_use_quests_of_their_faction():
    quests = _quests()
    for path in _route_paths():
        route = json.loads(path.read_text(encoding="utf-8"))
        wrong = sorted({
            s["questId"] for s in route["steps"]
            if s.get("questId") in quests and quests[s["questId"]]["factions"] is not None
            and route["faction"] not in quests[s["questId"]]["factions"]
        })
        assert wrong == [], f"{path.name}: quests of another faction {wrong}"


def test_committed_routes_have_no_over_level_with_shared_estimate():
    """The validator replays the generator's own level model, so this mainly guards override-added steps."""
    quests = _quests()
    known_maps = frozenset(load_uimaps_canonical(DATA_DIR))
    xp_table = load_questxp_canonical(DATA_DIR)
    for path in _route_paths():
        route = json.loads(path.read_text(encoding="utf-8"))
        issues = check_route(route, quests, known_maps, levels=estimate_levels(route, quests, xp_table))
        over = [i for i in issues if i.rule == "over-level"]
        assert over == [], f"{path.name}: {over[:3]}"


def test_every_route_map_has_its_image_or_a_recorded_absence():
    import pipeline.__main__ as cli

    assert cli.main(["maps", "--check"]) == 0
