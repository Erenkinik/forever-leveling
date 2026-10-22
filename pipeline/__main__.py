"""ForeverXP data pipeline CLI: python -m pipeline <command>."""
import argparse
import json
import os
import sys
from pathlib import Path

from pipeline.config import DATA_BUILD, DATA_DIR, RAW_DIR


def _write_text_atomic(out: Path, text: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)


def _canonical_path() -> Path:
    return DATA_DIR / "canonical" / "quests.json"


def _build_records() -> list[dict]:
    from pipeline.ingest.manual import load_manual
    from pipeline.ingest.pfquest import load_pfquest
    from pipeline.ingest.wago import load_quest_ids, load_zone_to_uimap
    from pipeline.normalize.quests import build_canonical

    wago = RAW_DIR / "wago" / DATA_BUILD
    return build_canonical(
        load_pfquest(RAW_DIR / "pfquest"),
        load_quest_ids(wago),
        load_zone_to_uimap(wago),
        load_manual(DATA_DIR / "manual" / "quests.yaml"),
    )


def _serialize(records: list[dict]) -> str:
    return json.dumps(records, indent=1, ensure_ascii=False) + "\n"


def cmd_normalize(args) -> int:
    from pipeline.normalize.quests import validation_errors

    try:
        records = _build_records()
    except FileNotFoundError as exc:
        print(f"missing raw data: {exc.filename} (run the fetch step first)", file=sys.stderr)
        return 1
    errors = validation_errors(records)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    out = _canonical_path()
    text = _serialize(records)
    if args.check:
        if not out.is_file():
            print(f"missing canonical quests: {out} (run normalize)", file=sys.stderr)
            return 1
        if out.read_bytes() != text.encode("utf-8"):
            print(f"{out} is out of date; run python -m pipeline normalize", file=sys.stderr)
            return 1
        print(f"up to date: {out}")
        return 0
    _write_text_atomic(out, text)
    print(f"wrote {len(records)} quests to {out}")
    return 0


def cmd_crosscheck(_args) -> int:
    from pipeline.crosscheck.report import render_markdown, summarize

    src = _canonical_path()
    if not src.is_file():
        print(f"missing canonical quests: {src} (run normalize)", file=sys.stderr)
        return 1
    summary = summarize(json.loads(src.read_text(encoding="utf-8")))
    out = DATA_DIR / "reports" / f"crosscheck-{DATA_BUILD}.md"
    _write_text_atomic(out, render_markdown(summary, DATA_BUILD))
    print(
        f"wrote {out}: needs_manual={len(summary.needs_manual)} in_scope={summary.in_scope} "
        f"in_scope_known={summary.in_scope_known} in_scope_unknown_level={summary.in_scope_unknown_level}"
    )
    return 0


def cmd_validate(args) -> int:
    from pipeline.ingest.wago import load_uimaps
    from pipeline.validate.semantic import check_route

    if args.all == bool(args.route):
        print("give exactly one of --all or <route.json>", file=sys.stderr)
        return 1
    paths = sorted((DATA_DIR / "routes").glob("*.json")) if args.all else [Path(args.route)]
    quests_path = _canonical_path()
    wago = RAW_DIR / "wago" / DATA_BUILD
    if not quests_path.is_file():
        print(f"missing canonical quests: {quests_path} (run normalize)", file=sys.stderr)
        return 1
    if not (wago / "UiMap.csv").is_file():
        print(f"missing raw wago data: {wago / 'UiMap.csv'}", file=sys.stderr)
        return 1
    quests = {q["id"]: q for q in json.loads(quests_path.read_text(encoding="utf-8"))}
    known_maps = frozenset(load_uimaps(wago))
    total = 0
    for path in paths:
        try:
            route = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"cannot read route file {path}: {exc}", file=sys.stderr)
            return 1
        for issue in check_route(route, quests, known_maps):
            total += 1
            print(f"{path.name}: [{issue.rule}] {issue.stepId or '-'}: {issue.message}")
    print(f"{len(paths)} routes checked, {total} issues")
    return 1 if total else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    norm = sub.add_parser("normalize", help="build data/canonical/quests.json")
    norm.add_argument("--check", action="store_true", help="compare with the committed file; never writes")
    norm.set_defaults(func=cmd_normalize)
    sub.add_parser("crosscheck", help="write data/reports/crosscheck-<build>.md").set_defaults(
        func=cmd_crosscheck
    )
    val = sub.add_parser("validate", help="semantic route validation")
    val.add_argument("--all", action="store_true", help="validate data/routes/*.json")
    val.add_argument("route", nargs="?", help="a single route file")
    val.set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
