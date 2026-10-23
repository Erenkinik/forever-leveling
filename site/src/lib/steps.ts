// Route step model and pure helpers shared by the pages and the RouteView island.

export type StepType =
  'accept' | 'turnin' | 'complete' | 'travel' | 'flightpath' | 'sethearth' | 'train' | 'grind' | 'gap';

export interface Objective {
  kind: 'kill' | 'collect' | 'use';
  id: number;
  name: string | null;
  /** collect only: nearest units/objects on the step's map that drop the item */
  sources?: string[];
  /** collect only: the item's icon FileDataID (site/public/art/items/<id>.webp), null when it has none */
  icon?: number | null;
}

export interface Step {
  id: string;
  type: StepType;
  mapId: number;
  x: number;
  y: number;
  confidence: string;
  questId?: number;
  npcId?: number;
  questName?: string | null;
  npcName?: string | null;
  zoneName?: string | null;
  untilLevel?: number;
  reason?: string;
  mode?: string;
  /** flightpath: the flight master found; travel by flight: the one flown to */
  node?: string;
  /** travel by flight: the flight master flown from */
  fromNode?: string;
  /** class quests: the classes (of this race) that do the step; absent for everyone */
  classOnly?: string[];
  objectives?: Objective[];
  /** estimated player level when the step starts (pipeline xpsim.estimate_levels) */
  level?: number;
  /** estimated seconds for the step, getting there included (pipeline export.timing) */
  seconds?: number;
  /** complete steps: spawn points (x, y on this map) where the objectives are done */
  area?: [number, number][];
  /** accept steps: a YouTube video of the quest, when one was found (pipeline videos) */
  video?: QuestVideo;
}

export interface QuestVideo {
  /** YouTube video id */
  id: string;
  title: string;
  channel: string | null;
}

export interface Route {
  id: string;
  race: string;
  faction: 'Alliance' | 'Horde';
  levelRange: [number, number];
  generatedAt: string;
  dataBuild: string;
  reviewed: boolean;
  releaseTier: 'beta' | 'full';
  steps: Step[];
  /** quests off the route that the race can do on its maps (exploration mode) */
  optional?: OptionalQuest[];
  /** dungeon entrances on the route's maps, with their quests for this race */
  dungeons?: Dungeon[];
}

export interface DungeonQuest extends Omit<OptionalQuest, 'level'> {
  /** null for the quests of Forever's new dungeons, whose level is not known */
  level: number | null;
  /** the map the quest starts on */
  zoneName: string | null;
  /** the route's accept step for it, or null when the route does not take it */
  step: string | null;
}

export interface Dungeon {
  id: number;
  name: string;
  kind: 'dungeon' | 'raid';
  mapId: number;
  x: number;
  y: number;
  /** lowest and highest level of its quests, or null without quests */
  levels: [number, number] | null;
  quests: DungeonQuest[];
  /** the attunement's quests, in chain order (each opens the next) */
  attunement: DungeonQuest[];
}

export interface OptionalQuest {
  questId: number;
  name: string | null;
  mapId: number;
  x: number;
  y: number;
  level: number;
  minLevel: number | null;
  npcName: string | null;
  classOnly?: string[];
}

export interface Part {
  text: string;
  kind?: 'quest' | 'npc' | 'item';
  /** an image shown before the text (item icons) */
  icon?: string;
}

const TRAVEL_VERB: Record<string, string> = {
  walk: 'Travel to', boat: 'Take the boat to', zeppelin: 'Take the zeppelin to', flight: 'Fly to', hearth: 'Hearth to',
  portal: 'Take the portal to',
};

const quest = (s: Step): Part => ({ text: s.questName ?? `quest #${s.questId}`, kind: 'quest' });
const npc = (s: Step): Part => ({ text: s.npcName ?? `NPC #${s.npcId}`, kind: 'npc' });
const zone = (s: Step): string => s.zoneName ?? `map #${s.mapId}`;

