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
