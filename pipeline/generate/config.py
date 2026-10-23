"""Constants for route generation, kept in one place."""

LEVEL_CAP = 35
HUB_RADIUS = 6.0
# spec 6.4-6: the only grind rule. A quest is taken only when the estimated level is at least its minLevel (the
# game refuses it before) and at most QUEST_LEVEL_MARGIN below its level (yellow or orange, not red). A hub's
# quests that are not doable yet wait for the XP of the doable ones; when none is doable, a grind step goes to the
# lowest level that makes one doable. Stricter than the validator's over-level slack (LEVEL_SLACK = 3 in
# pipeline/validate/semantic.py); keep it so.
QUEST_LEVEL_MARGIN = 2

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
    24: 31700, 25: 34000, 26: 36400, 27: 38900, 28: 41400, 29: 44300, 30: 47400, 31: 50800,
    32: 54500, 33: 58600, 34: 62800,
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

# Zone order suggestions (pipeline/generate/zone_suggest.py). A draft for a human to review, spec 8.2.
START_ZONES: dict[str, str] = {
    "Human": "Elwynn Forest",
    "Dwarf": "Dun Morogh",
    "Gnome": "Dun Morogh",
    "Night Elf": "Teldrassil",
    "Orc": "Durotar",
    "Troll": "Durotar",
    "Undead": "Tirisfal Glades",
    "Tauren": "Mulgore",
}
CITY_ZONES = frozenset({"Stormwind City", "Ironforge", "Darnassus", "Orgrimmar", "Undercity", "Thunder Bluff"})
CONTINENTS: dict[int, str] = {1414: "Kalimdor", 1415: "Eastern Kingdoms"}
# A zone needs at least this many usable quests of known level to be suggested.
MIN_ZONE_QUESTS = 10
# Picking the next zone: lowest median level, plus this many levels for a zone on the other continent.
CONTINENT_SWITCH_PENALTY = 5
# A zone whose median is more than this below the highest median reached so far is dropped (too low).
ZONE_BEHIND = 2

# Route id -> (race, faction) for routes whose zone order can be suggested. Skyborne needs manual data.
ROUTES: dict[str, tuple[str, str]] = {
    "human": ("Human", "Alliance"),
    "dwarf": ("Dwarf", "Alliance"),
    "gnome": ("Gnome", "Alliance"),
    "night-elf": ("Night Elf", "Alliance"),
    "orc": ("Orc", "Horde"),
    "troll": ("Troll", "Horde"),
    "undead": ("Undead", "Horde"),
    "tauren": ("Tauren", "Horde"),
}

# Classes each race can play (vanilla), for class quests: a route keeps a class quest when its race can play one
# of the quest's classes, and marks its steps classOnly with those classes.
RACE_CLASSES: dict[str, tuple[str, ...]] = {
    "Human": ("Warrior", "Paladin", "Rogue", "Priest", "Mage", "Warlock"),
    "Dwarf": ("Warrior", "Paladin", "Hunter", "Rogue", "Priest"),
    "Gnome": ("Warrior", "Rogue", "Mage", "Warlock"),
    "Night Elf": ("Warrior", "Hunter", "Rogue", "Priest", "Druid"),
    "Orc": ("Warrior", "Hunter", "Rogue", "Shaman", "Warlock"),
    "Troll": ("Warrior", "Hunter", "Rogue", "Priest", "Shaman", "Mage"),
    "Undead": ("Warrior", "Rogue", "Priest", "Mage", "Warlock"),
    "Tauren": ("Warrior", "Hunter", "Shaman", "Druid"),
}

# Kill XP. Counts, drop chances and mob levels come from the quest's `kills` (pipeline/normalize/kills.py); these
# fill in what the data does not say. A kill objective of unknown count is taken as this many kills, a collect
# objective of unknown count and drop chance as this many kills, and an unknown drop chance as this percent.
KILLS_PER_KILL_OBJECTIVE = 8
KILLS_PER_COLLECT = 10
DEFAULT_DROP_CHANCE = 50.0
# A rare drop is still got within this many kills (players use other droppers, or the item is shared).
MAX_KILLS_PER_OBJECTIVE = 40

# Travel: a map change across continents is a boat (Alliance) or zeppelin (Horde) trip. Teldrassil is an
# island, so going to or from it is a boat even within Kalimdor.
CONTINENT_TRAVEL = {"Alliance": "boat", "Horde": "zeppelin"}
ISLAND_MAPS = frozenset({1438})  # Teldrassil
# Leaving Zephras Isle (the Skyborne start) is the Skyborne portal to the faction's capital, not a ship.
PORTAL_MAPS = frozenset({2521})

# Flight paths (pipeline/generate/flight.py). A flight master within DISCOVER_YARDS of a step is found then (a
# flightpath step). A map change on one continent flies when walking to a found flight master, flying and walking
# on saves at least FLY_MIN_SAVING_YARDS of walking; a flight counts FLIGHT_SPEED_RATIO times shorter than a walk
# (about 7 yards a second on foot, about 30 in the air).
DISCOVER_YARDS = 150
FLIGHT_SPEED_RATIO = 4.0
FLY_MIN_SAVING_YARDS = 600