function objectiveParts(o: Objective): Part[] {
  if (o.kind === 'kill') return [{ text: 'kill ' }, { text: o.name ?? `NPC #${o.id}`, kind: 'npc' }];
  const thing: Part = { text: o.name ?? (o.kind === 'use' ? `object #${o.id}` : `item #${o.id}`), kind: 'item' };
  if (o.icon) thing.icon = `/art/items/${o.icon}.webp`;
  if (o.kind === 'use') return [{ text: 'use ' }, thing];
  const from = (o.sources ?? []).flatMap((name, i): Part[] => [
    { text: i === 0 ? ' from ' : ', ' }, { text: name, kind: 'npc' }]);
  return [{ text: 'collect ' }, thing, ...from];
}

/** The step as text segments; quest and NPC names are tagged for styling. */
export function describeStep(s: Step): Part[] {
  switch (s.type) {
    case 'accept':
      return [{ text: 'Accept ' }, quest(s), { text: ' from ' }, npc(s)];
    case 'turnin':
      return [{ text: 'Turn in ' }, quest(s), { text: ' to ' }, npc(s)];
    case 'complete':
      return s.objectives?.length
        ? [quest(s), { text: ': ' }, ...s.objectives.flatMap((o, i) => [
          ...(i > 0 ? [{ text: '; ' }] : []), ...objectiveParts(o)])]
        : [{ text: 'Complete the objectives of ' }, quest(s)];
    case 'travel':
      if (s.mode === 'flight' && s.fromNode && s.node) return [{ text: `Fly from ${s.fromNode} to ${s.node}` }];
      return [{ text: `${TRAVEL_VERB[s.mode ?? 'walk'] ?? 'Travel to'} ${zone(s)}` }];
    case 'flightpath':
      return [{ text: `Get the flight path at ${s.node ?? zone(s)}` }];
    case 'grind':
      return [{ text: `Grind until level ${s.untilLevel}` }];
    case 'gap':
      return [{ text: 'Skip for now: ' }, quest(s), { text: `. ${gapReason(s.reason)}` }];
    case 'sethearth':
      return [{ text: `Set your hearthstone in ${zone(s)}` }];
    case 'train':
      return [{ text: 'Visit your class trainer' }];
  }
}

/** The classes that have quests on the route, alphabetically. */
export function routeClasses(steps: Step[]): string[] {
  return [...new Set(steps.flatMap((s) => s.classOnly ?? []))].sort();
}

/** Whether a player of this class takes the quest: a quest for every class, or one of the class's own ('' = no class
 *  chosen, so no class quests). */
const forClass = (classOnly: string[] | undefined, playerClass: string) =>
  !classOnly || classOnly.includes(playerClass);

/** The steps a player of this class does: everyone's steps and the class's own ('' = only everyone's). */
export function stepsForClass(steps: Step[], playerClass: string): Step[] {
  return steps.filter((s) => forClass(s.classOnly, playerClass));
}

/** Exploration mode: the quests off the route on this map that a player of this class can take. */
export function optionalOnMap(quests: OptionalQuest[], mapId: number, playerClass: string): OptionalQuest[] {
  return quests.filter((q) => q.mapId === mapId && forClass(q.classOnly, playerClass));
}

/** Where a player already at `level` starts: the first step (not a skipped one) estimated at that level or higher;
 *  -1 when the route never gets there. */
export function stepForLevel(steps: Step[], level: number): number {
  return steps.findIndex((s) => s.type !== 'gap' && (s.level ?? 0) >= level);
}

/** The dungeon entrances on this map, each with the quests a player of this class can take. */
export function dungeonsOnMap(dungeons: Dungeon[], mapId: number, playerClass: string): Dungeon[] {
  const takes = (q: DungeonQuest) => forClass(q.classOnly, playerClass);
  return dungeons.filter((d) => d.mapId === mapId).map((d) => ({
    ...d,
    quests: d.quests.filter(takes),
    attunement: (d.attunement ?? []).filter(takes),
  }));
}

export interface ZoneGroup {
  key: string;
  mapId: number;
  zoneName: string;
  steps: Step[];
}

/** Consecutive steps on the same map form one group; a map visited twice gives two groups. */
export function groupByZone(steps: Step[]): ZoneGroup[] {
  const groups: ZoneGroup[] = [];
  for (const s of steps) {
    const last = groups[groups.length - 1];
    if (last && last.mapId === s.mapId) last.steps.push(s);
    else groups.push({ key: `${s.mapId}-${groups.length}`, mapId: s.mapId, zoneName: zone(s), steps: [s] });
  }
  return groups;
}

