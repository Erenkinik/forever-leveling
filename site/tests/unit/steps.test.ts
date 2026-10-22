import assert from 'node:assert/strict';
import { test } from 'node:test';

import { describeStep, groupByZone, loadDone, saveDone, storageKey, type Step } from '../../src/lib/steps.ts';

const base = { mapId: 1429, x: 48.2, y: 41.7, confidence: 'unverified', zoneName: 'Elwynn Forest' };

test('accept and turnin name the quest and the npc', () => {
  const accept: Step = { ...base, id: 'accept-783', type: 'accept', questId: 783, questName: 'A Threat Within',
    npcId: 823, npcName: 'Deputy Willem' };
  assert.deepEqual(describeStep(accept), [
    { text: 'Accept ' }, { text: 'A Threat Within', kind: 'quest' }, { text: ' from ' },
    { text: 'Deputy Willem', kind: 'npc' },
  ]);
  const turnin: Step = { ...accept, id: 'turnin-783', type: 'turnin' };
  assert.equal(describeStep(turnin).map((p) => p.text).join(''), 'Turn in A Threat Within to Deputy Willem');
});

test('unknown names fall back to ids', () => {
  const s: Step = { ...base, id: 'accept-9', type: 'accept', questId: 9, questName: null, npcId: 5, npcName: null };
  assert.equal(describeStep(s).map((p) => p.text).join(''), 'Accept quest #9 from NPC #5');
});

test('other step types', () => {
  const text = (s: Step) => describeStep(s).map((p) => p.text).join('');
  assert.equal(text({ ...base, id: 'c', type: 'complete', questId: 1, questName: 'Q' }), 'Complete the objectives of Q');
  assert.equal(text({ ...base, id: 'c', type: 'complete', questId: 1, questName: 'Q', objectives: [] }),
    'Complete the objectives of Q');
  assert.equal(text({ ...base, id: 't', type: 'travel', mode: 'walk' }), 'Travel to Elwynn Forest');
  assert.equal(text({ ...base, id: 't', type: 'travel', mode: 'boat' }), 'Take the boat to Elwynn Forest');
  assert.equal(text({ ...base, id: 't', type: 'travel', mode: 'zeppelin' }), 'Take the zeppelin to Elwynn Forest');
  assert.equal(text({ ...base, id: 't', type: 'travel', mode: 'flight' }), 'Fly to Elwynn Forest');
  assert.equal(text({ ...base, id: 't', type: 'travel', mode: 'hearth' }), 'Hearth to Elwynn Forest');
  assert.equal(text({ ...base, id: 'g', type: 'grind', untilLevel: 30 }), 'Grind until level 30');
  assert.equal(text({ ...base, id: 'x', type: 'gap', questId: 2, questName: 'Q2', reason: 'quest 2: prereq 1 not in route' }),
    'Skip for now: Q2. It needs an earlier quest that this route skips.');
});

test('groupByZone keeps runs of the same map together, in order', () => {
  const s = (id: string, mapId: number, zoneName: string): Step => ({ ...base, id, type: 'travel', mapId, zoneName });
  const groups = groupByZone([s('a', 1, 'A'), s('b', 1, 'A'), s('c', 2, 'B'), s('d', 1, 'A')]);
  assert.deepEqual(groups.map((g) => [g.zoneName, g.steps.map((x) => x.id)]),
    [['A', ['a', 'b']], ['B', ['c']], ['A', ['d']]]);
});

test('progress is stored per route and survives a broken store', () => {
  const mem = new Map<string, string>();
  const store = { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v) };
  assert.equal(storageKey('human'), 'fxp:v1:human');
  saveDone(store, 'human', new Set(['a', 'b']));
  assert.deepEqual([...loadDone(store, 'human')].sort(), ['a', 'b']);
  assert.equal(loadDone(store, 'orc').size, 0);
  mem.set('fxp:v1:human', '{not json');
  assert.equal(loadDone(store, 'human').size, 0);
  const throwing = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };
  assert.equal(loadDone(throwing, 'human').size, 0);
  assert.doesNotThrow(() => saveDone(throwing, 'human', new Set(['a'])));
});

