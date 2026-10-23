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


def _with_lodestar(pf):
    """pfQuest's data plus the Zephras Isle (Skyborne) facts from Lodestar's guides in raw/lodestar, when there."""
    from pipeline.ingest.lodestar import load_lodestar, merge
    from pipeline.ingest.wago import load_uimap_parents, load_uimaps, load_zone_to_uimap

    wago = RAW_DIR / "wago" / DATA_BUILD
    names, parents = load_uimaps(wago), load_uimap_parents(wago)
    map_ids: dict[str, int] = {}
    for ui in sorted(names):
        if parents.get(ui):  # a map with no parent is a duplicate (Zephras Isle 2665)
            map_ids.setdefault(names[ui], ui)
    uimap_to_area: dict[int, int] = {}
    for area, ui in sorted(load_zone_to_uimap(wago).items()):
        uimap_to_area.setdefault(ui, area)
    return merge(pf, load_lodestar(RAW_DIR / "lodestar", map_ids, uimap_to_area))


def _build_records() -> list[dict]:
    from pipeline.ingest.manual import load_manual
    from pipeline.ingest.pfquest import load_pfquest
    from pipeline.ingest.wago import load_quest_ids, load_zone_to_uimap
    from pipeline.normalize.quests import build_canonical

    wago = RAW_DIR / "wago" / DATA_BUILD
    return build_canonical(
        _with_lodestar(load_pfquest(RAW_DIR / "pfquest")),
        load_quest_ids(wago),
        load_zone_to_uimap(wago),
        load_manual(DATA_DIR / "manual" / "quests.yaml"),
    )


def _uimaps_path() -> Path:
    return DATA_DIR / "canonical" / "uimaps.json"


def _build_uimaps() -> str:
    from pipeline.ingest.wago import load_uimap_parents, load_uimaps

    maps = load_uimaps(RAW_DIR / "wago" / DATA_BUILD)
    parents = load_uimap_parents(RAW_DIR / "wago" / DATA_BUILD)
    doc = {
        "build": DATA_BUILD,
        "maps": {str(k): maps[k] for k in sorted(maps)},
        "parents": {str(k): parents[k] for k in sorted(parents)},
    }
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def _questxp_path() -> Path:
    return DATA_DIR / "canonical" / "questxp.json"


def _build_questxp() -> str:
    from pipeline.ingest.wago import load_quest_xp

    table = load_quest_xp(RAW_DIR / "wago" / DATA_BUILD)
    doc = {"build": DATA_BUILD, "levels": {str(k): table[k] for k in sorted(table)}}
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def _taxi_path() -> Path:
    return DATA_DIR / "canonical" / "taxi.json"


