// Race themes: an accent colour and a deep shade for backgrounds; the banner shows the race crest from the game.
// Decorative only (backgrounds, borders); text keeps the contrast-checked tokens.

export interface RaceTheme {
  accent: string;
  deep: string;
}

export const RACE_THEMES: Record<string, RaceTheme> = {
  human: { accent: '#4f7fd6', deep: '#16264a' },
  dwarf: { accent: '#c47a3a', deep: '#3a2412' },
  gnome: { accent: '#3fb8b0', deep: '#0f3533' },
  'night-elf': { accent: '#9a7ae0', deep: '#24183f' },
  orc: { accent: '#c8473a', deep: '#3d110d' },
  troll: { accent: '#3aa88f', deep: '#0f3029' },
  undead: { accent: '#8fbf5a', deep: '#1c2a12' },
  tauren: { accent: '#c99a52', deep: '#3a2a14' },
  'skyborne-alliance': { accent: '#6cb8e6', deep: '#10293a' },
  'skyborne-horde': { accent: '#e0866e', deep: '#3b1a12' },
};

export const themeFor = (routeId: string): RaceTheme => RACE_THEMES[routeId] ?? RACE_THEMES.human;
