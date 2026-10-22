"""XP estimate. Quest XP comes from the client's QuestXP table at one guessed difficulty column (the open data has
no per-quest difficulty); kill XP from the objectives' counts, drop chances and mob levels; both use the vanilla
level-difference rules. The player XP curve is vanilla's, not verified for Forever."""
import math
from dataclasses import dataclass

from pipeline.generate.config import (
    DEFAULT_DROP_CHANCE, DEFAULT_XP_DIFFICULTY, KILLS_PER_COLLECT, KILLS_PER_KILL_OBJECTIVE, LEVEL_CAP,
    MAX_KILLS_PER_OBJECTIVE, PLAYER_XP_TO_LEVEL,
)


def quest_level(q: dict) -> int:
    """The level used for quest XP: `level`, or `minLevel` when the level is unknown."""
    return q["level"] if q.get("level") is not None else q["minLevel"]


# Vanilla quest XP by how many levels the player is above the quest: full up to 5, then less, 10% from 10 up.
_QUEST_XP_OVER = {6: 0.8, 7: 0.6, 8: 0.4, 9: 0.2}


def quest_xp(level: int, table: dict[int, list[int]], player_level: int | None = None) -> int:
    """XP for a quest of this level at DEFAULT_XP_DIFFICULTY, reduced when the player is more than 5 levels above
    it; 0 when the level is not in the table."""
    row = table.get(level)
    if not row:
        return 0
    over = 0 if player_level is None else player_level - level
    factor = 1.0 if over <= 5 else _QUEST_XP_OVER.get(over, 0.1)
    return int(row[DEFAULT_XP_DIFFICULTY] * factor)


def _zero_difference(player_level: int) -> int:
    """Vanilla "zero difference" value: how fast XP falls off for mobs below the player."""
    for top, zd in ((7, 5), (9, 6), (11, 7), (15, 8), (19, 9), (29, 11), (39, 12)):
        if player_level <= top:
            return zd
    return 13


def gray_level(player_level: int) -> int:
    """Mobs at or below this level give no XP (vanilla)."""
    return 0 if player_level <= 5 else player_level - player_level // 10 - 5


def mob_xp(mob_level: float, player_level: int | None = None) -> int:
    """Vanilla XP for one normal mob: 45 + 5 * player level, +5% per level the mob is above the player (at most 4),
    falling off for lower mobs and 0 at the gray level. Without a player level, the mob is taken as the player's."""
    mob = round(mob_level)
    player = mob if player_level is None else player_level
    base = 45 + 5 * player
    if mob >= player:
        return int(base * (1 + 0.05 * min(mob - player, 4)))
    if mob <= gray_level(player):
        return 0
    return int(base * (1 - (player - mob) / _zero_difference(player)))


def objective_kills(entry: dict) -> int:
    """Kills one `kills` entry needs: the count for a kill objective; count / drop chance for a collect objective
    (none when only objects give the item), at most MAX_KILLS_PER_OBJECTIVE."""
    count = entry.get("count")
    if entry["kind"] == "kill":
        return count or KILLS_PER_KILL_OBJECTIVE
    chance = entry.get("chance")
    if chance == 0:
        return 0
    if count is None and chance is None:
        return KILLS_PER_COLLECT
    kills = math.ceil((count or 1) * 100 / (chance or DEFAULT_DROP_CHANCE))
    return min(kills, MAX_KILLS_PER_OBJECTIVE)


def kill_xp(q: dict, player_level: int | None = None) -> int:
    """XP from the kills a quest's objectives need, each mob at its own level (the quest's when unknown).

    Quests without `kills` data fall back to KILLS_PER_* kills per unit and item objective at the quest's level.
    """
    fallback_level = quest_level(q)
    if "kills" in q:
        return sum(objective_kills(e) * mob_xp(e["level"] if e.get("level") is not None else fallback_level,
                                               player_level) for e in q["kills"])
    obj = q.get("objectives") or {}
    kills = KILLS_PER_KILL_OBJECTIVE * len(obj.get("units", [])) + KILLS_PER_COLLECT * len(obj.get("items", []))
    return kills * mob_xp(fallback_level, player_level) if kills else 0


def shared_xp(q: dict) -> bool:
    """Whether the quest's XP counts in the route's level estimate: class quests do not, so the estimate holds for
    every class (a class doing its own quests is a little ahead of it)."""
    return not q.get("classes")


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

    Complete steps add kill XP and turn-ins add quest XP (both after the step, at the level the step starts at),
    grind steps raise the level to untilLevel and reset XP, and quests missing from `quests` or for some classes
    only (shared_xp) give no XP. The generator and the validator share this estimate.
    """
    state = XpState(route["levelRange"][0], 0)
    levels: dict[str, int] = {}
    for step in route["steps"]:
        levels[step["id"]] = state.level
        if step["type"] == "grind" and step["untilLevel"] > state.level:
            state = XpState(step["untilLevel"], 0)
        elif step.get("questId") in quests and not shared_xp(quests[step["questId"]]):
            continue
        elif step["type"] == "complete" and step.get("questId") in quests:
            state = state.gain(kill_xp(quests[step["questId"]], state.level))
        elif step["type"] == "turnin" and step.get("questId") in quests:
            state = state.gain(quest_xp(quest_level(quests[step["questId"]]), table, state.level))
    return levels
