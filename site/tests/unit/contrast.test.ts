import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

// WCAG 2.2 contrast for the tokens in src/styles/tokens.css (docs/plan.md §3.1).
const css = readFileSync(new URL('../../src/styles/tokens.css', import.meta.url), 'utf8');

function tokens(block: string): Record<string, string> {
  return Object.fromEntries([...block.matchAll(/--([a-z-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));
}

const base = tokens(css.slice(css.indexOf(':root {'), css.indexOf('}', css.indexOf(':root {'))));
const highStart = css.indexOf(':root[data-contrast="high"]');
const high = { ...base, ...tokens(css.slice(highStart, css.indexOf('}', highStart))) };

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TEXT = ['text', 'muted', 'gold', 'quest', 'npc', 'alliance', 'horde', 'success', 'warn'];
const BACKGROUNDS = ['bg', 'surface', 'raised'];

for (const [name, t] of [['default', base], ['high contrast', high]] as const) {
  test(`${name}: every text token is at least 4.5:1 on every background`, () => {
    for (const fg of TEXT) {
      for (const bg of BACKGROUNDS) {
        const r = ratio(t[fg], t[bg]);
        assert.ok(r >= 4.5, `${fg} on ${bg}: ${r.toFixed(2)}:1`);
      }
    }
  });

  test(`${name}: borders reach 3:1 and text on gold reaches 4.5:1`, () => {
    for (const bg of BACKGROUNDS) assert.ok(ratio(t.border, t[bg]) >= 3, `border on ${bg}`);
    assert.ok(ratio(t['on-gold'], t.gold) >= 4.5);
  });
}