def _build_taxi() -> str:
    import csv

    from pipeline.ingest.wago import load_uimap_parents, load_uimaps
    from pipeline.normalize.taxi import build_taxi

    wago = RAW_DIR / "wago" / DATA_BUILD

    def rows(table: str) -> list[dict]:
        with open(wago / f"{table}.csv", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    doc = build_taxi(rows("TaxiNodes"), rows("TaxiPath"), rows("UiMapAssignment"), load_uimaps(wago),
                     load_uimap_parents(wago))
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def _spawns_path() -> Path:
    return DATA_DIR / "canonical" / "spawns.json"


def _build_spawns(records: list[dict]) -> str:
    from pipeline.ingest.pfquest import load_pfquest
    from pipeline.ingest.wago import load_zone_to_uimap
    from pipeline.normalize.spawns import build_spawns

    doc = build_spawns(
        _with_lodestar(load_pfquest(RAW_DIR / "pfquest", require_items=True)), records,
        load_zone_to_uimap(RAW_DIR / "wago" / DATA_BUILD),
    )
    return json.dumps(doc, indent=None, ensure_ascii=False, separators=(",", ":")) + "\n"


def _serialize(records: list[dict]) -> str:
    return json.dumps(records, indent=1, ensure_ascii=False) + "\n"


def cmd_normalize(args) -> int:
    from pipeline.normalize.quests import validation_errors

    try:
        records = _build_records()
        uimaps_text = _build_uimaps()
        questxp_text = _build_questxp()
        spawns_text = _build_spawns(records)
        taxi_text = _build_taxi()
    except FileNotFoundError as exc:
        print(f"missing raw data: {exc.filename} (run the fetch step first)", file=sys.stderr)
        return 1
    errors = validation_errors(records)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    targets = [
        ("quests", _canonical_path(), _serialize(records)),
        ("uimaps", _uimaps_path(), uimaps_text),
        ("spawns", _spawns_path(), spawns_text),
        ("questxp", _questxp_path(), questxp_text),
        ("taxi", _taxi_path(), taxi_text),
    ]
    if args.check:
        for label, out, text in targets:
            if not out.is_file():
                print(f"missing canonical {label}: {out} (run normalize)", file=sys.stderr)
                return 1
            if out.read_bytes() != text.encode("utf-8"):
                print(f"{out} is out of date; run python -m pipeline normalize", file=sys.stderr)
                return 1
        print("up to date: " + ", ".join(str(out) for _, out, _t in targets))
        return 0
    for _, out, text in targets:
        _write_text_atomic(out, text)
    print(
        f"wrote {len(records)} quests to {targets[0][1]}, uimaps to {targets[1][1]}, "
        f"spawns to {targets[2][1]}, questxp to {targets[3][1]} and flight paths to {targets[4][1]}"
    )
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


def _route_levels(route, quests: dict[int, dict], xp_table: dict[int, list[int]]) -> dict[str, int] | None:
    """Shared level estimate for check_route; None for a route the schema rejects (check_route reports it)."""
    from pipeline.generate.xpsim import estimate_levels
    from pipeline.schema import validate as schema_validate

    if schema_validate("route", route):
        return None
    return estimate_levels(route, quests, xp_table)


def cmd_validate(args) -> int:
    from pipeline.canonical import load_questxp_canonical, load_uimaps_canonical
    from pipeline.generate.config import BETA_BLOCKING_RULES
    from pipeline.validate.semantic import check_route

    if args.all == bool(args.route):
        print("give exactly one of --all or <route.json>", file=sys.stderr)
        return 1
    paths = (
        sorted(p for p in (DATA_DIR / "routes").glob("*.json") if not p.name.endswith(".generated.json"))
        if args.all
        else [Path(args.route)]
    )
    quests_path = _canonical_path()
    if not quests_path.is_file():
        print(f"missing canonical quests: {quests_path} (run normalize)", file=sys.stderr)
        return 1
    for label, path in (("uimaps", _uimaps_path()), ("questxp", _questxp_path())):
        if not path.is_file():
            print(f"missing canonical {label}: {path} (run normalize)", file=sys.stderr)
            return 1
    quests = {q["id"]: q for q in json.loads(quests_path.read_text(encoding="utf-8"))}
    known_maps = frozenset(load_uimaps_canonical(DATA_DIR))
    xp_table = load_questxp_canonical(DATA_DIR)
    total = 0
    blocking = 0
    for path in paths:
        try:
            route = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"cannot read route file {path}: {exc}", file=sys.stderr)
            return 1
        issues = check_route(route, quests, known_maps, levels=_route_levels(route, quests, xp_table))
        # Tier-aware like cmd_generate; a missing or invalid tier is treated as full (strict).
        beta = isinstance(route, dict) and route.get("releaseTier") == "beta"
        for issue in issues:
            if beta and issue.rule not in BETA_BLOCKING_RULES:
                continue
            blocking += 1
            print(f"{path.name}: [{issue.rule}] {issue.stepId or '-'}: {issue.message}")
        for issue in issues:
            if beta and issue.rule not in BETA_BLOCKING_RULES:
                total += 1
                print(f"{path.name}: non-blocking (beta) [{issue.rule}] {issue.stepId or '-'}: {issue.message}")
    total += blocking
    print(f"{len(paths)} routes checked, {total} issues, {blocking} blocking")
    return 1 if blocking else 0