export interface KeyValueStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export const storageKey = (routeId: string): string => `fxp:v1:${routeId}`;

/** The browser store, or an in-memory one when reading `window.localStorage` itself throws (blocked site data). */
export function safeStorage(get: () => KeyValueStore): KeyValueStore {
  try {
    return get();
  } catch {
    const mem = new Map<string, string>();
    return { getItem: (k) => mem.get(k) ?? null, setItem: (k, v) => void mem.set(k, v) };
  }
}

/** Done step ids for a route; an unreadable or blocked store gives an empty set. Ids not in `valid`
 *  (steps removed when the route was regenerated) are dropped. */
export function loadDone(store: KeyValueStore, routeId: string, valid?: Set<string>): Set<string> {
  try {
    const raw = store.getItem(storageKey(routeId));
    const ids: unknown = raw ? JSON.parse(raw) : [];
    const list = Array.isArray(ids) ? ids.filter((x): x is string => typeof x === 'string') : [];
    return new Set(valid ? list.filter((id) => valid.has(id)) : list);
  } catch {
    return new Set();
  }
}

/** Saves done step ids; a blocked store is ignored (progress then lives only in the page). */
export function saveDone(store: KeyValueStore, routeId: string, done: Set<string>): void {
  try {
    store.setItem(storageKey(routeId), JSON.stringify([...done]));
  } catch {
    // Private mode or blocked storage: nothing to do.
  }
}

/** Groups map pins whose centres are closer than `threshold` (x map units) to the group's first pin.
 *  `yScale` is the map's height / width, so y distances are measured in x units. */
export function clusterPins(steps: Step[], threshold: number, yScale = 1): Step[][] {
  const clusters: Step[][] = [];
  for (const s of steps) {
    const near = clusters.find((c) => Math.hypot(c[0].x - s.x, (c[0].y - s.y) * yScale) < threshold);
    if (near) near.push(s);
    else clusters.push([s]);
  }
  return clusters;
}

export interface Settings {
  shortcuts: boolean;
  highContrast: boolean;
  /** the player's class; '' shows every class's quests */
  playerClass: string;
  /** exploration mode: the map also shows the quests off the route */
  explore: boolean;
}

// Also read by the inline script in src/layouts/Base.astro, which applies high contrast before first paint.
export const SETTINGS_KEY = 'fxp:v1:settings';
const DEFAULT_SETTINGS: Settings = {
  shortcuts: true, highContrast: false, playerClass: '', explore: false,
};

