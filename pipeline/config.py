"""Central constants for the ForeverXP data pipeline."""
from pathlib import Path

DATA_BUILD = "1.60.1.70532"

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "raw"
DATA_DIR = ROOT / "data"

SOURCE_LINEAGE: dict[str, str] = {
    "wago-db2": "blizzard-client",
    "pfquest": "vanilla-emu",
    "cmangos": "vanilla-emu",
    "wowhead-manual": "wowhead",
    "recorder": "ingame",
    "lodestar": "community",
    "mittenquest": "community",
    "evergreen": "community",
    "polestar": "community",
    "rxp-free": "community",
    "tugs": "community",
}

# Vanilla race bit mask. The Skyborne bit is unknown, so it is intentionally absent.
RACE_BITS: dict[str, int] = {
    "Human": 1,
    "Orc": 2,
    "Dwarf": 4,
    "Night Elf": 8,
    "Undead": 16,
    "Tauren": 32,
    "Gnome": 64,
    "Troll": 128,
}

# Vanilla class bit mask (pfQuest `class`). Bits not listed here become "unknown-bit-<n>".
CLASS_BITS: dict[str, int] = {
    "Warrior": 1,
    "Paladin": 2,
    "Hunter": 4,
    "Rogue": 8,
    "Priest": 16,
    "Shaman": 64,
    "Mage": 128,
    "Warlock": 256,
    "Druid": 1024,
}
