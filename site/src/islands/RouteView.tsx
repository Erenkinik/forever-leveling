import { memo, useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from 'react';

import {
  clusterPins, describeStep, groupByZone, levelRange, loadDone, loadSettings, pinLabel, questBrief, reportUrl,
  mapStepsFor, openQuests, routeClasses, safeStorage, saveDone, pinIcon,
  saveSettings, searchSteps, stepsForClass, storageKey,
  type KeyValueStore, type Part, type Route, type Settings, type Step,
} from '../lib/steps.ts';
import mapIndex from '../data/maps.json';
import RaceSwitcher, { type RouteMeta } from './RaceSwitcher.tsx';
import StepIcon from './StepIcon.tsx';
import { useDisclosure } from './useDisclosure.ts';
import './RouteView.css';

// Zone map art (python -m pipeline maps): size per UiMap id, or null when the game has no art for it.
const MAP_ART = mapIndex.maps as Record<string, { width: number; height: number } | null>;

const ZOOMS = [1, 1.5, 2, 3];
const SEARCH_LIMIT = 8;
// Steps shown on the map: a few behind and ahead of the current step, on its map only (plus the quest log's).
const MAP_BEHIND = 2;
const MAP_AHEAD = 6;
// Pins are 28px with a mouse and 44px on touch screens (RouteView.css); pins whose centres are closer than
// the pin size plus a small gap are merged so targets never overlap (WCAG 2.5.8).
const PIN_SPACING_PX = { fine: 32, coarse: 48 };
// Objective areas: each spawn point is a soft circle of this radius (map x units); overlaps merge into one area.
const AREA_RADIUS = 2.2;

const isTodo = (s: Step, done: Set<string>) => s.type !== 'gap' && !done.has(s.id);
const plain = (s: Step) => describeStep(s).map((p) => p.text).join('');
const coords = (s: Step) => `${s.x.toFixed(1)}, ${s.y.toFixed(1)}`;

function Text({ parts }: { parts: Part[] }) {
  return (
    <>
      {parts.map((p, i) => (p.kind
        ? (
          <span key={i} className={p.kind}>
            {p.icon && <img className="item-icon" src={p.icon} alt="" width={22} height={22} loading="lazy" />}
            {p.text}
          </span>
        )
        : <span key={i}>{p.text}</span>))}
    </>
  );
}

/** Space is a page shortcut unless the user is typing or on a control that Space itself activates. */
function spaceBelongsToTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  if (el.classList.contains('mark')) return false; // the step buttons: Space means "mark the current step"
  return el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(el.tagName);
}

interface RowProps {
  step: Step;
  n: number;
  isDone: boolean;
  isCurrent: boolean;
  /** Only the current step gets a report link, so the list stays one tab stop per step. */
  reportHref?: string;
  onToggle: (step: Step, e: MouseEvent<HTMLButtonElement>) => void;
  register: (id: string, el: HTMLLIElement | null) => void;
}

const StepRow = memo(function StepRow({ step, n, isDone, isCurrent, reportHref, onToggle, register }: RowProps) {
  return (
    <li
      id={isCurrent ? 'current-step' : undefined}
      ref={(el) => register(step.id, el)}
      tabIndex={-1}
      className={`step ${step.type}${isDone ? ' done' : ''}${isCurrent ? ' current' : ''}`}
      aria-current={isCurrent ? 'step' : undefined}
      data-step-id={step.id}
    >
      <button type="button" className="mark" aria-pressed={isDone} aria-label={`Step ${n} done`}
              onClick={(e) => onToggle(step, e)}>
        {isDone ? '✓' : n}
      </button>
      <StepIcon step={step} />
      <div className="body">
        {isCurrent && <span className="now">Now</span>}
        <span className="text"><Text parts={describeStep(step)} /></span>
        <span className="meta">
          <span className="xy">{coords(step)}</span>
          {step.classOnly && <span className="tag class">{step.classOnly.join(', ')}</span>}
          {step.type === 'gap' && <span className="tag warn">Skipped</span>}
          {reportHref && (
            <a className="report" href={reportHref} target="_blank" rel="noopener noreferrer">
              Report this step<span className="sr-only"> (opens GitHub in a new tab)</span>
            </a>
          )}
        </span>
      </div>
    </li>
  );
});

