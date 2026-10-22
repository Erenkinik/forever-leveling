"""ForeverXP data pipeline CLI: python -m pipeline <command>."""
import argparse
import json
import os
import sys
from pathlib import Path

from pipeline.config import DATA_BUILD, DATA_DIR, RAW_DIR


def cmd_normalize(_args) -> int:
    from pipeline.ingest.manual import load_manual
    from pipeline.ingest.pfquest import load_pfquest
    from pipeline.ingest.wago import load_quest_ids, load_zone_to_uimap
    from pipeline.normalize.quests import build_canonical, validation_errors

    wago = RAW_DIR / "wago" / DATA_BUILD
    records = build_canonical(
        load_pfquest(RAW_DIR / "pfquest"),
        load_quest_ids(wago),
        load_zone_to_uimap(wago),
        load_manual(DATA_DIR / "manual" / "quests.yaml"),
    )
    errors = validation_errors(records)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    out = DATA_DIR / "canonical" / "quests.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    try:
        tmp.write_text(json.dumps(records, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"wrote {len(records)} quests to {out}")
    return 0


def cmd_crosscheck(_args) -> int:
    from pipeline.crosscheck.report import render_markdown, summarize

    src = DATA_DIR / "canonical" / "quests.json"
    summary = summarize(json.loads(src.read_text(encoding="utf-8")))
    out = DATA_DIR / "reports" / f"crosscheck-{DATA_BUILD}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    try:
        tmp.write_text(render_markdown(summary, DATA_BUILD), encoding="utf-8")
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"wrote {out}: needs_manual={len(summary.needs_manual)} in_scope={summary.in_scope}")
    return 0


def cmd_validate(args) -> int:
    from pipeline.ingest.wago import load_uimaps
    from pipeline.validate.semantic import check_route

    if args.all == bool(args.route):
        print("give exactly one of --all or <route.json>", file=sys.stderr)
        return 1
    paths = sorted((DATA_DIR / "routes").glob("*.json")) if args.all else [Path(args.route)]
    quests_path = DATA_DIR / "canonical" / "quests.json"
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
        route = json.loads(path.read_text(encoding="utf-8"))
        for issue in check_route(route, quests, known_maps):
            total += 1
            print(f"{path.name}: [{issue.rule}] {issue.stepId or '-'}: {issue.message}")
    print(f"{len(paths)} routes checked, {total} issues")
    return 1 if total else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("normalize", help="build data/canonical/quests.json").set_defaults(func=cmd_normalize)
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
