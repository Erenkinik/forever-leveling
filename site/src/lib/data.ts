// Route files exported by the pipeline (python -m pipeline export). Never edit src/data/*.json by hand.
import type { Route } from './steps.ts';

// maps.json and item-icons.json (python -m pipeline maps) live next to the routes but are not routes.
const files = import.meta.glob<Route>(['../data/*.json', '!../data/maps.json', '!../data/item-icons.json'],
  { eager: true, import: 'default' });

// The game's character creation screen order: each Alliance race faces its Horde counterpart (Human and Orc, Dwarf
// and Undead, Night Elf and Tauren, Gnome and Troll, Skyborne and Skyborne).
const CREATE_ORDER = [['Human', 'Orc'], ['Dwarf', 'Undead'], ['Night Elf', 'Tauren'], ['Gnome', 'Troll'], ['Skyborne']];
const rank = (race: string) => {
  const i = CREATE_ORDER.findIndex((pair) => pair.includes(race));
  return i < 0 ? CREATE_ORDER.length : i;
};

export const routes: Route[] = Object.values(files)
  .sort((a, b) => rank(a.race) - rank(b.race) || a.faction.localeCompare(b.faction) || a.race.localeCompare(b.race));

export function routeById(id: string): Route | undefined {
  return routes.find((r) => r.id === id);
}