def _json_text(doc) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def _render_route_report(route: dict, report: dict, issues: list) -> str:
    import re

    gap_reasons: dict[str, int] = {}
    for step in route["steps"]:
        if step["type"] == "gap":
            key = re.sub(r"\d+", "N", step.get("reason", ""))
            gap_reasons[key] = gap_reasons.get(key, 0) + 1
    by_rule: dict[str, list] = {}
    for issue in issues:
        by_rule.setdefault(issue.rule, []).append(issue)

    lines = [
        f"# Rota raporu: {route['id']}",
        "",
        f"- Veri sürümü: {route['dataBuild']}",
        f"- Yayın seviyesi: {route['releaseTier']}",
        f"- Görevlerle ulaşılan tahmini seviye: {report['questLevel']} "
        "(görev XP'si + hedeflerdeki tahmini yaratık XP'si)",
        f"- Tahmini son seviye: {report['estimatedFinalLevel']}",
        f"- Boşluk (gap) adımı: {report['gaps']}",
        "",
        "## Adım sayıları",
        "",
    ]
    lines += [f"- {kind}: {n}" for kind, n in report["stepCounts"].items()]
    lines += ["", "## Elenen görevler (nedene göre)", ""]
    listed = report.get("excludedIds", {})
    lines += [
        f"- {reason}: {n}" + (f" (kimlikler: {', '.join(map(str, listed[reason]))})" if reason in listed else "")
        for reason, n in sorted(report["excluded"].items())
    ] or ["- yok"]
    pulled = report.get("pulledIn", [])
    lines += ["", "## Rotaya çekilen önkoşullar (başka bölgede başlıyor)", ""]
    lines += [f"- {len(pulled)} görev: {', '.join(map(str, pulled))}"] if pulled else ["- yok"]
    lines += ["", "## Boşluk nedenleri (sayıyla; N bir sayıyı gösterir)", ""]
    lines += [f"- {reason}: {n}" for reason, n in sorted(gap_reasons.items())] or ["- yok"]
    lines += ["", "## Engellemeyen denetim bulguları (kurala göre)", ""]
    if by_rule:
        for rule in sorted(by_rule):
            lines.append(f"### {rule} ({len(by_rule[rule])})")
            lines.append("")
            lines += [f"- {i.stepId or '-'}: {i.message}" for i in by_rule[rule]]
            lines.append("")
    else:
        lines += ["- yok", ""]
    lines += [
        "## Not",
        "",
        "XP değerleri bir tahmindir (wago'da görev başına zorluk indeksi ve oyuncu XP eğrisi yok). "
        "Tahmin rotanın seviye aralığını belirlemez; yalnız grind adımlarında ve tahmini son seviyede kullanılır.",
        "",
    ]
    return "\n".join(lines)


def _without_generated_at(text: str) -> dict:
    doc = json.loads(text)
    doc.pop("generatedAt", None)
    return doc


def _keep_committed_generated_at(out: Path, text: str) -> str:
    """When the committed file differs from `text` only in generatedAt, keep its generatedAt (no churn)."""
    try:
        committed = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return text  # absent or unreadable: write the fresh output
    if not isinstance(committed, dict) or "generatedAt" not in committed:
        return text
    doc = json.loads(text)
    stamp = committed.pop("generatedAt")
    if committed != {k: v for k, v in doc.items() if k != "generatedAt"}:
        return text
    doc["generatedAt"] = stamp
    return _json_text(doc)


