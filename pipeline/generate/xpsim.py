"""XP estimate. wago has no per-quest difficulty and no player XP curve, so this is a guess."""
from dataclasses import dataclass

from pipeline.generate.config import DEFAULT_XP_DIFFICULTY, LEVEL_CAP, PLAYER_XP_TO_LEVEL


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
