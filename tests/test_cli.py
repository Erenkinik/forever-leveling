import json
import shutil
from pathlib import Path

import pytest

import pipeline.__main__ as cli
from pipeline.config import DATA_BUILD

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated RAW_DIR / DATA_DIR populated from the test fixtures."""
    raw, data = tmp_path / "raw", tmp_path / "data"
    shutil.copytree(FIX / "pfquest", raw / "pfquest")
    shutil.copytree(FIX / "wago", raw / "wago" / DATA_BUILD)
    (data / "manual").mkdir(parents=True)
    shutil.copy(FIX / "manual" / "quests.yaml", data / "manual" / "quests.yaml")
    monkeypatch.setattr(cli, "RAW_DIR", raw)
    monkeypatch.setattr(cli, "DATA_DIR", data)
    return raw, data


def test_normalize_then_check_is_up_to_date(env, capsys):
    _, data = env
    assert cli.main(["normalize"]) == 0
    out = data / "canonical" / "quests.json"
    assert b"\r\n" not in out.read_bytes()
    capsys.readouterr()
    assert cli.main(["normalize", "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_check_detects_drift_and_never_writes(env, capsys):
    _, data = env
    assert cli.main(["normalize"]) == 0
    out = data / "canonical" / "quests.json"
    records = json.loads(out.read_text(encoding="utf-8"))
    records[0]["name"] = "tampered"
    out.write_text(json.dumps(records), encoding="utf-8")
    before = out.read_bytes()
    assert cli.main(["normalize", "--check"]) == 1
    assert "out of date" in capsys.readouterr().err
    assert out.read_bytes() == before


def test_check_without_committed_file_fails_without_writing(env, capsys):
    _, data = env
    assert cli.main(["normalize", "--check"]) == 1
    assert "missing canonical quests" in capsys.readouterr().err
    assert not (data / "canonical").exists()


def test_check_without_raw_is_a_clear_error(env, capsys):
    raw, data = env
    cli.main(["normalize"])
    shutil.rmtree(raw)
    assert cli.main(["normalize", "--check"]) == 1
    assert "missing raw data" in capsys.readouterr().err


def test_normalize_without_raw_is_a_clear_error(env, capsys):
    raw, data = env
    shutil.rmtree(raw)
    assert cli.main(["normalize"]) == 1
    err = capsys.readouterr().err
    assert "missing raw data" in err and len(err.strip().splitlines()) == 1
    assert not (data / "canonical").exists()


def test_crosscheck_without_quests_json_is_a_clear_error(env, capsys):
    assert cli.main(["crosscheck"]) == 1
    err = capsys.readouterr().err
    assert "missing canonical quests" in err and len(err.strip().splitlines()) == 1


def test_crosscheck_prints_known_and_unknown_level_and_writes_lf(env, capsys):
    _, data = env
    cli.main(["normalize"])
    capsys.readouterr()
    assert cli.main(["crosscheck"]) == 0
    out = capsys.readouterr().out
    assert "in_scope=" in out and "in_scope_known=" in out and "in_scope_unknown_level=" in out
    report = data / "reports" / f"crosscheck-{DATA_BUILD}.md"
    assert b"\r\n" not in report.read_bytes()


def test_validate_missing_route_file_is_a_clear_error(env, capsys):
    raw, data = env
    cli.main(["normalize"])
    capsys.readouterr()
    assert cli.main(["validate", str(data / "nope.json")]) == 1
    assert "route" in capsys.readouterr().err


def test_validate_malformed_route_file_is_a_clear_error(env, capsys):
    _, data = env
    cli.main(["normalize"])
    bad = data / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["validate", str(bad)]) == 1
    err = capsys.readouterr().err
    assert "bad.json" in err and "Traceback" not in err


def test_validate_all_with_zero_routes(env, capsys):
    cli.main(["normalize"])
    capsys.readouterr()
    assert cli.main(["validate", "--all"]) == 0
    assert "0 routes checked, 0 issues" in capsys.readouterr().out


def test_normalize_writes_uimaps_and_check_compares_it(env, capsys):
    _, data = env
    assert cli.main(["normalize"]) == 0
    uimaps = data / "canonical" / "uimaps.json"
    doc = json.loads(uimaps.read_text(encoding="utf-8"))
    assert doc["build"] == DATA_BUILD and doc["maps"]
    assert b"\r\n" not in uimaps.read_bytes()
    assert cli.main(["normalize", "--check"]) == 0
    uimaps.write_text(uimaps.read_text(encoding="utf-8") + " ", encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["normalize", "--check"]) == 1
    assert "uimaps.json" in capsys.readouterr().err


def test_validate_uses_committed_uimaps_not_raw(env):
    raw, _ = env
    cli.main(["normalize"])
    shutil.rmtree(raw)
    assert cli.main(["validate", "--all"]) == 0


def _generate_env(env, confidence="unverified"):
    """Canonical files for a one-quest route plus a zone order, all in the tmp data dir."""
    _, data = env
    start = {"type": "npc", "id": 1001, "name": None, "uiMapId": 1429, "x": 10.0, "y": 10.0}
    quest = {
        "id": 1, "name": "Q1", "level": 1, "minLevel": 1, "races": None, "classes": None, "prereqs": [],
        "start": start, "end": dict(start),
        "objectives": {"units": [], "items": [], "objects": []},
        "inForever": True, "confidence": confidence,
    }
    canon = data / "canonical"
    canon.mkdir(parents=True)
    (canon / "quests.json").write_text(json.dumps([quest]), encoding="utf-8")
    (canon / "uimaps.json").write_text(json.dumps({"build": DATA_BUILD, "maps": {"1429": "Elwynn Forest"}}),
                                       encoding="utf-8")
    (canon / "spawns.json").write_text(json.dumps({"units": {}, "objects": {}, "items": {}}), encoding="utf-8")
    (canon / "questxp.json").write_text(
        json.dumps({"build": DATA_BUILD, "levels": {"1": [0, 10, 20, 40, 60, 80, 100, 120, 0, 0]}}), encoding="utf-8")
    (data / "zone-order").mkdir()
    (data / "zone-order" / "t.yaml").write_text(
        "route: t\nrace: Human\nfaction: Alliance\nreviewed: false\nzones:\n  - Elwynn Forest\n", encoding="utf-8")
    return data


def test_generate_writes_files_and_check_round_trips(env, capsys):
    data = _generate_env(env)
    assert cli.main(["generate", "t"]) == 0
    routes = data / "routes"
    assert (routes / "t.generated.json").is_file() and (routes / "t.json").is_file()
    report = (data / "reports" / "route-t.md").read_text(encoding="utf-8")
    assert "tahmin" in report.lower() and "\r\n" not in report
    assert (routes / "t.json").read_bytes().endswith(b"}\n")
    capsys.readouterr()
    assert cli.main(["generate", "t", "--check"]) == 0
    assert "up to date" in capsys.readouterr().out
    (routes / "t.json").write_text("{}", encoding="utf-8")
    assert cli.main(["generate", "t", "--check"]) == 1


def test_generate_check_never_writes(env):
    data = _generate_env(env)
    assert cli.main(["generate", "t", "--check"]) == 1
    assert not (data / "routes").exists() and not (data / "reports").exists()


def test_generate_cli_blocks_on_blocking_rule(env, capsys):
    data = _generate_env(env)
    (data / "overrides").mkdir()
    (data / "overrides" / "t.yaml").write_text(
        "- op: insertAfter\n  after: accept-1\n  step: {id: bad-map, type: gap, mapId: 99999, x: 1, y: 1,"
        " confidence: unverified, questId: 1, reason: x}\n", encoding="utf-8")
    assert cli.main(["generate", "t"]) == 1
    assert "unknown-map" in capsys.readouterr().err
    assert not (data / "routes").exists() and not (data / "reports").exists()


def test_generate_cli_fails_on_missing_override_anchor(env, capsys):
    data = _generate_env(env)
    (data / "overrides").mkdir()
    (data / "overrides" / "t.yaml").write_text("- {op: remove, id: gone}\n", encoding="utf-8")
    assert cli.main(["generate", "t"]) == 1
    assert "patch 0 (remove): step gone not found" in capsys.readouterr().err
    assert not (data / "routes").exists()


def test_generate_missing_canonical_questxp_is_a_clear_error(env, capsys):
    data = _generate_env(env)
    (data / "canonical" / "questxp.json").unlink()
    assert cli.main(["generate", "t"]) == 1
    err = capsys.readouterr().err
    assert "missing canonical questxp" in err and len(err.strip().splitlines()) == 1
    assert not (data / "routes").exists()


def test_generate_needs_no_raw_data(env, capsys):
    raw, _ = env
    data = _generate_env(env)
    shutil.rmtree(raw)
    assert cli.main(["generate", "t"]) == 0
    assert cli.main(["generate", "t", "--check"]) == 0
    assert (data / "routes" / "t.json").is_file()


def test_normalize_writes_questxp_and_check_compares_it(env, capsys):
    _, data = env
    assert cli.main(["normalize"]) == 0
    path = data / "canonical" / "questxp.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["build"] == DATA_BUILD
    assert doc["levels"]["1"] == [0, 10, 20, 40, 60, 80, 100, 120, 0, 0]
    assert all(len(row) == 10 for row in doc["levels"].values())
    assert b"\r\n" not in path.read_bytes()
    assert cli.main(["normalize", "--check"]) == 0
    doc["levels"]["1"][5] = 1
    path.write_text(json.dumps(doc), encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["normalize", "--check"]) == 1
    assert "questxp.json" in capsys.readouterr().err


def test_load_questxp_canonical_has_int_levels(env):
    from pipeline.canonical import load_questxp_canonical

    _, data = env
    assert cli.main(["normalize"]) == 0
    table = load_questxp_canonical(data)
    assert table[1] == [0, 10, 20, 40, 60, 80, 100, 120, 0, 0]
    assert all(isinstance(k, int) for k in table)


def test_generate_rejects_unknown_tier(env):
    with pytest.raises(SystemExit):
        cli.main(["generate", "t", "--tier", "gold"])


def test_generate_full_tier_error_exits_1(env, capsys):
    data = _generate_env(env)
    quests = json.loads((data / "canonical" / "quests.json").read_text(encoding="utf-8"))
    quests[0]["prereqs"] = [777]  # prerequisite outside the route is a gap, an error in full
    (data / "canonical" / "quests.json").write_text(json.dumps(quests), encoding="utf-8")
    assert cli.main(["generate", "t", "--tier", "full"]) == 1
    assert capsys.readouterr().err.strip()
    assert not (data / "routes").exists()


def test_validate_all_skips_generated_files(env, capsys):
    _generate_env(env)
    assert cli.main(["generate", "t"]) == 0
    capsys.readouterr()
    assert cli.main(["validate", "--all"]) == 0
    assert "1 routes checked" in capsys.readouterr().out


# Quest 2 is known but not on the route (Orc only) and needs level 20, so a travel step that
# names it triggers over-level only, which never blocks a beta route.
NON_BLOCKING_PATCH = (
    "- op: insertAfter\n  after: accept-1\n  step: {id: stray, type: travel, mapId: 1429, x: 1, y: 1,"
    " confidence: cross-checked, questId: 2, mode: walk, radius: 5}\n"
)


def _add_off_route_level_20_quest(data):
    path = data / "canonical" / "quests.json"
    quests = json.loads(path.read_text(encoding="utf-8"))
    quests.append({**quests[0], "id": 2, "name": "Q2", "level": 20, "minLevel": 20, "races": ["Orc"]})
    path.write_text(json.dumps(quests), encoding="utf-8")


def test_generate_non_blocking_finding_is_reported_in_beta_and_blocks_in_full(env, capsys):
    data = _generate_env(env, confidence="cross-checked")
    _add_off_route_level_20_quest(data)
    (data / "overrides").mkdir()
    (data / "overrides" / "t.yaml").write_text(NON_BLOCKING_PATCH, encoding="utf-8")
    assert cli.main(["generate", "t", "--tier", "full"]) == 1
    assert "over-level" in capsys.readouterr().err
    assert not (data / "routes").exists() and not (data / "reports").exists()
    assert cli.main(["generate", "t"]) == 0
    report = (data / "reports" / "route-t.md").read_text(encoding="utf-8")
    assert "over-level" in report and "quest 2 needs level 20" in report


def test_generate_unknown_quest_blocks_in_beta(env, capsys):
    data = _generate_env(env)
    (data / "overrides").mkdir()
    (data / "overrides" / "t.yaml").write_text(NON_BLOCKING_PATCH.replace("questId: 2", "questId: 999"),
                                               encoding="utf-8")
    assert cli.main(["generate", "t"]) == 1
    assert "[unknown-quest] stray: quest 999 is not in the canonical data" in capsys.readouterr().err
    assert not (data / "routes").exists()


def test_generate_out_of_range_set_coords_exits_1_and_writes_nothing(env, capsys):
    data = _generate_env(env)
    (data / "overrides").mkdir()
    (data / "overrides" / "t.yaml").write_text(
        "- {op: setCoords, id: accept-1, mapId: 1429, x: 150, y: 5}\n", encoding="utf-8")
    assert cli.main(["generate", "t"]) == 1
    assert "/0: " in capsys.readouterr().err
    assert not (data / "routes").exists() and not (data / "reports").exists()


def test_generate_invalid_yaml_override_is_one_line_error(env, capsys):
    data = _generate_env(env)
    (data / "overrides").mkdir()
    (data / "overrides" / "t.yaml").write_text("- {op: remove\n", encoding="utf-8")
    assert cli.main(["generate", "t"]) == 1
    err = capsys.readouterr().err
    assert "t.yaml" in err and len(err.strip().splitlines()) == 1


def test_generate_check_with_corrupt_committed_json_is_a_clear_error(env, capsys):
    data = _generate_env(env)
    assert cli.main(["generate", "t"]) == 0
    (data / "routes" / "t.json").write_text("{not json", encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["generate", "t", "--check"]) == 1
    err = capsys.readouterr().err
    assert "t.json" in err and "Traceback" not in err


def _export_env(env):
    data = _generate_env(env)
    assert cli.main(["generate", "t"]) == 0
    return data, data.parent


def test_export_writes_site_json_and_lua_and_is_repeatable(env, capsys):
    data, root = _export_env(env)
    capsys.readouterr()
    assert cli.main(["export", "t"]) == 0
    site, lua = root / "site" / "src" / "data" / "t.json", root / "addon" / "ForeverXP" / "Data" / "t.lua"
    doc = json.loads(site.read_text(encoding="utf-8"))
    assert doc["steps"][0]["zoneName"] == "Elwynn Forest" and doc["steps"][0]["questName"] == "Q1"
    assert lua.read_text(encoding="utf-8").startswith("-- AUTO-GENERATED by pipeline/export.")
    assert b"\r\n" not in lua.read_bytes() and site.read_bytes().endswith(b"}\n")
    before = (site.read_bytes(), lua.read_bytes())
    assert cli.main(["export", "t"]) == 0
    assert (site.read_bytes(), lua.read_bytes()) == before


def test_export_all_skips_generated_files(env, capsys):
    data, root = _export_env(env)
    capsys.readouterr()
    assert cli.main(["export", "--all"]) == 0
    assert "1 routes exported" in capsys.readouterr().out
    assert not (root / "site" / "src" / "data" / "t.generated.json").exists()


def test_export_all_with_no_routes_exits_0(env, capsys):
    assert cli.main(["export", "--all"]) == 0
    assert "0 routes exported" in capsys.readouterr().out


def test_export_requires_exactly_one_of_all_or_route(env, capsys):
    assert cli.main(["export"]) == 1
    assert cli.main(["export", "--all", "t"]) == 1
    assert capsys.readouterr().err.strip()


def test_export_missing_route_is_a_clear_error(env, capsys):
    _export_env(env)
    capsys.readouterr()
    assert cli.main(["export", "nope"]) == 1
    err = capsys.readouterr().err
    assert "nope" in err and len(err.strip().splitlines()) == 1


def test_export_unwritable_route_is_one_line_error_and_writes_nothing(env, capsys):
    data, root = _export_env(env)
    good = (data / "routes" / "t.json").read_text(encoding="utf-8")
    (data / "routes" / "a-bad.json").write_text(good.replace('"x": 10.0', '"x": NaN', 1), encoding="utf-8")
    (data / "routes" / "b-noid.json").write_text("{}", encoding="utf-8")
    capsys.readouterr()
    for name in ("a-bad", "b-noid"):
        assert cli.main(["export", name]) == 1
        err = capsys.readouterr().err
        assert f"{name}.json" in err and len(err.strip().splitlines()) == 1 and "Traceback" not in err
    assert cli.main(["export", "--all"]) == 1  # one bad file aborts the whole run before any write
    assert not (root / "site").exists() and not (root / "addon").exists()


def _route_with_over_level(env, tier):
    data = _generate_env(env)
    assert cli.main(["generate", "t"]) == 0
    route_path = data / "routes" / "t.json"
    route = json.loads(route_path.read_text(encoding="utf-8"))
    route["releaseTier"] = tier
    route_path.write_text(json.dumps(route), encoding="utf-8")
    quests_path = data / "canonical" / "quests.json"
    quests = json.loads(quests_path.read_text(encoding="utf-8"))
    quests[0]["minLevel"] = 10  # route starts at level 1, so this is over-level only
    quests_path.write_text(json.dumps(quests), encoding="utf-8")


def test_validate_beta_route_with_only_over_level_exits_0_and_labels_it(env, capsys):
    _route_with_over_level(env, "beta")
    capsys.readouterr()
    assert cli.main(["validate", "--all"]) == 0
    out = capsys.readouterr().out
    assert "non-blocking (beta)" in out and "over-level" in out
    assert "0 blocking" in out


def test_validate_full_route_with_over_level_exits_1(env, capsys):
    _route_with_over_level(env, "full")
    capsys.readouterr()
    assert cli.main(["validate", "--all"]) == 1
    out = capsys.readouterr().out
    assert "non-blocking" not in out and "over-level" in out


def _set_generated_at(path, stamp):
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["generatedAt"] = stamp
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def test_generate_keeps_committed_generated_at_when_nothing_else_changed(env):
    data = _generate_env(env)
    assert cli.main(["generate", "t"]) == 0
    routes = data / "routes"
    old = "2000-01-01T00:00:00Z"
    for name in ("t.generated.json", "t.json"):
        _set_generated_at(routes / name, old)
    before = {name: (routes / name).read_bytes() for name in ("t.generated.json", "t.json")}
    assert cli.main(["generate", "t"]) == 0
    assert {name: (routes / name).read_bytes() for name in before} == before


def test_generate_takes_a_new_generated_at_when_content_changed(env):
    data = _generate_env(env)
    assert cli.main(["generate", "t"]) == 0
    routes = data / "routes"
    old = "2000-01-01T00:00:00Z"
    for name in ("t.generated.json", "t.json"):
        _set_generated_at(routes / name, old)
    path = data / "canonical" / "quests.json"
    quests = json.loads(path.read_text(encoding="utf-8"))
    quests[0]["start"]["x"] = 20.0
    path.write_text(json.dumps(quests), encoding="utf-8")
    assert cli.main(["generate", "t"]) == 0
    for name in ("t.generated.json", "t.json"):
        assert json.loads((routes / name).read_text(encoding="utf-8"))["generatedAt"] != old


def test_route_report_lists_class_ids_and_counts_other_reasons(env):
    data = _generate_env(env)
    path = data / "canonical" / "quests.json"
    quests = json.loads(path.read_text(encoding="utf-8"))
    quests += [{**quests[0], "id": 12, "classes": ["Mage"]}, {**quests[0], "id": 11, "classes": ["Rogue"]},
               {**quests[0], "id": 13, "races": ["Orc"]}]
    path.write_text(json.dumps(quests), encoding="utf-8")
    assert cli.main(["generate", "t"]) == 0
    report = (data / "reports" / "route-t.md").read_text(encoding="utf-8")
    assert "- class: 2 (kimlikler: 11, 12)\n" in report
    assert "- race: 1\n" in report
