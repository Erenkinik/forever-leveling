import { useId } from 'react';

import { useDisclosure } from './useDisclosure.ts';

export interface RouteMeta {
  id: string;
  race: string;
  faction: 'Alliance' | 'Horde';
}

const FACTIONS = ['Alliance', 'Horde'] as const;
const CREST = { Alliance: '◆', Horde: '▲' } as const;

/** The selected race as a button; it opens the list of all races, grouped by faction. */
export default function RaceSwitcher({ current, routes }: { current: RouteMeta; routes: RouteMeta[] }) {
  const { open, setOpen, buttonRef, rootRef } = useDisclosure();
  const panelId = useId();
  return (
    <div className="race-switcher" ref={rootRef}>
      <button ref={buttonRef} type="button" className={`race-button ${current.faction.toLowerCase()}`}
              aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}>
        <img className="crest-img" src={`/art/crest-${current.id}.webp`} alt="" width={30} height={30} />
        <span className="race-name">{current.race}</span>
        <span className="sr-only">, {current.faction}. Change race</span>
        <span className="chevron" aria-hidden="true">▾</span>
      </button>
      <div id={panelId} className="race-panel" hidden={!open}>
        {FACTIONS.map((faction) => (
          <div key={faction} className={`race-group ${faction.toLowerCase()}`}>
            <p className="race-group-title"><span aria-hidden="true">{CREST[faction]}</span> {faction}</p>
            <ul>
              {routes.filter((r) => r.faction === faction).map((r) => (
                <li key={r.id}>
                  <a href={`/${r.id}/`} aria-current={r.id === current.id ? 'page' : undefined}>
                    <img src={`/art/crest-${r.id}.webp`} alt="" width={28} height={28} loading="lazy" />
                    {r.race}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