function Settings({ settings, update }: { settings: Settings; update: (patch: Partial<Settings>) => void }) {
  const { open, setOpen, buttonRef, rootRef } = useDisclosure();
  return (
    <div className="settings" ref={rootRef}>
      <button ref={buttonRef} type="button" className="icon-button" aria-expanded={open}
              aria-controls="settings-panel" onClick={() => setOpen(!open)}>
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM19.4 13.5l1.8 1.4-2 3.4-2.1-.8a7 7 0 0 1-1.9 1.1L14.9 21h-4l-.3-2.4a7 7 0 0 1-1.9-1.1l-2.1.8-2-3.4 1.8-1.4a7 7 0 0 1 0-3L4.6 9.1l2-3.4 2.1.8a7 7 0 0 1 1.9-1.1L10.9 3h4l.3 2.4a7 7 0 0 1 1.9 1.1l2.1-.8 2 3.4-1.8 1.4a7 7 0 0 1 0 3z" />
        </svg>
        <span className="sr-only">Settings</span>
      </button>
      <div id="settings-panel" className="settings-panel" hidden={!open}>
        <label>
          <input type="checkbox" checked={settings.shortcuts} onChange={(e) => update({ shortcuts: e.target.checked })} />
          Space marks the current step done
        </label>
        <label>
          <input type="checkbox" checked={settings.highContrast} onChange={(e) => update({ highContrast: e.target.checked })} />
          High contrast
        </label>
      </div>
    </div>
  );
}

