"""ForeverXP data pipeline CLI: python -m pipeline <command>."""
import argparse
import json
import os
import sys

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("normalize", help="build data/canonical/quests.json").set_defaults(func=cmd_normalize)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
