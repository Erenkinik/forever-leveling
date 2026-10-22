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
  assert.equal(text({ ...base, id: 't', type: 'travel', mode: 'walk' }), 'Travel to Elwynn Forest');
  assert.equal(text({ ...base, id: 'g', type: 'grind', untilLevel: 30 }), 'Grind until level 30');
  assert.equal(text({ ...base, id: 'x', type: 'gap', questId: 2, questName: 'Q2', reason: 'prereq 1 not in route' }),
    'Not routed yet: Q2 (prereq 1 not in route)');
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
  assert.deepEqual(loadSettings(store), { shortcuts: true, highContrast: false });
  saveSettings(store, { shortcuts: false, highContrast: true });
  assert.equal(SETTINGS_KEY, 'fxp:v1:settings');
  assert.deepEqual(loadSettings(store), { shortcuts: false, highContrast: true });
  mem.set(SETTINGS_KEY, '[1]');
  assert.deepEqual(loadSettings(store), { shortcuts: true, highContrast: false });
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