def cmd_generate(args) -> int:
    from datetime import datetime, timezone

    from pipeline.canonical import (
        load_questxp_canonical, load_spawns_canonical, load_taxi_canonical, load_uimap_parents_canonical,
        load_uimaps_canonical,
    )
    from pipeline.generate import GenerationError
    from pipeline.generate.config import BETA_BLOCKING_RULES
    from pipeline.generate.overrides import apply_overrides, load_overrides
    from pipeline.generate.steps import generate_route
    from pipeline.generate.zone_order import load_zone_order
    from pipeline.validate.semantic import check_route

    quests_path = _canonical_path()
    canonical = (("quests", quests_path), ("uimaps", _uimaps_path()), ("spawns", _spawns_path()),
                 ("questxp", _questxp_path()))
    for label, path in canonical:
        if not path.is_file():
            print(f"missing canonical {label}: {path} (run normalize)", file=sys.stderr)
            return 1
    order_path = DATA_DIR / "zone-order" / f"{args.route}.yaml"
    if not order_path.is_file():
        print(f"missing zone order: {order_path}", file=sys.stderr)
        return 1

    try:
        uimaps = load_uimaps_canonical(DATA_DIR)
        order = load_zone_order(order_path, uimaps, load_uimap_parents_canonical(DATA_DIR))
        patches = load_overrides(DATA_DIR / "overrides" / f"{args.route}.yaml")
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    quests = {q["id"]: q for q in json.loads(quests_path.read_text(encoding="utf-8"))}
    xp_table = load_questxp_canonical(DATA_DIR)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        generated, report = generate_route(
            order, quests, load_spawns_canonical(DATA_DIR), xp_table, args.tier, DATA_BUILD, now,
            continents=load_uimap_parents_canonical(DATA_DIR), taxi=load_taxi_canonical(DATA_DIR),
        )
    except (GenerationError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    route, errors = apply_overrides(generated, patches)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    issues = check_route(route, quests, frozenset(uimaps), levels=_route_levels(route, quests, xp_table))
    blocking = issues if args.tier == "full" else [i for i in issues if i.rule in BETA_BLOCKING_RULES]
    if blocking:
        print("\n".join(f"[{i.rule}] {i.stepId or '-'}: {i.message}" for i in blocking), file=sys.stderr)
        return 1
    rest = [i for i in issues if i not in blocking]

    routes = DATA_DIR / "routes"
    targets = [
        (routes / f"{args.route}.generated.json", _json_text(generated)),
        (routes / f"{args.route}.json", _json_text(route)),
        (DATA_DIR / "reports" / f"route-{args.route}.md", _render_route_report(route, report, rest)),
    ]
    if args.check:
        for out, text in targets:
            if not out.is_file():
                print(f"missing {out} (run generate)", file=sys.stderr)
                return 1
            try:
                if out.suffix == ".json":
                    same = _without_generated_at(out.read_text(encoding="utf-8")) == _without_generated_at(text)
                else:
                    same = out.read_bytes() == text.encode("utf-8")
            except (OSError, ValueError) as exc:
                print(f"cannot read {out}: {exc}; run python -m pipeline generate {args.route}", file=sys.stderr)
                return 1
            if not same:
                print(f"{out} is out of date; run python -m pipeline generate {args.route}", file=sys.stderr)
                return 1
        print("up to date: " + ", ".join(str(out) for out, _t in targets))
        return 0
    for out, text in targets:
        if out.suffix == ".json":
            text = _keep_committed_generated_at(out, text)
        _write_text_atomic(out, text)
    print(
        f"wrote {len(route['steps'])} steps to {targets[1][0]} "
        f"(gaps={report['gaps']}, quest level={report['questLevel']}, final level={report['estimatedFinalLevel']})"
    )
    return 0


def _item_icons(root: Path) -> dict[str, int | None] | None:
    """Item id -> icon FileDataID written by `maps` (site/src/data/item-icons.json); None before maps ran."""
    path = root / "site" / "src" / "data" / "item-icons.json"
    return json.loads(path.read_text(encoding="utf-8"))["items"] if path.is_file() else None


def cmd_export(args) -> int:
    from pipeline.canonical import (
        load_questxp_canonical, load_spawns_canonical, load_taxi_canonical, load_uimaps_canonical,
    )
    from pipeline.export.lua import to_lua
    from pipeline.export.site import to_site_json
    from pipeline.export.timing import step_seconds

    if args.all == bool(args.route):
        print("give exactly one of --all or <route>", file=sys.stderr)
        return 1
    routes_dir = DATA_DIR / "routes"
    paths = (
        sorted(p for p in routes_dir.glob("*.json") if not p.name.endswith(".generated.json"))
        if args.all
        else [routes_dir / f"{args.route}.json"]
    )
    if not paths:
        print("0 routes exported")
        return 0
    for label, path in (("quests", _canonical_path()), ("uimaps", _uimaps_path()), ("spawns", _spawns_path()),
                        ("questxp", _questxp_path())):
        if not path.is_file():
            print(f"missing canonical {label}: {path} (run normalize)", file=sys.stderr)
            return 1
    quests = {q["id"]: q for q in json.loads(_canonical_path().read_text(encoding="utf-8"))}
    uimaps = load_uimaps_canonical(DATA_DIR)
    spawns = load_spawns_canonical(DATA_DIR)
    xp_table = load_questxp_canonical(DATA_DIR)
    root = DATA_DIR.parent
    item_icons = _item_icons(root)
    taxi = load_taxi_canonical(DATA_DIR)
    outputs = []
    for path in paths:
        try:
            route = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"cannot read route file {path}: {exc}", file=sys.stderr)
            return 1
        try:
            levels = _route_levels(route, quests, xp_table)
            site = to_site_json(route, quests, spawns, uimaps, levels, item_icons,
                                step_seconds(route, quests, levels, taxi))
            outputs.append((path.stem, _json_text(site), to_lua(route)))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f"cannot export route file {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    for name, site_text, lua_text in outputs:
        _write_text_atomic(root / "site" / "src" / "data" / f"{name}.json", site_text)
        _write_text_atomic(root / "addon" / "ForeverXP" / "Data" / f"{name}.lua", lua_text)
    print(f"{len(outputs)} routes exported")
    return 0


