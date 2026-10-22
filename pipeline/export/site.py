"""Site JSON export: the route with human-readable names added next to the ids."""
import copy


def to_site_json(route: dict, quests: dict[int, dict], spawns: dict, uimaps: dict[int, str]) -> dict:
    """Return a copy of route whose steps also carry questName, npcName and zoneName (None when unknown)."""
    out = copy.deepcopy(route)
    units = spawns.get("units", {})
    for step in out.get("steps", []):
        quest_id, npc_id, map_id = step.get("questId"), step.get("npcId"), step.get("mapId")
        step["questName"] = quests.get(quest_id, {}).get("name") if quest_id is not None else None
        step["npcName"] = units.get(str(npc_id), {}).get("name") if npc_id is not None else None
        step["zoneName"] = uimaps.get(map_id) if map_id is not None else None
    return out