export function loadSettings(store: KeyValueStore): Settings {
  try {
    const raw: unknown = JSON.parse(store.getItem(SETTINGS_KEY) ?? '{}');
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return { ...DEFAULT_SETTINGS };
    const r = raw as Partial<Record<keyof Settings, unknown>>;
    return {
      shortcuts: typeof r.shortcuts === 'boolean' ? r.shortcuts : DEFAULT_SETTINGS.shortcuts,
      highContrast: typeof r.highContrast === 'boolean' ? r.highContrast : DEFAULT_SETTINGS.highContrast,
      playerClass: typeof r.playerClass === 'string' ? r.playerClass : DEFAULT_SETTINGS.playerClass,
      explore: typeof r.explore === 'boolean' ? r.explore : DEFAULT_SETTINGS.explore,
    };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function saveSettings(store: KeyValueStore, settings: Settings): void {
  try {
    store.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Blocked storage: the setting lasts for this page only.
  }
}

export const REPO_URL = 'https://github.com/Erenkinik/forever-leveling';

/** A new-issue link prefilled with everything needed to find and fix the step. */
export function reportUrl(route: Pick<Route, 'id' | 'dataBuild'>, step: Step, n: number): string {
  const text = describeStep(step).map((p) => p.text).join('');
  const body = [
    `Route: ${route.id}`,
    `Step ${n} (${step.id}): ${text}`,
    step.questId !== undefined ? `Quest: ${step.questId}` : null,
    step.npcId !== undefined ? `NPC: ${step.npcId}` : null,
    `Map ${step.mapId} at ${step.x}, ${step.y}`,
    `Data build: ${route.dataBuild}`,
    '',
    'What is wrong? (wrong NPC, wrong place, quest not available, …)',
    '',
  ].filter((line) => line !== null).join('\n');
  const params = new URLSearchParams({ title: `[${route.id}] Step ${n}: ${text}`, body });
  return `${REPO_URL}/issues/new?${params}`;
}

const GAP_REASONS: [RegExp, string][] = [
  [/prereq \d+ not in route/, 'It needs an earlier quest that this route skips.'],
  [/prereq \d+ is a gap/, 'It needs an earlier quest that is not routed yet.'],
  [/objective (unit|item|object) \d+ location unknown/, 'Where to do its objective is not known yet.'],
  [/objective located only off-route/, 'Its objective is outside this route.'],
  [/end location unknown|end type is unknown/, 'Where to turn it in is not known yet.'],
  [/start location unknown|start type is unknown/, 'Where it starts is not known yet.'],
  [/start type is \w+, not an NPC/, 'It starts from an item or object, which is not routed yet.'],
  [/end type is \w+, not an NPC/, 'It ends at an item or object, which is not routed yet.'],
];

/** The generator's gap reason ("quest 1: prereq 2 not in route") in words a player understands. */
export function gapReason(raw: string | undefined): string {
  return GAP_REASONS.find(([re]) => re.test(raw ?? ''))?.[1] ?? 'Not routed yet.';
}

/** Lowest and highest estimated level of the steps, or null when the route has no levels. */
export function levelRange(steps: Step[]): [number, number] | null {
  const levels = steps.map((s) => s.level).filter((l): l is number => typeof l === 'number');
  return levels.length ? [Math.min(...levels), Math.max(...levels)] : null;
}

/** Steps whose quest or NPC name contains the query (any case), starting at index `from` and wrapping. */
export function searchSteps(steps: Step[], query: string, from: number, limit = 8): Step[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const ordered = [...steps.slice(from), ...steps.slice(0, from)];
  return ordered
    .filter((s) => [s.questName, s.npcName].some((name) => name?.toLowerCase().includes(q)))
    .slice(0, limit);
}

/** Short text for a map pin: the NPC to talk to, the mob or source of the objective, or the destination. */
export function pinLabel(s: Step): string {
  switch (s.type) {
    case 'accept':
    case 'turnin':
      return s.npcName ?? s.questName ?? `quest #${s.questId}`;
    case 'complete': {
      const o = s.objectives?.[0];
      return (o?.kind === 'collect' ? o.sources?.[0] : undefined) ?? o?.name ?? s.questName ?? `quest #${s.questId}`;
    }
    case 'grind':
      return `Grind to ${s.untilLevel}`;
    case 'flightpath':
      return 'Flight master';
    case 'travel':
      return s.mode === 'flight' && s.node ? `Fly to ${s.node.split(',')[0]}` : zone(s);
    default:
      return s.questName ?? zone(s);
  }
}

export interface BriefItem {
  stepId: string;
  parts: Part[];
  state: 'done' | 'current' | 'todo';
}

export interface QuestBrief {
  title: string;
  zone: string;
  items: BriefItem[];
}

const xy = (s: Step) => `${s.x.toFixed(1)}, ${s.y.toFixed(1)}`;

function briefParts(s: Step, here: Step): Part[][] {
  const where = s.zoneName && s.zoneName !== here.zoneName ? ` in ${s.zoneName}` : '';
  switch (s.type) {
    case 'accept':
      return [[{ text: 'Talk to ' }, npc(s), { text: ` at ${xy(s)}${where} and accept the quest.` }]];
    case 'turnin':
      return [[{ text: 'Return to ' }, npc(s), { text: ` at ${xy(s)}${where} and turn the quest in.` }]];
    case 'complete':
      if (!s.objectives?.length) return [[{ text: `Complete the objectives around ${xy(s)}${where}.` }]];
      return s.objectives.map((o) => {
        const parts = objectiveParts(o);
        const [verb, ...rest] = parts;
        const capital = { ...verb, text: verb.text.charAt(0).toUpperCase() + verb.text.slice(1) };
        const at = o.kind === 'use' ? ` at ${xy(s)}${where}.` : ` around ${xy(s)}${where}.`;
        return [capital, ...rest, { text: at }];
      });
    case 'travel':
      if (s.mode === 'flight' && s.fromNode && s.node) {
        return [[{ text: `Take the flight from ${s.fromNode} to ${s.node}.` }]];
      }
      return [[{ text: `${TRAVEL_VERB[s.mode ?? 'walk'] ?? 'Travel to'} ${zone(s)}.` }]];
    case 'flightpath':
      return [[{ text: `Talk to the flight master at ${xy(s)}${where} to learn the ${s.node ?? zone(s)} flight path.` }]];
    case 'grind':
      return [[{ text: `Kill monsters around ${xy(s)} until you reach level ${s.untilLevel}.` }]];
    default:
      return [[...describeStep(s), { text: '.' }]];
  }
}

/** What to do for the current step's quest, step by step in route order; a step without a quest describes itself. */
export function questBrief(steps: Step[], current: Step, done: Set<string>): QuestBrief {
  const own = current.questId === undefined
    ? [current]
    : steps.filter((s) => s.questId === current.questId && s.type !== 'gap');
  const items = own.flatMap((s) => {
    const state = done.has(s.id) ? 'done' : s === current ? 'current' : 'todo';
    return briefParts(s, current).map((parts) => ({ stepId: s.id, parts, state }) as BriefItem);
  });
  const title = current.questId === undefined ? zone(current) : current.questName ?? `quest #${current.questId}`;
  return { title, zone: zone(current), items };
}

export type IconName = 'accept' | 'turnin' | 'progress' | 'kill' | 'collect' | 'use' | 'grind' | 'flight';

/** The game icon for a step (site/public/art/icon-<name>.webp, from the minimap icon atlas), or null. */
export function stepIcon(s: Step): IconName | null {
  switch (s.type) {
    case 'accept':
    case 'turnin':
    case 'grind':
      return s.type;
    case 'complete':
      return s.objectives?.[0]?.kind ?? 'kill';
    case 'flightpath':
      return 'flight';
    case 'travel':
      return s.mode === 'flight' ? 'flight' : null;
    default:
      return null;
  }
}

/** Quests in the log: accepted (accept step done) and not turned in yet, as in the game's quest log. */
export function openQuests(steps: Step[], done: ReadonlySet<string>): Set<number> {
  const open = new Set<number>();
  for (const s of steps) {
    if (s.questId === undefined) continue;
    if (s.type === 'accept' && done.has(s.id)) open.add(s.questId);
    if (s.type === 'turnin' && done.has(s.id)) open.delete(s.questId);
  }
  return open;
}

/** The steps a map shows: the window around the current step, plus what is left of every quest in the log on
 *  this map (its objectives and its turn-in, where the game puts the grey "?"), in route order. As in the game,
 *  a quest not accepted yet shows only its "!" (its turn-in is not on the map), and what is done leaves the map:
 *  accepting a quest takes its "!" away and puts the grey "?" over the NPC to turn it in to. */
export function mapStepsFor(steps: Step[], currentIndex: number, done: ReadonlySet<string>, behind: number,
                            ahead: number): Step[] {
  const current = steps[currentIndex];
  if (!current) return [];
  const open = openQuests(steps, done);
  const inLog = (s: Step) => s.questId !== undefined && open.has(s.questId);
  const near = new Set(steps.slice(Math.max(0, currentIndex - behind), currentIndex + ahead + 1));
  return steps.filter((s) => {
    if (s.mapId !== current.mapId || done.has(s.id)) return false;
    if (s.type === 'turnin' && s !== current && !inLog(s)) return false;
    return near.has(s) || (inLog(s) && !done.has(s.id) && (s.type === 'complete' || s.type === 'turnin'));
  });
}

/** The map icon: like stepIcon, but a turn-in whose quest still has earlier unfinished steps shows the grey,
 *  hollow "?" the game puts over a quest that is not done yet. */
export function pinIcon(s: Step, steps: Step[], done: ReadonlySet<string>): IconName | null {
  const icon = stepIcon(s);
  if (icon !== 'turnin' || s.questId === undefined) return icon;
  const at = steps.indexOf(s);
  const open = steps.some((o, i) => i < at && o.questId === s.questId && !done.has(o.id));
  return open ? 'progress' : 'turnin';
}
