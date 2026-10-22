"""What a quest's objectives take to finish, from pfQuest: how many of each mob or item, the best drop chance for
an item and the mob levels. The XP model (pipeline.generate.xpsim) turns this into kills."""
import re

from pipeline.ingest.pfquest import PfData

_WORDS = {w: n for n, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
    "eighteen nineteen twenty".split())}
_NUM = r"(\d+|" + "|".join(_WORDS) + r")"
MAX_COUNT = 50  # larger numbers in objective text are not objective counts (gold, years)


def _number(s: str) -> int:
    return int(s) if s.isdigit() else _WORDS[s.lower()]


def _stem(word: str) -> str:
    """The word without its ending, so plurals match ("Highwaymen" for "Highwayman", "Bandanas")."""
    return re.escape(word[:-2] if len(word) > 5 else word[:-1] if len(word) > 3 else word)


def objective_count(text: str | None, name: str | None) -> int | None:
    """How many of `name` the objective text asks for, or None when the text does not say.

    "Kill 10 Kobold Vermin" -> 10, "five pieces of Tough Condor Meat" -> 5, "Kill 7 Tidehunters" (Murloc Tidehunter)
    -> 7; a text with no number at all, or one naming the thing with "a"/"the"/"his", asks for one.
    """
    if not text or not name:
        return None
    words = re.findall(r"[\w'-]+", name)
    if not words:
        return None
    full = r"\W+".join(re.escape(w) for w in words[:-1]) + (r"\W+" if len(words) > 1 else "") + _stem(words[-1])
    tail = r"\W+".join([re.escape(w) for w in words[-2:-1]] + [_stem(words[-1])])
    for pattern in (full, tail, _stem(words[-1])):
        # up to three words between the number and the name ("pieces of"), none of them another number
        m = re.search(r"\b" + _NUM + r"\s+(?:(?!" + _NUM + r"\b)[\w'-]+\s+){0,3}?" + pattern, text, re.I)
        if m:
            n = _number(m.group(1))
            return n if 0 < n <= MAX_COUNT else None
    if not re.search(r"\b" + _NUM + r"\b", text, re.I) or re.search(re.escape(name), text, re.I):
        return 1
    if re.search(r"\b(?:an?|the|his|her)\s+(?:[\w'-]+\s+){0,2}?" + tail, text, re.I):
        return 1
    return None


def unit_level(lvl) -> float | None:
    """pfQuest unit level ("12", "1-2", 12) -> its mean, or None when unknown."""
    if isinstance(lvl, (int, float)):
        return float(lvl)
    nums = [int(n) for n in re.findall(r"\d+", str(lvl or ""))]
    return sum(nums) / len(nums) if nums else None


def kill_plan(pq: dict, pf: PfData) -> list[dict]:
    """One entry per unit or item objective: {"kind", "id", "count", "chance", "level"}.

    count: how many the text asks for (None: unknown). For items, chance is the best drop chance in percent among
    the units that drop it and level that unit's level; chance 0 means only objects give it (no kills). For units,
    chance is None and level is the unit's level.
    """
    obj = pq.get("obj") or {}
    text = pq.get("objectiveText")
    plan: list[dict] = []
    for uid in dict.fromkeys(obj.get("U") or []):
        unit = pf.units.get(uid, {})
        plan.append({"kind": "kill", "id": uid, "count": objective_count(text, unit.get("name")), "chance": None,
                     "level": unit_level(unit.get("lvl"))})
    for iid in dict.fromkeys(obj.get("I") or []):
        item = pf.items.get(iid, {})
        chances = item.get("chances") or {}
        best = max(chances, key=lambda u: (chances[u], -u), default=None)
        if best is not None:
            chance, level = float(chances[best]), unit_level(pf.units.get(best, {}).get("lvl"))
        else:
            chance, level = (0.0 if item.get("objects") else None), None
        plan.append({"kind": "collect", "id": iid, "count": objective_count(text, item.get("name")),
                     "chance": chance, "level": level})
    return plan