def _is_reviewed_order(path: Path) -> bool:
    """True when a zone order file parses and says `reviewed: true`; unreadable files are not reviewed."""
    import yaml

    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return False
    return isinstance(doc, dict) and doc.get("reviewed") is True


def cmd_suggest_zones(args) -> int:
    from pipeline.canonical import load_uimap_parents_canonical, load_uimaps_canonical
    from pipeline.generate.config import ROUTES
    from pipeline.generate.zone_suggest import render_yaml, suggest_zones

    routes = sorted(ROUTES) if args.all else args.routes
    unknown = [r for r in routes if r not in ROUTES]
    if not routes or unknown:
        print(f"unknown or missing route {unknown}; known: {', '.join(sorted(ROUTES))}", file=sys.stderr)
        return 1
    for label, path in (("quests", _canonical_path()), ("uimaps", _uimaps_path())):
        if not path.is_file():
            print(f"missing canonical {label}: {path} (run normalize)", file=sys.stderr)
            return 1
    try:
        quests = {q["id"]: q for q in json.loads(_canonical_path().read_text(encoding="utf-8"))}
        names = load_uimaps_canonical(DATA_DIR)
        parents = load_uimap_parents_canonical(DATA_DIR)
        drafts = []
        for route in routes:
            race, faction = ROUTES[route]
            stats = suggest_zones(quests, names, parents, race, faction)
            drafts.append((route, stats, render_yaml(route, race, faction, stats)))
    except ValueError as exc:
        print(f"cannot suggest zones: {exc}", file=sys.stderr)
        return 1
    out_dir = DATA_DIR / "zone-order"
    existing = [out_dir / f"{r}.yaml" for r, _, _ in drafts if (out_dir / f"{r}.yaml").exists()]
    if existing and not args.force:
        print(f"refusing to overwrite {', '.join(p.name for p in existing)} (use --force)", file=sys.stderr)
        return 1
    reviewed = [p for p in existing if _is_reviewed_order(p)]
    if reviewed:
        print(f"refusing to overwrite reviewed zone orders {', '.join(p.name for p in reviewed)}", file=sys.stderr)
        return 1
    for route, stats, text in drafts:
        _write_text_atomic(out_dir / f"{route}.yaml", text)
        print(f"{route}: " + " -> ".join(f"{s.name} ({s.median:g})" for s in stats))
    return 0


def _route_map_ids() -> list[int]:
    ids: set[int] = set()
    for path in sorted((DATA_DIR / "routes").glob("*.json")):
        if path.name.endswith(".generated.json"):
            continue
        ids.update(s["mapId"] for s in json.loads(path.read_text(encoding="utf-8")).get("steps", []))
    return sorted(ids)


def _route_collect_items() -> list[int]:
    """Items that the routes' complete steps ask to collect (their icons show in the quest text)."""
    quests = {q["id"]: q for q in json.loads(_canonical_path().read_text(encoding="utf-8"))}
    items: set[int] = set()
    for path in sorted((DATA_DIR / "routes").glob("*.json")):
        if path.name.endswith(".generated.json"):
            continue
        for step in json.loads(path.read_text(encoding="utf-8")).get("steps", []):
            if step.get("type") == "complete" and step.get("questId") in quests:
                items.update((quests[step["questId"]].get("objectives") or {}).get("items", []))
    return sorted(items)


