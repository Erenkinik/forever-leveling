import copy

import pytest

from pipeline.generate.overrides import apply_overrides, load_overrides


def _step(sid, x=10.0):
    return {"id": sid, "type": "gap", "mapId": 1429, "x": x, "y": 10.0, "confidence": "unverified",
            "questId": 1, "reason": "r"}


@pytest.fixture
def route():
    return {"id": "t", "steps": [_step("a"), _step("b"), _step("c")]}


def _ids(r):
    return [s["id"] for s in r["steps"]]


def test_insert_after(route):
    before = copy.deepcopy(route)
    out, errors = apply_overrides(route, [{"op": "insertAfter", "after": "a", "step": _step("n")}])
    assert errors == [] and _ids(out) == ["a", "n", "b", "c"]
    assert route == before  # input untouched


def test_insert_after_existing_id_fails(route):
    out, errors = apply_overrides(route, [{"op": "insertAfter", "after": "a", "step": _step("c")}])
    assert len(errors) == 1 and "patch 0 (insertAfter)" in errors[0] and "c" in errors[0]
    assert _ids(out) == ["a", "b", "c"]


def test_remove(route):
    out, errors = apply_overrides(route, [{"op": "remove", "id": "b"}])
    assert errors == [] and _ids(out) == ["a", "c"]


def test_move(route):
    out, errors = apply_overrides(route, [{"op": "move", "id": "a", "after": "c"}])
    assert errors == [] and _ids(out) == ["b", "c", "a"]
    out, errors = apply_overrides(route, [{"op": "move", "id": "c", "after": "a"}])
    assert errors == [] and _ids(out) == ["a", "c", "b"]


def test_move_forward_to_non_last_anchor(route):
    out, errors = apply_overrides(route, [{"op": "move", "id": "a", "after": "b"}])
    assert errors == [] and _ids(out) == ["b", "a", "c"]


def test_move_after_itself_fails(route):
    out, errors = apply_overrides(route, [{"op": "move", "id": "a", "after": "a"}])
    assert len(errors) == 1 and _ids(out) == ["a", "b", "c"]


def test_set_coords(route):
    out, errors = apply_overrides(route, [{"op": "setCoords", "id": "b", "mapId": 1436, "x": 5.5, "y": 6.5}])
    assert errors == []
    b = out["steps"][1]
    assert (b["mapId"], b["x"], b["y"]) == (1436, 5.5, 6.5)
    assert route["steps"][1]["mapId"] == 1429


def test_override_with_missing_anchor_fails(route):
    patches = [
        {"op": "remove", "id": "a"},
        {"op": "insertAfter", "after": "gone", "step": _step("n")},
        {"op": "move", "id": "b", "after": "gone2"},
        {"op": "setCoords", "id": "gone3", "mapId": 1, "x": 1, "y": 1},
    ]
    out, errors = apply_overrides(route, patches)
    assert errors == [
        "patch 1 (insertAfter): step gone not found",
        "patch 2 (move): step gone2 not found",
        "patch 3 (setCoords): step gone3 not found",
    ]
    assert _ids(out) == ["b", "c"]  # the valid patch applied; failing ones did not


def test_overrides_survive_regeneration(route):
    patches = [
        {"op": "insertAfter", "after": "a", "step": _step("n")},
        {"op": "setCoords", "id": "c", "mapId": 1429, "x": 1.0, "y": 2.0},
    ]
    first, e1 = apply_overrides(route, patches)
    regenerated = copy.deepcopy(route)
    regenerated["steps"][0]["x"] = 50.0  # generator output changed, ids are stable
    second, e2 = apply_overrides(regenerated, patches)
    assert e1 == e2 == []
    assert _ids(first) == _ids(second) == ["a", "n", "b", "c"]
    assert second["steps"][0]["x"] == 50.0
    # when regeneration drops the anchor the patch is reported, never silently dropped
    del regenerated["steps"][0]
    _, errors = apply_overrides(regenerated, patches)
    assert errors == ["patch 0 (insertAfter): step a not found"]


def test_load_overrides(tmp_path):
    assert load_overrides(tmp_path / "none.yaml") == []
    f = tmp_path / "o.yaml"
    f.write_text("[]\n", encoding="utf-8")
    assert load_overrides(f) == []
    f.write_text("- {op: remove, id: a}\n", encoding="utf-8")
    assert load_overrides(f) == [{"op": "remove", "id": "a"}]
    f.write_text("- {op: bogus}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema errors"):
        load_overrides(f)


def test_load_overrides_invalid_yaml_names_the_file(tmp_path):
    f = tmp_path / "broken.yaml"
    f.write_text("- {op: remove\n", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.yaml"):
        load_overrides(f)