test('clusterPins merges pins closer than the threshold, in step order', async () => {
  const { clusterPins } = await import('../../src/lib/steps.ts');
  const s = (id: string, x: number, y: number): Step => ({ ...base, id, type: 'travel', x, y });
  const clusters = clusterPins([s('a', 10, 10), s('b', 12, 11), s('c', 50, 50), s('d', 10.5, 9)], 5);
  assert.deepEqual(clusters.map((c) => c.map((x) => x.id)), [['a', 'b', 'd'], ['c']]);
  assert.deepEqual(clusterPins([s('a', 10, 10), s('b', 12, 11)], 1).map((c) => c.length), [1, 1]);
  // On a map 2/3 as tall as wide, a y step counts 2/3 of an x step.
  assert.deepEqual(clusterPins([s('a', 10, 10), s('b', 10, 16)], 4.5, 2 / 3).map((c) => c.length), [2]);
  assert.deepEqual(clusterPins([s('a', 10, 10), s('b', 10, 16)], 4.5).map((c) => c.length), [1, 1]);
});

test('safeStorage falls back to memory when the browser blocks storage', async () => {
  const { safeStorage } = await import('../../src/lib/steps.ts');
  const store = safeStorage(() => { throw new Error('SecurityError'); });
  store.setItem('k', 'v');
  assert.equal(store.getItem('k'), 'v');
  const real = { getItem: () => 'x', setItem: () => {} };
  assert.equal(safeStorage(() => real), real);
});

test('loadDone keeps only ids of the current route', () => {
  const mem = new Map<string, string>([['fxp:v1:human', JSON.stringify(['a', 'old', 'b'])]]);
  const store = { getItem: (k: string) => mem.get(k) ?? null, setItem: () => {} };
  assert.deepEqual([...loadDone(store, 'human', new Set(['a', 'b', 'c']))].sort(), ['a', 'b']);
});

test('settings round-trip with defaults for missing or broken values', async () => {
  const { loadSettings, saveSettings, SETTINGS_KEY } = await import('../../src/lib/steps.ts');
  const mem = new Map<string, string>();
  const store = { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v) };
  assert.deepEqual(loadSettings(store), { shortcuts: true, highContrast: false, playerClass: '' });
  saveSettings(store, { shortcuts: false, highContrast: true, playerClass: 'Warlock' });
  assert.equal(SETTINGS_KEY, 'fxp:v1:settings');
  assert.deepEqual(loadSettings(store), { shortcuts: false, highContrast: true, playerClass: 'Warlock' });
  mem.set(SETTINGS_KEY, '[1]');
  assert.deepEqual(loadSettings(store), { shortcuts: true, highContrast: false, playerClass: '' });
});

test('reportUrl opens a prefilled GitHub issue for the step', async () => {
  const { reportUrl } = await import('../../src/lib/steps.ts');
  const step: Step = { ...base, id: 'accept-783', type: 'accept', questId: 783, questName: 'A Threat Within',
    npcId: 823, npcName: 'Deputy Willem' };
  const url = new URL(reportUrl({ id: 'human', dataBuild: '1.60.1.70532' }, step, 14));
  assert.equal(url.origin + url.pathname, 'https://github.com/Erenkinik/forever-leveling/issues/new');
  assert.equal(url.searchParams.get('title'), '[human] Step 14: Accept A Threat Within from Deputy Willem');
  const body = url.searchParams.get('body')!;
  for (const part of ['Route: human', 'Step 14 (accept-783)', 'Quest: 783', 'NPC: 823', 'Map 1429 at 48.2, 41.7',
                      'Data build: 1.60.1.70532', 'What is wrong?']) {
    assert.ok(body.includes(part), part);
  }
});

test('complete steps spell out their objectives', () => {
  const step: Step = { ...base, id: 'complete-5', type: 'complete', questId: 5, questName: 'Wolves', objectives: [
    { kind: 'kill', id: 10, name: 'Kobold Vermin' },
    { kind: 'collect', id: 750, name: 'Tough Wolf Meat', sources: ['Timber Wolf', 'Young Wolf'] },
    { kind: 'collect', id: 999, name: null, sources: [] },
    { kind: 'use', id: 31, name: 'Old Lion Statue' },
  ] };
  const parts = describeStep(step);
  assert.equal(parts.map((p) => p.text).join(''),
    'Wolves: kill Kobold Vermin; collect Tough Wolf Meat from Timber Wolf, Young Wolf; collect item #999; use Old Lion Statue');
  assert.deepEqual(parts.filter((p) => p.kind).map((p) => [p.kind, p.text]), [
    ['quest', 'Wolves'], ['npc', 'Kobold Vermin'], ['item', 'Tough Wolf Meat'], ['npc', 'Timber Wolf'],
    ['npc', 'Young Wolf'], ['item', 'item #999'], ['item', 'Old Lion Statue'],
  ]);
});

