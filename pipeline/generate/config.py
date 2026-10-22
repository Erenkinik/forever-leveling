"""Constants for route generation, kept in one place."""

LEVEL_CAP = 30
HUB_RADIUS = 6.0
# spec 6.4-6: the only grind rule. Before a chunk of quests is accepted, the estimated level must be
# at least max(minLevel) - GRIND_TRIGGER, else a grind step is inserted. This is stricter than the
# validator's over-level slack (LEVEL_SLACK = 3 in pipeline/validate/semantic.py); keep it below that.
GRIND_TRIGGER = 2

# v1 rule: a quest whose level is more than this above its start zone's median level is
# excluded as a zone outlier (event quests, high chains starting in low zones).
ZONE_OUTLIER_SPREAD = 6

# Research value, not verified against Forever.
QUEST_LOG_LIMIT = 40

# QuestXP column index; a guess.
DEFAULT_XP_DIFFICULTY = 5

# Level -> XP needed for the next level. Vanilla values, not verified for Forever.
PLAYER_XP_TO_LEVEL: dict[int, int] = {
    1: 400, 2: 900, 3: 1400, 4: 2100, 5: 2800, 6: 3600, 7: 4500, 8: 5400, 9: 6500,
    10: 7600, 11: 8800, 12: 10100, 13: 11400, 14: 12900, 15: 14400, 16: 16000,
    17: 17700, 18: 19400, 19: 21300, 20: 23200, 21: 25200, 22: 27300, 23: 29400,
    24: 31700, 25: 34000, 26: 36400, 27: 38900, 28: 41400, 29: 44300,
}

BETA_BLOCKING_RULES = (
    "schema",
    "turnin-before-accept",
    "complete-before-accept",
    "accepted-never-closed",
    "unknown-map",
    "duplicate-step-id",
    "not-in-forever",
    "unknown-quest",
    "prereq-not-done",
)
