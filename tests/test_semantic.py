import json
from pathlib import Path

from pipeline.validate.semantic import Issue, check_route

FIX = Path(__file__).parent / "fixtures" / "routes"
MAPS = frozenset({1429})


def _q(qid, minLevel=1, prereqs=(), confidence="cross-checked"):
    return {"id": qid, "minLevel": minLevel, "prereqs": list(prereqs), "confidence": confidence}


QUESTS = {
    783: _q(783),
    33: _q(33),
    100: _q(100, prereqs=[783]),
    200: _q(200, minLevel=20),
    300: _q(300, confidence="unverified"),
    400: {**_q(400), "inForever": False},
}


def _check(name, quests=QUESTS, **kw):
    route = json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))
    return check_route(route, quests, MAPS, **kw)


def _rules(issues):
    return {i.rule for i in issues}


def test_valid_fixture_has_no_issues():
    assert _check("valid") == []


def test_rule_schema():
    issues = _check("schema")
    assert _rules(issues) == {"schema"}
    assert all(isinstance(i, Issue) for i in issues)


def test_rule_turnin_before_accept():
    assert "turnin-before-accept" in _rules(_check("turnin-before-accept"))


def test_rule_complete_before_accept():
    issues = _check("complete-before-accept")
    assert "complete-before-accept" in _rules(issues)
    assert [i.stepId for i in issues if i.rule == "complete-before-accept"] == ["s1"]


def test_rule_prereq_not_done():
    issues = _check("prereq-not-done")
    assert [(i.rule, i.stepId) for i in issues] == [("prereq-not-done", "s1")]


def test_rule_accepted_never_closed():
    issues = _check("accepted-never-closed")
    assert [(i.rule, i.stepId) for i in issues] == [("accepted-never-closed", "s1")]


def test_rule_unknown_map():
    issues = _check("unknown-map")
    assert {(i.rule, i.stepId) for i in issues} == {("unknown-map", "s1")}


def test_rule_duplicate_step_id():
    issues = _check("duplicate-step-id")
    assert [(i.rule, i.stepId) for i in issues] == [("duplicate-step-id", "s1")]


def test_rule_over_level():
    issues = _check("over-level")
    assert {(i.rule, i.stepId) for i in issues} == {("over-level", "s1"), ("over-level", "s2")}


def test_rule_not_in_forever():
    issues = _check("not-in-forever")
    assert [(i.rule, i.stepId) for i in issues] == [
        ("not-in-forever", "s1"), ("not-in-forever", "s2"),
    ]
    assert "quest 400 is not in Forever" in issues[0].message


def test_in_forever_flag_true_or_absent_is_fine():
    quests = {**QUESTS, 400: {**_q(400), "inForever": True}}
    assert _check("not-in-forever", quests=quests) == []
    quests = {**QUESTS, 400: _q(400)}
    assert _check("not-in-forever", quests=quests) == []


def test_over_level_uses_last_grind_untillevel():
    route = json.loads((FIX / "over-level.json").read_text(encoding="utf-8"))
    grind = {"id": "g1", "type": "grind", "mapId": 1429, "x": 1, "y": 1,
             "confidence": "cross-checked", "untilLevel": 17}
    route["steps"].insert(0, grind)
    assert check_route(route, QUESTS, MAPS) == []  # 20 <= 17 + 3


def test_unknown_quest_is_reported_not_crashing():
    issues = _check("unknown-quest")
    assert {i.rule for i in issues} == {"unknown-quest"}
    assert [i.stepId for i in issues] == ["s1", "s2"]
    assert "quest 424242 is not in the canonical data" in issues[0].message


def test_unknown_quest_and_prereq_not_done_block_in_beta():
    from pipeline.generate.config import BETA_BLOCKING_RULES

    assert "unknown-quest" in BETA_BLOCKING_RULES
    assert "prereq-not-done" in BETA_BLOCKING_RULES
    assert "over-level" not in BETA_BLOCKING_RULES and "level-unknown" not in BETA_BLOCKING_RULES


def test_rule_xp_target():
    assert _check("valid", xp_reaches_target=lambda r: True) == []
    issues = _check("valid", xp_reaches_target=lambda r: False)
    assert _rules(issues) == {"xp-target"}


def test_xp_target_skipped_when_not_given():
    assert "xp-target" not in _rules(_check("over-level"))


def test_rule_tier_full_requires_cross_checked():
    issues = _check("tier-full-requires-cross-checked")
    assert {(i.rule, i.stepId) for i in issues} == {
        ("tier-full-requires-cross-checked", "s1"),
        ("tier-full-requires-cross-checked", "s2"),
        ("tier-full-requires-cross-checked", "s3"),
    }


def test_beta_tier_allows_gap_and_unverified():
    assert _check("beta-gap-unverified") == []


def test_null_min_level_reported_not_crashing():
    quests = {**QUESTS, 33: _q(33, minLevel=None)}
    issues = _check("valid", quests=quests)
    assert {i.rule for i in issues} == {"level-unknown"}
    assert {i.stepId for i in issues} == {"s2", "s3", "s4"}
    assert all("quest 33 level unknown" in i.message for i in issues)


def test_unaccepted_turnin_does_not_satisfy_prereq():
    # quest 100 has prereq 783; 783 is turned in without ever being accepted
    route = json.loads((FIX / "valid.json").read_text(encoding="utf-8"))
    base = {"mapId": 1429, "x": 1, "y": 1, "confidence": "cross-checked", "npcId": 5}
    route["steps"] = [
        {**base, "id": "a1", "type": "turnin", "questId": 783},
        {**base, "id": "a2", "type": "accept", "questId": 100},
        {**base, "id": "a3", "type": "turnin", "questId": 100},
    ]
    issues = check_route(route, QUESTS, MAPS)
    assert {(i.rule, i.stepId) for i in issues} == {
        ("turnin-before-accept", "a1"),
        ("prereq-not-done", "a2"),
    }


def test_over_level_uses_given_level_estimate():
    route = json.loads((FIX / "over-level.json").read_text(encoding="utf-8"))
    sids = [s["id"] for s in route["steps"]]
    assert "over-level" in _rules(check_route(route, QUESTS, MAPS))
    assert check_route(route, QUESTS, MAPS, levels={sid: 17 for sid in sids}) == []
    issues = check_route(route, QUESTS, MAPS, levels={sid: 16 for sid in sids})
    assert "estimated level is 16" in next(i.message for i in issues if i.rule == "over-level")


def test_gap_steps_are_not_level_checked():
    route = json.loads((FIX / "over-level.json").read_text(encoding="utf-8"))
    route["steps"] = [{"id": "g", "type": "gap", "mapId": 1429, "x": 1.0, "y": 1.0, "confidence": "unverified",
                       "questId": 200, "reason": "quest 200: objective located only off-route"}]
    assert check_route(route, QUESTS, MAPS) == []
