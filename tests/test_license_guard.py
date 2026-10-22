"""License gate: forbidden third-party sources must never be tracked."""
import subprocess

from pipeline.config import ROOT

FORBIDDEN = ["QuestieDB", "questie", "RXPGuides", "zygor", "Guidelime_", "TomTom"]
EXCLUDED = {"tests/test_license_guard.py", "THIRD_PARTY.md"}
EXCLUDED_PREFIXES = ("docs/",)


def _git_ls_files(*args: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", *args], cwd=ROOT, check=True, capture_output=True
    ).stdout
    return [p for p in out.decode("utf-8", errors="replace").split("\0") if p]


def find_violations(files: list[str]) -> list[str]:
    needles = [s.lower() for s in FORBIDDEN]
    hits = []
    for rel in files:
        if rel in EXCLUDED or rel.startswith(EXCLUDED_PREFIXES):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="replace").lower()
        hits.extend(f"{rel}: {n}" for n in needles if n in text)
    return hits


def test_no_forbidden_sources():
    assert find_violations(_git_ls_files()) == []


def test_no_raw_dir_tracked():
    assert _git_ls_files("raw/") == []
