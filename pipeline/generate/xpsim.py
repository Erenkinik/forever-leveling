"""XP estimate. wago has no per-quest difficulty and no player XP curve, so this is a guess."""
from dataclasses import dataclass

from pipeline.generate.config import DEFAULT_XP_DIFFICULTY, LEVEL_CAP, PLAYER_XP_TO_LEVEL


def quest_level(q: dict) -> int:
    """The level used for quest XP: `level`, or `minLevel` when the level is unknown."""
    return q["level"] if q.get("level") is not None else q["minLevel"]


def quest_xp(level: int, table: dict[int, list[int]]) -> int:
    """XP for a quest of this level at DEFAULT_XP_DIFFICULTY; 0 when the level is not in the table."""
    row = table.get(level)
    return row[DEFAULT_XP_DIFFICULTY] if row else 0


@dataclass(frozen=True)
class XpState:
    level: int
    xp: int

    def gain(self, amount: int) -> "XpState":
        """Add XP, levelling up and carrying the overflow; stops at LEVEL_CAP with 0 XP."""
        level, xp = self.level, self.xp + amount
        while level < LEVEL_CAP and xp >= PLAYER_XP_TO_LEVEL[level]:
            xp -= PLAYER_XP_TO_LEVEL[level]
            level += 1
        return XpState(level, 0 if level >= LEVEL_CAP else xp)


def estimate_levels(route: dict, quests: dict[int, dict], table: dict[int, list[int]]) -> dict[str, int]:
    """Step id -> estimated level when the step starts, replaying the generator's model.

    Turn-ins add quest XP (after the step), grind steps raise the level to untilLevel and reset XP, and
    quests missing from `quests` give no XP. The generator and the validator share this estimate.
    """
    state = XpState(route["levelRange"][0], 0)
    levels: dict[str, int] = {}
    for step in route["steps"]:
        levels[step["id"]] = state.level
        if step["type"] == "grind" and step["untilLevel"] > state.level:
            state = XpState(step["untilLevel"], 0)
        elif step["type"] == "turnin" and step.get("questId") in quests:
            state = state.gain(quest_xp(quest_level(quests[step["questId"]]), table))
    return levels
