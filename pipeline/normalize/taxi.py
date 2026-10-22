"""Flight masters and their routes (TaxiNodes, TaxiPath) on the zone maps, plus each zone map's world bounds so
map coordinates convert to yards (pipeline.generate.flight)."""
from pipeline.config import DATA_BUILD

# TaxiNodes.Flags bits for the factions that can use a node; nodes with neither are boats and zeppelins.
FACTION_FLAGS = {"Alliance": 1, "Horde": 2}
_WORLD = 947


def map_bounds(assignments: list[dict], uimaps: dict[int, str]) -> dict[int, list[float]]:
    """UiMap -> [minX, minY, maxX, maxY, continent MapID] in world yards, from its whole-map UiMapAssignment
    (UiMin 0,0 to UiMax 1,1; the largest one when there are several)."""
    best: dict[int, list[float]] = {}
    for r in assignments:
        ui = int(r["UiMapID"])
        if ui not in uimaps or [float(r[f"Ui{k}_{i}"]) for k in ("Min", "Max") for i in (0, 1)] != [0, 0, 1, 1]:
            continue
        b = [float(r["Region_0"]), float(r["Region_1"]), float(r["Region_3"]), float(r["Region_4"]), int(r["MapID"])]
        area = (b[2] - b[0]) * (b[3] - b[1])
        if area > 0 and (ui not in best or area > (best[ui][2] - best[ui][0]) * (best[ui][3] - best[ui][1])):
            best[ui] = b
    return dict(sorted(best.items()))


def to_map(x_world: float, y_world: float, b: list[float]) -> tuple[float, float]:
    """World (X, Y) -> map (x, y) percent; map x runs along -Y, map y along -X."""
    return (b[3] - y_world) / (b[3] - b[1]) * 100, (b[2] - x_world) / (b[2] - b[0]) * 100


def to_world(x: float, y: float, b: list[float]) -> tuple[float, float]:
    """Map (x, y) percent -> world (X, Y), the inverse of to_map."""
    return b[2] - y / 100 * (b[2] - b[0]), b[3] - x / 100 * (b[3] - b[1])


def _zone_for(name: str, x_world: float, y_world: float, continent: int, bounds: dict[int, list[float]],
              uimaps: dict[int, str], parents: dict[int, int]) -> int | None:
    """The zone map (not a continent or the world) of this continent that contains the point. Map bounds are
    rectangles that overlap their neighbours, so the node's name decides: "Orgrimmar, Durotar" is on the Orgrimmar
    map, "Crossroads, The Barrens" on The Barrens; else the smallest map containing the point."""
    inside = [ui for ui, b in bounds.items()
              if b[4] == continent and parents.get(ui) not in (None, 0, _WORLD)
              and b[0] <= x_world <= b[2] and b[1] <= y_world <= b[3]]
    parts = [part.strip().lower() for part in name.split(",")]
    for part in parts:
        named = [ui for ui in inside if uimaps[ui].lower().startswith(part)]
        if named:
            return named[0]
    return min(inside, key=lambda ui: (bounds[ui][2] - bounds[ui][0]) * (bounds[ui][3] - bounds[ui][1]),
               default=None)


def build_taxi(nodes: list[dict], paths: list[dict], assignments: list[dict], uimaps: dict[int, str],
               parents: dict[int, int]) -> dict:
    """Flight masters a faction can use, on the zone map they stand in, the direct flights between them, and the
    zone maps' world bounds."""
    bounds = map_bounds(assignments, uimaps)
    out_nodes: dict[str, dict] = {}
    for r in nodes:
        flags = int(r["Flags"])
        factions = [f for f, bit in FACTION_FLAGS.items() if flags & bit]
        if not factions or r["Name_lang"].startswith("zzOLD"):  # zzOLD: retired nodes
            continue
        xw, yw, continent = float(r["Pos_0"]), float(r["Pos_1"]), int(r["ContinentID"])
        ui = _zone_for(r["Name_lang"], xw, yw, continent, bounds, uimaps, parents)
        if ui is None:
            continue
        x, y = to_map(xw, yw, bounds[ui])
        out_nodes[r["ID"]] = {"name": r["Name_lang"], "factions": factions, "uiMapId": ui,
                              "x": round(x, 1), "y": round(y, 1), "continent": continent,
                              "world": [round(xw, 1), round(yw, 1)]}
    out_paths = sorted({(int(r["FromTaxiNode"]), int(r["ToTaxiNode"])) for r in paths
                        if r["FromTaxiNode"] in out_nodes and r["ToTaxiNode"] in out_nodes
                        and set(out_nodes[r["FromTaxiNode"]]["factions"]) & set(out_nodes[r["ToTaxiNode"]]["factions"])})
    return {
        "build": DATA_BUILD,
        "nodes": dict(sorted(out_nodes.items(), key=lambda kv: int(kv[0]))),
        "paths": [list(p) for p in out_paths],
        "bounds": {str(ui): b for ui, b in bounds.items()},
    }
