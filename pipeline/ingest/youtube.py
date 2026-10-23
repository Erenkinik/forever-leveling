"""A YouTube video for each quest the routes take, found with the YouTube Data API (search.list).

Videos are kept by quest name in data/videos.json; quests of the same name share one search and one video. A
search costs 100 of the API's 10,000 daily quota units, so a run does at most `budget` searches and the next run
goes on from where it stopped: the quests met earliest in the routes come first. A video is taken only when its
title names the quest and says it is WoW; else the name is recorded with no video, so it is not searched again.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
# One search costs 100 units of the default 10,000 a day; a few units stay free for retries.
DEFAULT_BUDGET = 95
RESULTS = 10
_WOW = re.compile(r"\b(wow|world of warcraft|classic|forever|vanilla|quest)\b", re.I)
# Quests new in Forever (ids from here on) often share a name with an older quest (Skyborne's "Call of Earth",
# "Coming of Age"), so they get their own entry, are searched as Forever quests and take only a video that says so.
FOREVER_QUESTS = 90_000
FOREVER_SUFFIX = " (WoW Forever)"
_FOREVER = re.compile(r"\b(forever|skyborne|zephras)\b", re.I)


def video_key(quest_id: int | None, name: str) -> str:
    """The quest's entry in data/videos.json: its name, plus FOREVER_SUFFIX for a quest new in Forever."""
    return f"{name}{FOREVER_SUFFIX}" if (quest_id or 0) >= FOREVER_QUESTS else name


class QuotaExceeded(Exception):
    """The API refused the search: the day's quota is used up (or the key is not allowed)."""


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", text.lower()).split())


def query_for(key: str) -> str:
    if key.endswith(FOREVER_SUFFIX):
        return f'"{key.removesuffix(FOREVER_SUFFIX)}" wow forever quest'
    return f'"{key}" wow classic quest'


def pick(key: str, items: list[dict]) -> dict | None:
    """The first search result whose title names the quest and says it is WoW, as {id, title, channel}; for a
    Forever quest's entry its title or description must also say Forever (or Skyborne, Zephras)."""
    forever = key.endswith(FOREVER_SUFFIX)
    want = _norm(key.removesuffix(FOREVER_SUFFIX))
    for item in items:
        vid = (item.get("id") or {}).get("videoId")
        snippet = item.get("snippet") or {}
        title = snippet.get("title") or ""
        if not (vid and f" {want} " in f" {_norm(title)} " and _WOW.search(title)):
            continue
        if forever and not _FOREVER.search(f"{title} {snippet.get('description') or ''}"):
            continue
        return {"id": vid, "title": title, "channel": snippet.get("channelTitle")}
    return None


def search(name: str, api_key: str, opener: Callable = urllib.request.urlopen) -> list[dict]:
    params = urllib.parse.urlencode({
        "part": "snippet", "type": "video", "videoEmbeddable": "true", "maxResults": RESULTS,
        "q": query_for(name), "key": api_key,
    })
    try:
        with opener(f"{SEARCH_URL}?{params}", timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("items", [])
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            raise QuotaExceeded(f"YouTube refused the search (HTTP {exc.code}): quota used up or key not allowed") \
                from exc
        raise


def quest_names_in_order(routes: list[dict], quests: dict[int, dict]) -> list[str]:
    """The video entries (video_key) of the quests the routes accept, earliest first (by step position, over all
    routes)."""
    first: dict[str, int] = {}
    for route in routes:
        for i, step in enumerate(route.get("steps", [])):
            name = (quests.get(step.get("questId")) or {}).get("name")
            if step.get("type") == "accept" and name:
                key = video_key(step.get("questId"), name)
                first[key] = min(first.get(key, i), i)
    return sorted(first, key=lambda n: (first[n], n))


def load_videos(path: Path) -> dict[str, dict | None]:
    return json.loads(path.read_text(encoding="utf-8"))["videos"] if path.is_file() else {}


def save_videos(path: Path, videos: dict[str, dict | None]) -> None:
    doc = {"note": "quest name -> YouTube video (null: searched, none fit); python -m pipeline videos",
           "videos": dict(sorted(videos.items()))}
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(path)


def fill_videos(names: list[str], videos: dict[str, dict | None], api_key: str, budget: int = DEFAULT_BUDGET,
                opener: Callable = urllib.request.urlopen) -> tuple[int, bool]:
    """Search the names not in `videos` yet, in order, at most `budget` of them, adding each to `videos`.
    Returns (searches done, whether the quota ran out)."""
    done = 0
    for name in names:
        if done >= budget:
            break
        if name in videos:
            continue
        try:
            items = search(name, api_key, opener)
        except QuotaExceeded:
            return done, True
        videos[name] = pick(name, items)
        done += 1
    return done, False


def api_key_from(env: dict[str, str], dotenv: Path) -> str | None:
    """YOUTUBE_API_KEY from the environment, else from the .env file (only that line is read)."""
    if env.get("YOUTUBE_API_KEY"):
        return env["YOUTUBE_API_KEY"]
    if dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key.strip() == "YOUTUBE_API_KEY":
                return value.strip().strip('"').strip("'") or None
    return None
