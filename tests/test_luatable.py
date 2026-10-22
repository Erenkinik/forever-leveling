from pathlib import Path

import pytest

from pipeline.ingest.luatable import parse_lua_table

FIX = Path(__file__).parent / "fixtures" / "pfquest"


def test_parses_nested_quest_table():
    data = parse_lua_table((FIX / "quests.lua").read_text(encoding="utf-8"))
    q = data[33]
    assert q["lvl"] == 2
    assert q["pre"] == [5261]
    assert q["end"] == {"U": [196]}


def test_sequential_int_keys_become_list():
    assert parse_lua_table("x = { [1] = {48.9, 41.6, 12, 285} }") == [[48.9, 41.6, 12, 285]]


def test_non_sequential_int_keys_stay_dict():
    assert parse_lua_table("x = { [2] = 1, [5] = 2 }") == {2: 1, 5: 2}


def test_parses_escapes_and_crlf():
    lua = (
        'x = {\n'
        '  [1] = "you\\\'ll\\r\\n",\n'
        '  [2] = \'a\\"b\\\\c\\nd\',\n'
        '}\n'
    ).replace("\n", "\r\n")
    assert parse_lua_table(lua) == ["you'll\r\n", 'a"b\\c\nd']


def test_real_fixture_escapes():
    data = parse_lua_table((FIX / "enUS" / "quests.lua").read_text(encoding="utf-8"))
    assert "you'll find useful.$B$B" in data[33]["D"]
    assert data[1]["T"] == 'The "Chow" Quest (123)aa'


def test_negative_and_float_numbers():
    assert parse_lua_table("x = { -3, 2.5, -0.75, 10 }") == [-3, 2.5, -0.75, 10]


def test_literals_comments_empty_and_trailing_commas():
    text = 'x = { -- first\n ["a"] = true, ["b"] = false, ["c"] = nil, ["d"] = {}, --[[ no ]] }'
    assert parse_lua_table(text) == {"a": True, "b": False, "c": None, "d": []}


def test_only_first_table_after_first_equals():
    assert parse_lua_table('a["b"] = { 1 }\nc = { 2 }') == [1]


def test_unterminated_table_raises():
    with pytest.raises(ValueError):
        parse_lua_table("x = { [1] = 2")


def test_decimal_escape():
    assert parse_lua_table(r'x = { "\065\10x\0" }') == ["A\nx\0"]


def test_decimal_escape_over_255_raises():
    with pytest.raises(ValueError, match="offset"):
        parse_lua_table(r'x = { "\256" }')


def test_unsupported_escape_raises_with_position():
    with pytest.raises(ValueError, match="offset"):
        parse_lua_table(r'x = { "a\qb" }')
