"""Download and load pfQuest (MIT) database files."""
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .luatable import parse_lua_table

BASE_URL = "https://raw.githubusercontent.com/shagu/pfQuest/master/db/"
FILES = ("quests.lua", "units.lua", "objects.lua", "enUS/quests.lua", "enUS/units.lua")


def fetch_pfquest(raw_dir: Path, opener: Callable = urllib.request.urlopen) -> None:
    """Download the pfQuest files into raw_dir/pfquest; never leaves a partial file."""
    base = Path(raw_dir) / "pfquest"
    for rel in FILES:
        dest = base / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        try:
            with opener(BASE_URL + rel) as resp:
                part.write_bytes(resp.read())
        except (urllib.error.URLError, OSError) as exc:  # HTTPError is a URLError
            part.unlink(missing_ok=True)
            raise RuntimeError(f"failed to download {rel}: {exc}") from exc
        part.replace(dest)


@dataclass(frozen=True)
class PfData:
    quests: dict[int, dict]
    units: dict[int, dict]
    objects: dict[int, dict]


def _read(path: Path):
    return parse_lua_table(path.read_text(encoding="utf-8"))


def _spawns(src: dict, names: dict[int, str] | None) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for sid, entry in src.items():
        rec = {
            "coords": [(c[0], c[1], c[2]) for c in entry.get("coords", [])],
            "fac": entry.get("fac"),
        }
        if names is not None:
            rec["name"] = names.get(sid)
        out[sid] = rec
    return out


def load_pfquest(src_dir: Path) -> PfData:
    src = Path(src_dir)
    quest_names = _read(src / "enUS" / "quests.lua")
    quests: dict[int, dict] = {}
    for qid, entry in _read(src / "quests.lua").items():
        rec = dict(entry)
        rec["name"] = quest_names.get(qid, {}).get("T")
        quests[qid] = rec
    unit_names = _read(src / "enUS" / "units.lua")
    return PfData(
        quests=quests,
        units=_spawns(_read(src / "units.lua"), unit_names),
        objects=_spawns(_read(src / "objects.lua"), None),
    )
