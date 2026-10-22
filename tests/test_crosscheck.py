from pipeline.crosscheck.report import render_markdown, summarize


def q(qid, sources, confidence, in_forever=True, min_level=1, conflicts=()):
    return {
        "id": qid,
        "inForever": in_forever,
        "minLevel": min_level,
        "sources": list(sources),
        "confidence": confidence,
        "conflicts": list(conflicts),
    }


def test_counts_by_confidence():
    s = summarize([
        q(1, ["wago-db2", "pfquest"], "cross-checked"),
        q(2, ["wago-db2", "pfquest"], "cross-checked"),
        q(3, ["pfquest"], "unverified", in_forever=False),
        q(4, ["wago-db2", "pfquest"], "unverified", conflicts=["start.coords", "name"]),
        q(5, ["wago-db2", "pfquest"], "unverified", min_level=None, conflicts=["name"]),
        q(6, ["wago-db2", "pfquest"], "cross-checked", min_level=45),
    ])
    assert s.total == 6
    assert s.by_confidence == {"cross-checked": 3, "unverified": 3}
    assert s.not_in_forever == 1
    assert s.conflicts == {"start.coords": 1, "name": 2}
    assert s.in_scope == 4
    assert s.needs_manual == []


def test_new_forever_quest_listed_as_needs_manual():
    s = summarize([
        q(10, ["wago-db2"], "unverified"),
        q(11, ["wago-db2", "pfquest"], "cross-checked"),
        q(12, ["pfquest"], "unverified", in_forever=False),
        q(13, ["wago-db2", "wowhead-manual"], "cross-checked"),
    ])
    assert s.needs_manual == [10]


def test_render_markdown_has_build_and_table():
    s = summarize([q(1, ["wago-db2", "pfquest"], "cross-checked")])
    md = render_markdown(s, "1.60.1.70532")
    assert "1.60.1.70532" in md
    assert "| cross-checked |" in md
