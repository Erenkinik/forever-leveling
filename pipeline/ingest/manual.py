"""Load hand-entered Forever quest facts looked up on Wowhead (facts only, never copied text)."""
import datetime
import re
from pathlib import Path

import yaml

SOURCE = "wowhead-manual"
URL_PREFIX = "https://www.wowhead.com/forever/quest="
REQUIRED = ("id", "name", "level", "minLevel", "wowheadUrl", "checkedOn")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def load_manual(path: Path) -> dict[int, dict]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    if not isinstance(data, list):
        raise ValueError(f"{path}: top level must be a list of quest entries")
    quests: dict[int, dict] = {}
    for index, entry in enumerate(data):
        if not isinstance(entry, dict) or "id" not in entry:
            raise ValueError(f"{path}: entry #{index} is not a mapping with an id")
        qid = entry["id"]
        if type(qid) is not int:  # excludes bool, str, list
            raise ValueError(f"quest {qid!r}: id must be an integer")
        missing = [k for k in REQUIRED if entry.get(k) is None]
        if missing:
            raise ValueError(f"quest {qid}: missing required field(s): {', '.join(missing)}")
        if qid in quests:
            raise ValueError(f"quest {qid}: duplicate id")
        url = entry["wowheadUrl"]
        if not isinstance(url, str) or not url.startswith(URL_PREFIX):
            raise ValueError(f"quest {qid}: wowheadUrl must start with {URL_PREFIX}")
        checked = entry["checkedOn"]
        if isinstance(checked, datetime.date):
            checked = checked.isoformat()
        if not isinstance(checked, str) or not _DATE_RE.fullmatch(checked):
            raise ValueError(f"quest {qid}: checkedOn must be YYYY-MM-DD")
        try:
            datetime.date.fromisoformat(checked)
        except ValueError:
            raise ValueError(f"quest {qid}: checkedOn {checked!r} is not a real date") from None
        quests[qid] = {**entry, "checkedOn": checked, "source": SOURCE}
    return quests