test('gap reasons are told in player language', async () => {
  const { gapReason } = await import('../../src/lib/steps.ts');
  const cases: [string, string][] = [
    ['quest 1: prereq 2 not in route', 'It needs an earlier quest that this route skips.'],
    ['quest 1: prereq 2 is a gap', 'It needs an earlier quest that is not routed yet.'],
    ['quest 1: objective item 2894 location unknown', 'Where to do its objective is not known yet.'],
    ['quest 1: objective unit 7 location unknown', 'Where to do its objective is not known yet.'],
    ['quest 1: objective located only off-route', 'Its objective is outside this route.'],
    ['quest 1: end location unknown', 'Where to turn it in is not known yet.'],
    ['quest 1: start location unknown', 'Where it starts is not known yet.'],
    ['quest 1: start type is item, not an NPC', 'It starts from an item or object, which is not routed yet.'],
    ['quest 1: end type is object, not an NPC', 'It ends at an item or object, which is not routed yet.'],
    ['quest 1: start type is unknown, not an NPC', 'Where it starts is not known yet.'],
    ['quest 1: end type is unknown, not an NPC', 'Where to turn it in is not known yet.'],
    ['quest 1: something new', 'Not routed yet.'],
  ];
  for (const [raw, friendly] of cases) assert.equal(gapReason(raw), friendly, raw);
});

test('levelRange of a zone group uses the estimated step levels', async () => {
  const { levelRange } = await import('../../src/lib/steps.ts');
  const s = (id: string, level?: number): Step => ({ ...base, id, type: 'travel', level });
  assert.deepEqual(levelRange([s('a', 3), s('b', 6), s('c', 4)]), [3, 6]);
  assert.equal(levelRange([s('a'), s('b')]), null);
});

test('searchSteps finds quests and NPCs from the current step on, then wraps', async () => {
  const { searchSteps } = await import('../../src/lib/steps.ts');
  const steps: Step[] = [
    { ...base, id: 'a', type: 'accept', questId: 1, questName: 'Wolf Pelts', npcName: 'Eagan' },
    { ...base, id: 'b', type: 'turnin', questId: 2, questName: 'Kobold Camp', npcName: 'Marshal McBride' },
    { ...base, id: 'c', type: 'accept', questId: 3, questName: 'The Wolf Hunt', npcName: 'Marshal McBride' },
  ];
  assert.deepEqual(searchSteps(steps, 'wolf', 1).map((s) => s.id), ['c', 'a']);
  assert.deepEqual(searchSteps(steps, 'MCBRIDE', 0).map((s) => s.id), ['b', 'c']);
  assert.deepEqual(searchSteps(steps, '  ', 0), []);
  assert.deepEqual(searchSteps(steps, 'wolf', 0, 1).map((s) => s.id), ['a']);
  assert.equal(searchSteps(steps, 'mcbride', 0, 2).length, 2);
  assert.equal(searchSteps(steps, 'mcbride', 0, 3).length, 2);
});

test('pinLabel names who or what is at the pin', async () => {
  const { pinLabel } = await import('../../src/lib/steps.ts');
  const accept: Step = { ...base, id: 'a', type: 'accept', questId: 1, questName: 'Q', npcName: 'Deputy Willem' };
  assert.equal(pinLabel(accept), 'Deputy Willem');
  assert.equal(pinLabel({ ...accept, npcName: null }), 'Q');
  const complete: Step = { ...base, id: 'c', type: 'complete', questId: 1, questName: 'Q',
    objectives: [{ kind: 'collect', id: 5, name: 'Tough Wolf Meat', sources: ['Young Wolf'] }] };
  assert.equal(pinLabel(complete), 'Young Wolf');
  assert.equal(pinLabel({ ...complete, objectives: [{ kind: 'kill', id: 9, name: 'Kobold Vermin' }] }), 'Kobold Vermin');
  assert.equal(pinLabel({ ...complete, objectives: [] }), 'Q');
  assert.equal(pinLabel({ ...base, id: 't', type: 'travel', mode: 'walk' }), 'Elwynn Forest');
  assert.equal(pinLabel({ ...base, id: 'g', type: 'grind', untilLevel: 8 }), 'Grind to 8');
});

