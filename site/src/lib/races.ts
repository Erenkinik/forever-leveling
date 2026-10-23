// Race themes: an accent colour, a deep shade for backgrounds and the starting zone whose map art is the backdrop;
// the banner shows the race crest from the game.
// Decorative only (backgrounds, borders); text keeps the contrast-checked tokens.

export interface RaceTheme {
  accent: string;
  deep: string;
  /** UiMap id of the race's starting zone: its map art, blurred and dark, is the page backdrop */
  home: number;
}

export const RACE_THEMES: Record<string, RaceTheme> = {
  human: { accent: '#4f7fd6', deep: '#16264a', home: 1429 },
  dwarf: { accent: '#c47a3a', deep: '#3a2412', home: 1426 },
  gnome: { accent: '#3fb8b0', deep: '#0f3533', home: 1426 },
  'night-elf': { accent: '#9a7ae0', deep: '#24183f', home: 1438 },
  orc: { accent: '#c8473a', deep: '#3d110d', home: 1411 },
  troll: { accent: '#3aa88f', deep: '#0f3029', home: 1411 },
  undead: { accent: '#8fbf5a', deep: '#1c2a12', home: 1420 },
  tauren: { accent: '#c99a52', deep: '#3a2a14', home: 1412 },
  'skyborne-alliance': { accent: '#6cb8e6', deep: '#10293a', home: 2521 },
  'skyborne-horde': { accent: '#e0866e', deep: '#3b1a12', home: 2521 },
};

export const themeFor = (routeId: string): RaceTheme => RACE_THEMES[routeId] ?? RACE_THEMES.human;
