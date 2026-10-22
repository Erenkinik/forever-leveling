// Route step model and pure helpers shared by the pages and the RouteView island.

export type StepType = 'accept' | 'turnin' | 'complete' | 'travel' | 'sethearth' | 'train' | 'grind' | 'gap';

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
}

export interface Part {
  text: string;
  kind?: 'quest' | 'npc';
}

const quest = (s: Step): Part => ({ text: s.questName ?? `quest #${s.questId}`, kind: 'quest' });
const npc = (s: Step): Part => ({ text: s.npcName ?? `NPC #${s.npcId}`, kind: 'npc' });
const zone = (s: Step): string => s.zoneName ?? `map #${s.mapId}`;

/** The step as text segments; quest and NPC names are tagged for styling. */
export function describeStep(s: Step): Part[] {
  switch (s.type) {
    case 'accept':
      return [{ text: 'Accept ' }, quest(s), { text: ' from ' }, npc(s)];
    case 'turnin':
      return [{ text: 'Turn in ' }, quest(s), { text: ' to ' }, npc(s)];
    case 'complete':
      return [{ text: 'Complete the objectives of ' }, quest(s)];
    case 'travel':
      return [{ text: `Travel to ${zone(s)}` }];
    case 'grind':
      return [{ text: `Grind until level ${s.untilLevel}` }];
    case 'gap':
      return [{ text: 'Not routed yet: ' }, quest(s), { text: ` (${s.reason})` }];
    case 'sethearth':
      return [{ text: `Set your hearthstone in ${zone(s)}` }];
    case 'train':
      return [{ text: 'Visit your class trainer' }];
  }
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

/** Groups map pins whose centres are closer than `threshold` (map units) to the group's first pin. */
export function clusterPins(steps: Step[], threshold: number): Step[][] {
  const clusters: Step[][] = [];
  for (const s of steps) {
    const near = clusters.find((c) => Math.hypot(c[0].x - s.x, c[0].y - s.y) < threshold);
    if (near) near.push(s);
    else clusters.push([s]);
  }
  return clusters;
}

export interface Settings {
  shortcuts: boolean;
  highContrast: boolean;
}

// Also read by the inline script in src/layouts/Base.astro, which applies high contrast before first paint.
export const SETTINGS_KEY = 'fxp:v1:settings';
const DEFAULT_SETTINGS: Settings = { shortcuts: true, highContrast: false };

export function loadSettings(store: KeyValueStore): Settings {
  try {
    const raw: unknown = JSON.parse(store.getItem(SETTINGS_KEY) ?? '{}');
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return { ...DEFAULT_SETTINGS };
    const r = raw as Partial<Record<keyof Settings, unknown>>;
    return {
      shortcuts: typeof r.shortcuts === 'boolean' ? r.shortcuts : DEFAULT_SETTINGS.shortcuts,
      highContrast: typeof r.highContrast === 'boolean' ? r.highContrast : DEFAULT_SETTINGS.highContrast,
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