test('questBrief lists the current quest as numbered things to do, marking done and current ones', async () => {
  const { questBrief } = await import('../../src/lib/steps.ts');
  const q = { questId: 5, questName: 'Wolves Across the Border' };
  const steps: Step[] = [
    { ...base, id: 'accept-5', type: 'accept', ...q, npcName: 'Eagan Peltskinner', x: 48.9, y: 40.2 },
    { ...base, id: 'accept-6', type: 'accept', questId: 6, questName: 'Other', npcName: 'X' },
    { ...base, id: 'complete-5', type: 'complete', ...q, x: 47.0, y: 36.5, objectives: [
      { kind: 'collect', id: 750, name: 'Tough Wolf Meat', sources: ['Young Wolf', 'Timber Wolf'] },
      { kind: 'kill', id: 10, name: 'Kobold Vermin' },
    ] },
    { ...base, id: 'turnin-5', type: 'turnin', ...q, npcName: 'Eagan Peltskinner', x: 48.9, y: 40.2 },
  ];
  const brief = questBrief(steps, steps[2], new Set(['accept-5']));
  assert.equal(brief.title, 'Wolves Across the Border');
  const text = (parts: { text: string }[]) => parts.map((p) => p.text).join('');
  assert.deepEqual(brief.items.map((i) => [text(i.parts), i.state]), [
    ['Talk to Eagan Peltskinner at 48.9, 40.2 and accept the quest.', 'done'],
    ['Collect Tough Wolf Meat from Young Wolf, Timber Wolf around 47.0, 36.5.', 'current'],
    ['Kill Kobold Vermin around 47.0, 36.5.', 'current'],
    ['Return to Eagan Peltskinner at 48.9, 40.2 and turn the quest in.', 'todo'],
  ]);
  assert.equal(brief.zone, 'Elwynn Forest');
});

test('questBrief for a step without a quest describes the stop', async () => {
  const { questBrief } = await import('../../src/lib/steps.ts');
  const travel: Step = { ...base, id: 't', type: 'travel', mode: 'boat', zoneName: 'Darkshore' };
  const brief = questBrief([travel], travel, new Set());
  assert.equal(brief.title, 'Darkshore');
  assert.deepEqual(brief.items.map((i) => i.parts.map((p) => p.text).join('')), ['Take the boat to Darkshore.']);
  const grind: Step = { ...base, id: 'g', type: 'grind', untilLevel: 12 };
  assert.deepEqual(questBrief([grind], grind, new Set()).items.map((i) => i.parts.map((p) => p.text).join('')),
    ['Kill monsters around 48.2, 41.7 until you reach level 12.']);
});

test('stepIcon picks the game icon for the step', async () => {
  const { stepIcon } = await import('../../src/lib/steps.ts');
  const s = (type: Step['type'], extra: Partial<Step> = {}): Step => ({ ...base, id: type, type, ...extra });
  assert.equal(stepIcon(s('accept')), 'accept');
  assert.equal(stepIcon(s('turnin')), 'turnin');
  assert.equal(stepIcon(s('complete', { objectives: [{ kind: 'kill', id: 1, name: 'A' }] })), 'kill');
  assert.equal(stepIcon(s('complete', { objectives: [{ kind: 'collect', id: 1, name: 'A', sources: [] }] })), 'collect');
  assert.equal(stepIcon(s('complete', { objectives: [{ kind: 'use', id: 1, name: 'A' }] })), 'use');
  assert.equal(stepIcon(s('complete')), 'kill');
  assert.equal(stepIcon(s('grind', { untilLevel: 5 })), 'grind');
  assert.equal(stepIcon(s('travel', { mode: 'walk' })), null);
  assert.equal(stepIcon(s('gap')), null);
});

test('pinIcon greys the turn-in "?" while the quest has unfinished steps', async () => {
  const { pinIcon } = await import('../../src/lib/steps.ts');
  const q = (id: string, type: Step['type'], questId = 7): Step => ({ ...base, id, type, questId });
  const route = [q('a', 'accept'), q('c', 'complete'), q('other', 'complete', 8), q('t', 'turnin')];
  const turnin = route[3];
  assert.equal(pinIcon(turnin, route, new Set()), 'progress');
  assert.equal(pinIcon(turnin, route, new Set(['a'])), 'progress');
  assert.equal(pinIcon(turnin, route, new Set(['a', 'c'])), 'turnin'); // another quest's step does not matter
  assert.equal(pinIcon(route[0], route, new Set()), 'accept');
});

