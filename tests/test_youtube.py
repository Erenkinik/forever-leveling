import io
import json
import urllib.error

import pytest

from pipeline.ingest.youtube import (
    QuotaExceeded, api_key_from, fill_videos, load_videos, pick, quest_names_in_order, save_videos, search,
)


def item(vid, title, channel="Guides"):
    return {"id": {"videoId": vid}, "snippet": {"title": title, "channelTitle": channel}}


def test_pick_takes_the_first_title_that_names_the_quest_and_wow():
    items = [item("a", "Rude Awakening - a song"), item("b", "Rude Awakenings in Life"),
             item("c", "WoW Classic: Rude Awakening quest guide"), item("d", "Rude Awakening WoW")]
    assert pick("Rude Awakening", items) == {"id": "c", "title": "WoW Classic: Rude Awakening quest guide",
                                             "channel": "Guides"}
    assert pick("Rude Awakening", items[:2]) is None
    # punctuation and case do not matter
    assert pick("The Hunt Begins", [item("e", "WOW - the hunt begins!")])["id"] == "e"


def test_quest_names_in_order_puts_the_earliest_steps_first_and_shares_names():
    quests = {1: {"name": "Alpha"}, 2: {"name": "Beta"}, 3: {"name": "Alpha"}, 4: {"name": "Gamma"}}
    routes = [{"steps": [{"type": "accept", "questId": 2}, {"type": "accept", "questId": 1},
                         {"type": "turnin", "questId": 4}]},
              {"steps": [{"type": "accept", "questId": 3}, {"type": "accept", "questId": 4}]}]
    assert quest_names_in_order(routes, quests) == ["Alpha", "Beta", "Gamma"]


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fill_videos_searches_new_names_within_the_budget_and_stops_at_the_quota():
    asked = []

    def opener(url, timeout):
        asked.append(url)
        if len(asked) == 3:
            raise urllib.error.HTTPError(url, 403, "quotaExceeded", {}, None)
        return FakeResp(json.dumps({"items": [item("v1", "WoW Classic Beta quest")]}).encode())

    videos = {"Alpha": None}
    done, out = fill_videos(["Alpha", "Beta", "Gamma", "Delta"], videos, "KEY", budget=5, opener=opener)
    assert (done, out) == (2, True)
    assert videos == {"Alpha": None, "Beta": {"id": "v1", "title": "WoW Classic Beta quest", "channel": "Guides"},
                      "Gamma": None}
    assert "Delta" not in videos and "key=KEY" in asked[0] and "Alpha" not in asked[0]
    videos2: dict = {}
    assert fill_videos(["A", "B", "C"], videos2, "KEY", budget=1,
                       opener=lambda u, timeout: FakeResp(b'{"items": []}')) == (1, False)
    assert videos2 == {"A": None}


def test_search_takes_too_many_requests_as_the_quota_used_up():
    def opener(url, timeout):
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
    with pytest.raises(QuotaExceeded):
        search("X", "KEY", opener)


def test_search_raises_other_http_errors():
    def opener(url, timeout):
        raise urllib.error.HTTPError(url, 500, "boom", {}, None)
    with pytest.raises(urllib.error.HTTPError):
        search("X", "KEY", opener)


def test_videos_file_round_trips(tmp_path):
    path = tmp_path / "videos.json"
    assert load_videos(path) == {}
    save_videos(path, {"B": None, "A": {"id": "x", "title": "t", "channel": "c"}})
    assert load_videos(path) == {"A": {"id": "x", "title": "t", "channel": "c"}, "B": None}


def test_api_key_comes_from_the_environment_or_the_dotenv_line(tmp_path):
    dotenv = tmp_path / ".env"
    assert api_key_from({}, dotenv) is None
    dotenv.write_text("OTHER=1\nYOUTUBE_API_KEY = \"abc\"\n", encoding="utf-8")
    assert api_key_from({}, dotenv) == "abc"
    assert api_key_from({"YOUTUBE_API_KEY": "env"}, dotenv) == "env"