export default function RouteView({ route, routes }: { route: Route; routes: RouteMeta[] }) {
  const classes = useMemo(() => routeClasses(route.steps), [route.steps]);
  const validIds = useMemo(() => new Set(route.steps.map((s) => s.id)), [route.steps]);

  const storeRef = useRef<KeyValueStore | null>(null);
  const store = () => (storeRef.current ??= safeStorage(() => window.localStorage));

  const [done, setDone] = useState<Set<string>>(() => new Set());
  const [loaded, setLoaded] = useState(false);
  const [settings, setSettings] = useState<Settings>({ shortcuts: true, highContrast: false, playerClass: '' });
  const [zoom, setZoom] = useState(0);
  const [announcement, setAnnouncement] = useState('');
  const [query, setQuery] = useState('');
  const itemRefs = useRef(new Map<string, HTMLLIElement>());

  useEffect(() => {
    setDone(loadDone(store(), route.id, validIds));
    setSettings(loadSettings(store()));
    setLoaded(true);
    // Another tab of the same route saved progress: take it over instead of overwriting it later.
    const onStorage = (e: StorageEvent) => {
      if (e.key === storageKey(route.id)) setDone(loadDone(store(), route.id, validIds));
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [route.id, validIds]);

  useEffect(() => {
    document.documentElement.dataset.contrast = settings.highContrast ? 'high' : '';
  }, [settings.highContrast]);

  // Only the chosen class's quests are shown (a class this race cannot play shows every class).
  const playerClass = classes.includes(settings.playerClass) ? settings.playerClass : '';
  const steps = useMemo(() => stepsForClass(route.steps, playerClass), [route.steps, playerClass]);
  const index = useMemo(() => new Map(steps.map((s, i) => [s.id, i])), [steps]);
  const groups = useMemo(() => groupByZone(steps), [steps]);

  const updateSettings = (patch: Partial<Settings>) => {
    const next = { ...settings, ...patch };
    setSettings(next);
    saveSettings(store(), next);
  };

  // Skipped (gap) steps are information, not something to do: they never become the current step.
  const currentIndex = steps.findIndex((s) => isTodo(s, done));
  const current = currentIndex >= 0 ? steps[currentIndex] : undefined;

  const toggle = (step: Step) => {
    const next = new Set(done);
    const wasDone = next.has(step.id);
    if (wasDone) next.delete(step.id);
    else next.add(step.id);
    setDone(next);
    saveDone(store(), route.id, next);
    const n = (index.get(step.id) ?? 0) + 1;
    const following = steps.find((s) => isTodo(s, next));
    setAnnouncement(wasDone
      ? `Step ${n} marked not done.`
      : `Step ${n} done.${following ? ` Next: ${plain(following)}.` : ' Route complete.'}`);
  };
  // Stable callbacks for the memoised rows; they always call the latest toggle.
  const toggleRef = useRef(toggle);
  toggleRef.current = toggle;
  const onRowToggle = useCallback((step: Step, e: MouseEvent<HTMLButtonElement>) => {
    toggleRef.current(step);
    // A mouse click leaves focus on the button, where Space would click it again; move focus to the row.
    if (e.detail > 0) (e.currentTarget.closest('li') as HTMLLIElement | null)?.focus({ preventScroll: true });
  }, []);
  const register = useCallback((id: string, el: HTMLLIElement | null) => {
    if (el) itemRefs.current.set(id, el);
    else itemRefs.current.delete(id);
  }, []);

  useEffect(() => {
    if (!settings.shortcuts) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== ' ' || e.ctrlKey || e.metaKey || e.altKey || spaceBelongsToTarget(e.target)) return;
      e.preventDefault();
      if (e.repeat) return; // holding Space must not run through the route
      const cur = steps.find((s) => isTodo(s, done));
      if (cur) toggleRef.current(cur);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [settings.shortcuts, steps, done]);

  // Map frame width for pin merging; a callback ref so a frame that remounts is observed again.
  const [frameWidth, setFrameWidth] = useState(400);
  const [coarse, setCoarse] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(pointer: coarse)');
    setCoarse(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setCoarse(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  const observerRef = useRef<ResizeObserver | null>(null);
  const frameRef = useCallback((el: HTMLDivElement | null) => {
    observerRef.current?.disconnect();
    if (!el) return;
    observerRef.current = new ResizeObserver(([entry]) => {
      setFrameWidth(Math.max(100, Math.round(entry.contentRect.width / 20) * 20));
    });
    observerRef.current.observe(el);
  }, []);

  const mapSteps = mapStepsFor(steps, currentIndex, done, MAP_BEHIND, MAP_AHEAD);
  const inLog = openQuests(steps, done);
  // The current step leads its cluster, so a merged pin is drawn where the player has to go (done steps are off the
  // map, so a merged pin always shows what is left there, e.g. the grey "?" of a turn-in).
  const art = current ? MAP_ART[String(current.mapId)] ?? null : null;
  const pins = current
    ? clusterPins([current, ...mapSteps.filter((s) => s !== current)],
      (PIN_SPACING_PX[coarse ? 'coarse' : 'fine'] / (frameWidth * ZOOMS[zoom])) * 100,
      art ? art.height / art.width : 1)
    : [];
  const focusStep = (s: Step) => {
    const el = itemRefs.current.get(s.id);
    el?.scrollIntoView({ block: 'center' });
    el?.focus();
  };
  const position = current ? currentIndex + 1 : steps.length;
  // One more than shown, so "8+" only appears when there really are more.
  const found = searchSteps(steps, query, Math.max(0, currentIndex), SEARCH_LIMIT + 1);
  const matches = found.slice(0, SEARCH_LIMIT);
  const doneCount = steps.reduce((n, s) => n + (done.has(s.id) ? 1 : 0), 0);

  return (
    <div className="route-view">
      <div className="topbar">
        <div className="who">
          <RaceSwitcher current={{ id: route.id, race: route.race, faction: route.faction }} routes={routes} />
          {classes.length > 0 && (
            <label className="class-pick">
              <span className="sr-only">Class</span>
              <select value={playerClass} onChange={(e) => updateSettings({ playerClass: e.target.value })}>
                <option value="">All classes</option>
                {classes.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
          )}
        </div>
        <div className="progress">
          <label htmlFor="route-progress">
            <span className="progress-step">Step {position}<span className="of"> / {steps.length}</span></span>
            {current?.level !== undefined && <span className="progress-level" title="Estimated level">Level {current.level}</span>}
          </label>
          <progress id="route-progress" max={steps.length} value={doneCount} />
        </div>
        <div className="search">
          <label htmlFor="step-search" className="sr-only">Find a quest or NPC</label>
          <input id="step-search" type="search" value={query} autoComplete="off" placeholder="Find a quest or NPC"
                 onChange={(e) => setQuery(e.target.value)} aria-describedby="step-search-count" />
          <p id="step-search-count" className="sr-only" aria-live="polite">
            {query.trim() ? `${found.length > SEARCH_LIMIT ? `${SEARCH_LIMIT}+` : found.length} found` : ''}
          </p>
          {query.trim() !== '' && (
            <ul className="search-results">
              {matches.length === 0 && <li className="search-empty">No quest or NPC matches.</li>}
              {matches.map((s) => (
                <li key={s.id}>
                  <button type="button" onClick={() => { focusStep(s); setQuery(''); }}>
                    <strong>{(index.get(s.id) ?? 0) + 1}</strong> {plain(s)}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <Settings settings={settings} update={updateSettings} />
      </div>
      <p id="announcer" className="sr-only" aria-live="polite">{announcement}</p>

      <div className="route-main">
        <section aria-label="Route steps" className="steps" data-loaded={loaded ? 'true' : 'false'}>
          {groups.map((g) => (
            <section key={g.key}>
              <h2 className="zone">
                {g.zoneName}
                {(() => {
                  const range = levelRange(g.steps);
                  return range && <span className="zone-levels">Levels {range[0]}–{range[1]}</span>;
                })()}
              </h2>
              <ol>
                {g.steps.map((s) => (
                  <StepRow key={s.id} step={s} n={(index.get(s.id) ?? 0) + 1} isDone={done.has(s.id)}
                           isCurrent={s === current} onToggle={onRowToggle} register={register}
                           reportHref={s === current ? reportUrl(route, s, currentIndex + 1) : undefined} />
                ))}
              </ol>
            </section>
          ))}
        </section>

        <aside className="mapbox" aria-label={current ? `Map of ${current.zoneName ?? 'the current zone'}` : 'Map'}>
          {current ? (
            <>
              <h2 className="map-title">{current.zoneName ?? `map #${current.mapId}`}</h2>
              <div className="map-frame" ref={frameRef}>
                <div
                  className={`map${art ? ' art' : ''}`}
                  style={art
                    ? { width: `${ZOOMS[zoom] * 100}%`, aspectRatio: `${art.width} / ${art.height}`,
                        backgroundImage: `url(/maps/${current.mapId}.webp)` }
                    : { width: `${ZOOMS[zoom] * 100}%` }}
                >
                  {(() => {
                    // Where to kill / collect / use: the current quest strongly, the other quests in the log clearly,
                    // upcoming quests on this map faintly.
                    const ry = AREA_RADIUS * (art ? art.width / art.height : 1);
                    const onMap = (s: Step) => s.type === 'complete' && s.mapId === current.mapId && !!s.area?.length;
                    const active = steps.filter((s) => onMap(s) && s.questId === current.questId && !done.has(s.id));
                    const logged = mapSteps.filter((s) => onMap(s) && !done.has(s.id) && !active.includes(s)
                      && s.questId !== undefined && inLog.has(s.questId));
                    const upcoming = mapSteps.filter((s) => onMap(s) && !done.has(s.id) && !active.includes(s)
                      && !logged.includes(s));
                    const blobs = (list: Step[]) => list.flatMap((s) => (s.area ?? []).map(([x, y]) => (
                      <ellipse key={`${s.id}-${x}-${y}`} cx={x} cy={y} rx={AREA_RADIUS} ry={ry} />
                    )));
                    return (
                      <svg className="areas" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"
                           focusable="false">
                        <g className="area upcoming">{blobs(upcoming)}</g>
                        <g className="area logged">{blobs(logged)}</g>
                        <g className="area active">{blobs(active)}</g>
                      </svg>
                    );
                  })()}
                  {!art && (
                    <svg viewBox="0 0 100 100" aria-hidden="true" focusable="false" className="grid">
                      {[10, 20, 30, 40, 50, 60, 70, 80, 90].map((v) => (
                        <g key={v}>
                          <line x1={v} y1={0} x2={v} y2={100} />
                          <line x1={0} y1={v} x2={100} y2={v} />
                        </g>
                      ))}
                    </svg>
                  )}
                  {pins.map((group) => {
                    const lead = group[0];
                    const numbers = group.map((s) => (index.get(s.id) ?? 0) + 1).sort((a, b) => a - b);
                    const state = lead === current ? 'current' : group.every((s) => done.has(s.id)) ? 'done' : 'todo';
                    const n = (index.get(lead.id) ?? 0) + 1;
                    const icon = pinIcon(lead, steps, done);
                    // A turn-in merged under another step still shows its "?" (grey while the quest is not done).
                    const turnIn = group.slice(1).map((s) => pinIcon(s, steps, done))
                      .find((i) => (i === 'progress' || i === 'turnin') && i !== icon);
                    // Starts with the visible text (number, label) so the name matches what is seen (WCAG 2.5.3).
                    const label = `${n} ${pinLabel(lead)}, ` + (group.length === 1
                      ? `step ${n} at ${coords(lead)}: ${plain(lead)}`
                      : `steps ${numbers.join(', ')} near ${coords(lead)}`);
                    return (
                      <button
                        key={lead.id}
                        type="button"
                        className={`pin ${state}${group.length > 1 ? ' multi' : ''}${icon ? ' has-icon' : ''}${icon === 'progress' ? ' progress' : ''}`}
                        style={{ left: `${lead.x}%`, top: `${lead.y}%` }}
                        aria-label={label}
                        onClick={() => focusStep(lead)}
                      >
                        {icon && <img src={`/art/icon-${icon}.webp`} alt="" width={32} height={32} />}
                        {icon && turnIn && (
                          <img className={`pin-extra ${turnIn}`} src={`/art/icon-${turnIn}.webp`} alt="" width={20}
                               height={20} />
                        )}
                        <span className="pin-num">{state === 'done' ? '✓' : n}</span>{' '}
                        <span className="pin-label">{pinLabel(lead)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="zoom" role="group" aria-label="Map zoom">
                <button type="button" aria-label="Zoom in" disabled={zoom === ZOOMS.length - 1}
                        onClick={() => setZoom((z) => Math.min(ZOOMS.length - 1, z + 1))}>+</button>
                <button type="button" aria-label="Zoom out" disabled={zoom === 0}
                        onClick={() => setZoom((z) => Math.max(0, z - 1))}>−</button>
              </div>
              {(() => {
                const brief = questBrief(steps, current, done);
                return (
                  <section className="quest-scroll" aria-labelledby="quest-title">
                    <h3 id="quest-title">{brief.title}</h3>
                    <p className="quest-zone">{brief.zone}</p>
                    <ol>
                      {brief.items.map((item, i) => (
                        <li key={`${item.stepId}-${i}`} className={item.state}
                            aria-current={item.state === 'current' ? 'step' : undefined}>
                          <Text parts={item.parts} />
                          {item.state === 'done' && <span className="sr-only"> (done)</span>}
                        </li>
                      ))}
                    </ol>
                  </section>
                );
              })()}
              <details className="coords-details">
                <summary>All pins on this map</summary>
                <ol className="coords" aria-label="Coordinates of the steps on the map">
                  {mapSteps.map((s) => (
                    <li key={s.id}><strong>{(index.get(s.id) ?? 0) + 1}</strong> {coords(s)} · {plain(s)}</li>
                  ))}
                </ol>
              </details>
              <p className="map-note">
                {art ? 'Map art © Blizzard Entertainment. ' : 'Simple coordinate grid (0–100). '}
                Coordinates match the in-game map.
              </p>
            </>
          ) : (
            <p id="current-step" tabIndex={-1}>Route complete. Well done!</p>
          )}
        </aside>
      </div>
    </div>
  );
}