test('collect objectives carry the item icon into the text parts', async () => {
  const { questBrief } = await import('../../src/lib/steps.ts');
  const step: Step = { ...base, id: 'complete-5', type: 'complete', questId: 5, questName: 'Q', objectives: [
    { kind: 'collect', id: 750, name: 'Tough Wolf Meat', sources: ['Young Wolf'], icon: 133972 },
    { kind: 'collect', id: 751, name: 'No Icon', sources: [], icon: null },
  ] };
  const items = questBrief([step], step, new Set()).items;
  assert.equal(items[0].parts.find((p) => p.kind === 'item')?.icon, '/art/items/133972.webp');
  assert.equal(items[1].parts.find((p) => p.kind === 'item')?.icon, undefined);
  assert.equal(describeStep(step).find((p) => p.kind === 'item')?.icon, '/art/items/133972.webp');
});

test('flight steps: finding a flight master and flying between two', async () => {
  const { describeStep, stepIcon, pinLabel } = await import('../../src/lib/steps.ts');
  const found: Step = { ...base, id: 'flightpath-25', type: 'flightpath', node: 'Crossroads, The Barrens' };
  const fly: Step = { ...base, id: 'travel-fly-23-25', type: 'travel', mode: 'flight',
    fromNode: 'Orgrimmar, Durotar', node: 'Crossroads, The Barrens' };
  assert.equal(describeStep(found).map((p) => p.text).join(''), 'Get the flight path at Crossroads, The Barrens');
  assert.equal(describeStep(fly).map((p) => p.text).join(''),
    'Fly from Orgrimmar, Durotar to Crossroads, The Barrens');
  assert.equal(stepIcon(found), 'flight');
  assert.equal(stepIcon(fly), 'flight');
  assert.equal(stepIcon({ ...fly, mode: 'walk' }), null);
  assert.equal(pinLabel(fly), 'Fly to Crossroads');
});

test('a class sees the steps for everyone and its own class quests', async () => {
  const { routeClasses, stepsForClass } = await import('../../src/lib/steps.ts');
  const all: Step = { ...base, id: 'a', type: 'accept' };
  const lock: Step = { ...base, id: 'w', type: 'accept', classOnly: ['Warlock'] };
  const war: Step = { ...base, id: 'r', type: 'accept', classOnly: ['Warrior', 'Rogue'] };
  const steps = [all, lock, war];
  assert.deepEqual(routeClasses(steps), ['Rogue', 'Warlock', 'Warrior']);
  assert.deepEqual(stepsForClass(steps, 'Warlock'), [all, lock]);
  assert.deepEqual(stepsForClass(steps, 'Rogue'), [all, war]);
  assert.deepEqual(stepsForClass(steps, ''), steps);
});

test('the map shows what is left of every quest in the log, wherever it is in the route', async () => {
  const { mapStepsFor, openQuests, pinIcon } = await import('../../src/lib/steps.ts');
  const q = (id: string, type: Step['type'], questId: number, mapId = 1): Step => ({ ...base, id, type, questId, mapId });
  const route = [
    q('a1', 'accept', 1), q('a2', 'accept', 2), q('c1', 'complete', 1),
    ...Array.from({ length: 12 }, (_, i) => q(`x${i}`, 'accept', 10 + i)),  // far ahead
    q('c2', 'complete', 2), q('t2', 'turnin', 2), q('t1', 'turnin', 1), q('t9', 'turnin', 9, 2),
  ];
  const done = new Set(['a1', 'a2']);
  assert.deepEqual([...openQuests(route, done)].sort(), [1, 2]);
  const ids = mapStepsFor(route, 2, done, 2, 3).map((s) => s.id);
  // Done steps leave the map; t9 is on another map.
  assert.deepEqual(ids, ['c1', 'x0', 'x1', 'x2', 'c2', 't2', 't1']);
  const t1 = route.find((s) => s.id === 't1')!;
  assert.equal(pinIcon(t1, route, done), 'progress');  // objectives left: the grey "?"
  assert.equal(pinIcon(t1, route, new Set([...done, 'c1', ...route.slice(3, 15).map((s) => s.id)])), 'turnin');
  assert.deepEqual([...openQuests(route, new Set([...done, 't2']))], [1]);
  // Not accepted yet: only its "!" is on the map, not its turn-in.
  const fresh = [q('b1', 'accept', 5), q('b2', 'turnin', 5)];
  assert.deepEqual(mapStepsFor(fresh, 0, new Set(), 2, 3).map((s) => s.id), ['b1']);
  // Accepted: the "!" goes, the turn-in "?" comes.
  assert.deepEqual(mapStepsFor(fresh, 1, new Set(['b1']), 2, 3).map((s) => s.id), ['b2']);
});
