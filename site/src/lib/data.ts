// Route files exported by the pipeline (python -m pipeline export). Never edit src/data/*.json by hand.
import type { Route } from './steps.ts';

const files = import.meta.glob<Route>('../data/*.json', { eager: true, import: 'default' });

export const routes: Route[] = Object.values(files).sort((a, b) => a.race.localeCompare(b.race));

export function routeById(id: string): Route | undefined {
  return routes.find((r) => r.id === id);
}