def cmd_maps(args) -> int:
    """Zone map images for every map a route visits, plus race crests and the quest parchment (site/public/art);
    --check needs no raw data."""
    site = DATA_DIR.parent / "site"
    index_path = site / "src" / "data" / "maps.json"
    out_dir = site / "public" / "maps"
    art_dir = site / "public" / "art"
    icons_path = site / "src" / "data" / "item-icons.json"
    map_ids = _route_map_ids()
    if args.check:
        doc = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {}
        index = doc.get("maps", {})
        problems = [f"map {m}: not built (run python -m pipeline maps)" for m in map_ids if str(m) not in index]
        problems += [f"map {m}: image missing: {out_dir / f'{m}.webp'}" for m in map_ids
                     if index.get(str(m)) and not (out_dir / f"{m}.webp").is_file()]
        problems += [f"art {name}: image missing: {art_dir / f'{name}.webp'}" for name in doc.get("art", [])
                     if not (art_dir / f"{name}.webp").is_file()]
        fonts_dir = site / "public" / "fonts"
        problems += [f"font {name}: missing: {fonts_dir / f'{name}.ttf'}" for name in doc.get("fonts", [])
                     if not (fonts_dir / f"{name}.ttf").is_file()]
        if icons_path.is_file():
            icons = json.loads(icons_path.read_text(encoding="utf-8")).get("items", {})
            problems += [f"item {i}: icon not built (run python -m pipeline maps)" for i in _route_collect_items()
                         if str(i) not in icons]
            problems += [f"item icon {f}: image missing" for f in sorted({f for f in icons.values() if f})
                         if not (art_dir / "items" / f"{f}.webp").is_file()]
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        print(f"up to date: {len(map_ids)} maps")
        return 0
    from pipeline.export.maps import build_art, build_fonts, build_item_icons, build_maps

    try:
        index = build_maps(map_ids, DATA_BUILD, RAW_DIR, out_dir)
        art = build_art(RAW_DIR, art_dir)
        icons = build_item_icons(_route_collect_items(), DATA_BUILD, RAW_DIR, art_dir / "items")
        fonts = build_fonts(RAW_DIR, site / "public" / "fonts")
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"cannot build maps: {exc}", file=sys.stderr)
        return 1
    _write_text_atomic(index_path, _json_text({"build": DATA_BUILD, "maps": index, "art": art, "fonts": fonts}))
    _write_text_atomic(icons_path, _json_text({"build": DATA_BUILD, "items": icons}))
    built = sum(1 for v in index.values() if v)
    print(f"wrote {built} map images to {out_dir} ({len(index) - built} maps have no art)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    norm = sub.add_parser(
        "normalize", help="build data/canonical/quests.json, uimaps.json, spawns.json, questxp.json and taxi.json"
    )
    norm.add_argument("--check", action="store_true", help="compare with the committed file; never writes")
    norm.set_defaults(func=cmd_normalize)
    sub.add_parser("crosscheck", help="write data/reports/crosscheck-<build>.md").set_defaults(
        func=cmd_crosscheck
    )
    val = sub.add_parser("validate", help="semantic route validation")
    val.add_argument("--all", action="store_true", help="validate data/routes/*.json")
    val.add_argument("route", nargs="?", help="a single route file")
    val.set_defaults(func=cmd_validate)
    gen = sub.add_parser("generate", help="generate data/routes/<route>.json from a zone order")
    gen.add_argument("route", help="route name, e.g. human")
    gen.add_argument("--tier", choices=["beta", "full"], default="beta")
    gen.add_argument("--check", action="store_true", help="compare with the committed files; never writes")
    gen.set_defaults(func=cmd_generate)
    exp = sub.add_parser("export", help="write site JSON and addon Lua from data/routes/*.json")
    exp.add_argument("--all", action="store_true", help="export every data/routes/*.json except *.generated.json")
    exp.add_argument("route", nargs="?", help="a single route name, e.g. human")
    exp.set_defaults(func=cmd_export)
    mp = sub.add_parser("maps", help="write site/public/maps/<uiMapId>.webp from the game's map art")
    mp.add_argument("--check", action="store_true", help="every route map has an image or a recorded absence")
    mp.set_defaults(func=cmd_maps)
    sug = sub.add_parser("suggest-zones", help="write draft data/zone-order/<route>.yaml from quest data")
    sug.add_argument("--all", action="store_true", help="every route in pipeline/generate/config.py ROUTES")
    sug.add_argument("--force", action="store_true", help="overwrite existing zone order files")
    sug.add_argument("routes", nargs="*", help="route ids, e.g. dwarf orc")
    sug.set_defaults(func=cmd_suggest_zones)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
