import { memo, useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from 'react';

import {
  clusterPins, describeStep, dungeonsOnMap, groupByZone, levelRange, loadDone, loadSettings, pinLabel, questBrief,
  reportUrl, stepForLevel,
  mapStepsFor, openQuests, optionalOnMap, routeClasses, safeStorage, saveDone, pinIcon,
  saveSettings, searchSteps, stepsForClass, storageKey,
  type DungeonQuest, type KeyValueStore, type QuestVideo, type Part, type Route, type Settings, type Step,
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

/** One tag per class, in the class's game colour (RouteView.css, [data-class]); none for a quest of every class of
 *  the route (`every`), which follows class versions of a quest and shows once a class is chosen. */
function ClassTags({ classes, every }: { classes?: string[]; every?: number }) {
  if (every !== undefined && every > 1 && (classes?.length ?? 0) >= every) return null;
  return <>{classes?.map((c) => <span key={c} className="tag class" data-class={c}>{c}</span>)}</>;
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
  /** how many classes have quests on the route */
  classCount: number;
  onToggle: (step: Step, e: MouseEvent<HTMLButtonElement>) => void;
  register: (id: string, el: HTMLLIElement | null) => void;
}

const StepRow = memo(function StepRow({ step, n, isDone, isCurrent, reportHref, classCount, onToggle, register }:
  RowProps) {
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
          <ClassTags classes={step.classOnly} every={classCount} />
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

/** The quest's video on parchment, where a quest starts. Nothing loads from YouTube but the thumbnail until the
 * viewer presses the seal; then the player (privacy-enhanced mode, with YouTube's own controls) takes its place. */
function VideoScroll({ video }: { video: QuestVideo }) {
  const [playing, setPlaying] = useState(false);
  return (
    <section className="quest-scroll video-scroll" aria-labelledby="video-title">
      <h3 id="video-title">Quest video</h3>
      <p className="quest-zone">{video.title}{video.channel && <> · {video.channel}</>}</p>
      <div className="video-frame">
        {playing ? (
          <iframe src={`https://www.youtube-nocookie.com/embed/${video.id}?autoplay=1&rel=0`} title={video.title}
                  allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowFullScreen />
        ) : (
          <button type="button" className="video-play" onClick={() => setPlaying(true)}
                  aria-label={`Watch the quest: ${video.title}`}>
            <img src={`https://i.ytimg.com/vi/${video.id}/hqdefault.jpg`} alt="" loading="lazy" />
            <span className="video-seal" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false"><path d="M8 4.5v15l12-7.5z" /></svg>
            </span>
            <span className="video-cta" aria-hidden="true">Watch the quest</span>
          </button>
        )}
      </div>
      <p className="video-note">
        Plays from YouTube. <a href={`https://www.youtube.com/watch?v=${video.id}`} target="_blank"
                               rel="noopener noreferrer">Open on YouTube</a>
      </p>
    </section>
  );
}

/** A dungeon's quests: name and level ("?" when unknown), who gives it and where, and the route step for it. */
function QuestList({ quests, index }: { quests: DungeonQuest[]; index: Map<string, number> }) {
  return (
    <ol className="dungeon-quests-list">
      {quests.map((q) => (
        <li key={q.questId}>
          <span className="quest">{q.name ?? `quest #${q.questId}`}</span>{' '}
          <span className="lvl">({q.level ?? '?'})</span>
          <ClassTags classes={q.classOnly} />
          <span className="from">
            From <span className="npc">{q.npcName ?? 'unknown'}</span>
            {q.zoneName && <> in {q.zoneName}</>} at {q.x.toFixed(1)}, {q.y.toFixed(1)}.
            {' '}{q.step ? <>On your route: step {(index.get(q.step) ?? 0) + 1}.</> : <>Not on this route.</>}
          </span>
        </li>
      ))}
    </ol>
  );
}

interface SettingsProps {
  settings: Settings;
  update: (patch: Partial<Settings>) => void;
  /** steps marked done on this route; resetting clears them, after a second press to confirm */
  doneCount: number;
  onReset: () => void;
}

function Settings({ settings, update, doneCount, onReset }: SettingsProps) {
  const { open, setOpen, buttonRef, rootRef } = useDisclosure();
  const [confirming, setConfirming] = useState(false);
  const confirmRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (!open) setConfirming(false);
  }, [open]);
  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);
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
        <div className="reset">
          {confirming ? (
            <div role="group" aria-labelledby="reset-question" className="reset-confirm">
              <p id="reset-question">Clear all {doneCount} done steps on this route?</p>
              <button ref={confirmRef} type="button" className="danger"
                      onClick={() => { onReset(); setConfirming(false); }}>Reset</button>
              <button type="button" onClick={() => setConfirming(false)}>Cancel</button>
            </div>
          ) : (
            <button type="button" disabled={doneCount === 0} onClick={() => setConfirming(true)}>
              Reset progress
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function RouteView({ route, routes }: { route: Route; routes: RouteMeta[] }) {
  // Every class the race plays, also one with no class quests on the route (a Human hunter still picks Hunter).
  const classes = useMemo(() => route.classes ?? routeClasses(route.steps), [route.classes, route.steps]);
  const validIds = useMemo(() => new Set(route.steps.map((s) => s.id)), [route.steps]);

  const storeRef = useRef<KeyValueStore | null>(null);
  const store = () => (storeRef.current ??= safeStorage(() => window.localStorage));

  const [done, setDone] = useState<Set<string>>(() => new Set());
  const [loaded, setLoaded] = useState(false);
  const [settings, setSettings] = useState<Settings>({
    shortcuts: true, highContrast: false, playerClass: '', explore: false,
  });
  const [zoom, setZoom] = useState(0);
  // The dungeon whose quest panel is open (its Map id), and the marker to give focus back to when it closes.
  const [openDungeon, setOpenDungeon] = useState<number | null>(null);
  const dungeonButton = useRef<HTMLButtonElement | null>(null);
  const dungeonPanel = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => {
    if (openDungeon === null) return;
    dungeonPanel.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      setOpenDungeon(null);
      dungeonButton.current?.focus();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [openDungeon]);
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

  // Only the chosen class's quests are shown; with no class (or one this race cannot play) no class quests are.
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
  const resetDone = () => {
    const next = new Set<string>();
    setDone(next);
    saveDone(store(), route.id, next);
    setAnnouncement('Progress reset. Back to step 1.');
  };
  // A player who is already levelled starts where the route reaches their level: every step before it is done.
  const levels = useMemo(() => levelRange(steps), [steps]);
  const [startLevel, setStartLevel] = useState(0);
  const startAtLevel = (level: number) => {
    const at = stepForLevel(steps, level);
    if (at < 0) return;
    const next = new Set(steps.slice(0, at).map((s) => s.id));
    setDone(next);
    saveDone(store(), route.id, next);
    setAnnouncement(`Starting at step ${at + 1}, level ${steps[at].level}. The steps before it are marked done.`);
    focusStep(steps[at]);
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
  // Phones and tablets show the map as a sheet opened from a round button (RouteView.css, max-width 900px).
  const [narrow, setNarrow] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const fabRef = useRef<HTMLButtonElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 900px)');
    setNarrow(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setNarrow(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  const sheet = narrow && sheetOpen;
  const closeSheet = useCallback(() => {
    setSheetOpen(false);
    fabRef.current?.focus();
  }, []);
  useEffect(() => {
    if (!sheet) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeSheet();
    };
    document.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
    };
  }, [sheet, closeSheet]);
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
              <select value={playerClass} data-class={playerClass || undefined}
                      onChange={(e) => updateSettings({ playerClass: e.target.value })}>
                <option value="">Class</option>
                {classes.map((c) => <option key={c} value={c} data-class={c}>{c}</option>)}
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
        <Settings settings={settings} update={updateSettings} doneCount={doneCount} onReset={resetDone} />
      </div>
      <p id="announcer" className="sr-only" aria-live="polite">{announcement}</p>

      <div className="route-main">
        <section aria-label="Route steps" className="steps" data-loaded={loaded ? 'true' : 'false'}>
          {levels && levels[1] > levels[0] && (
            <form className="level-start" onSubmit={(e) => { e.preventDefault(); startAtLevel(Math.max(startLevel, levels[0])); }}>
              <label>
                <span>Already levelled? Start at level</span>
                <select value={Math.max(startLevel, levels[0])} onChange={(e) => setStartLevel(Number(e.target.value))}>
                  {Array.from({ length: levels[1] - levels[0] + 1 }, (_, i) => levels[0] + i)
                    .map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
              </label>
              <button type="submit">Go to that step</button>
            </form>
          )}
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
                  <StepRow key={s.id} step={s} n={(index.get(s.id) ?? 0) + 1} isDone={done.has(s.id)} classCount={classes.length}
                           isCurrent={s === current} onToggle={onRowToggle} register={register}
                           reportHref={s === current ? reportUrl(route, s, currentIndex + 1) : undefined} />
                ))}
              </ol>
            </section>
          ))}
        </section>

        {narrow && current && (
          <button ref={fabRef} type="button" className="map-fab" aria-controls="route-map" aria-expanded={sheet}
                  onClick={() => setSheetOpen(true)}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15M15 6v15" /></svg>
            Map
          </button>
        )}
        {sheet && <div className="map-scrim" aria-hidden="true" onClick={closeSheet} />}
        <div id="route-map" className={`mapbox${sheet ? ' open' : ''}`}
               aria-label={current ? `Map of ${current.zoneName ?? 'the current zone'}` : 'Map'}
               role={sheet ? 'dialog' : 'complementary'} aria-modal={sheet ? true : undefined}
               inert={narrow && !sheet ? true : undefined}>
          {narrow && (
            <button ref={closeRef} type="button" className="icon-button map-close" aria-label="Close map"
                    onClick={closeSheet}>×</button>
          )}
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
                  {dungeonsOnMap(route.dungeons ?? [], current.mapId, playerClass).map((d) => {
                    // Dungeon or raid entrance: the game's icon, a "!" at its top right when it has quests or an
                    // attunement for this race.
                    const count = d.quests.length + d.attunement.length;
                    return (
                    <button key={`dungeon-${d.id}`} type="button" className="pin dungeon"
                            style={{ left: `${d.x}%`, top: `${d.y}%` }} aria-haspopup="dialog"
                            aria-expanded={openDungeon === d.id}
                            aria-label={`${d.name}, ${d.kind}${count ? `, ${count} quests` : ''}`}
                            onClick={(e) => {
                              dungeonButton.current = e.currentTarget;
                              setOpenDungeon(openDungeon === d.id ? null : d.id);
                            }}>
                      <img src="/art/icon-dungeon.webp" alt="" width={28} height={28} />
                      {count > 0 && <img className="dungeon-quests" src="/art/icon-accept.webp" alt=""
                                         width={18} height={18} />}
                      <span className="pin-label">{d.name}</span>
                    </button>
                    );
                  })}
                  {settings.explore && optionalOnMap(route.optional ?? [], current.mapId, playerClass).map((q) => (
                    // Off-route quests: drawn under the route's pins, named on hover and in the list below.
                    <span key={`optional-${q.questId}`} role="img" style={{ left: `${q.x}%`, top: `${q.y}%` }}
                          className={`pin optional${(q.minLevel ?? q.level) > (current.level ?? 1) ? ' too-high' : ''}`}
                          aria-label={`Optional quest: ${q.name ?? `quest #${q.questId}`}, level ${q.level}`}>
                      <img src="/art/icon-accept.webp" alt="" width={20} height={20} />
                      <span className="pin-label">{q.name ?? `quest #${q.questId}`} ({q.level})</span>
                    </span>
                  ))}
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
              {(() => {
                const d = dungeonsOnMap(route.dungeons ?? [], current.mapId, playerClass)
                  .find((x) => x.id === openDungeon);
                if (!d) return null;
                return (
                  <section className="dungeon-panel" role="dialog" aria-labelledby="dungeon-title">
                    <div className="dungeon-head">
                      <h3 id="dungeon-title" ref={dungeonPanel} tabIndex={-1}>{d.name}</h3>
                      <button type="button" className="icon-button" aria-label="Close"
                              onClick={() => { setOpenDungeon(null); dungeonButton.current?.focus(); }}>×</button>
                    </div>
                    <p className="dungeon-sub">
                      {d.kind === 'raid' ? 'Raid' : 'Dungeon'}
                      {d.levels && <> · quests level {d.levels[0]}–{d.levels[1]}</>}
                    </p>
                    {d.attunement.length > 0 && (
                      <>
                        <h4>Attunement</h4>
                        <p className="dungeon-note">Done in this order; each quest opens the next.</p>
                        <QuestList quests={d.attunement} index={index} />
                      </>
                    )}
                    {d.quests.length > 0 && (
                      <>
                        {d.attunement.length > 0 && <h4>Quests</h4>}
                        <QuestList quests={d.quests} index={index} />
                      </>
                    )}
                    {d.quests.length + d.attunement.length === 0 && (
                      <p>No quests here that you can take.</p>
                    )}
                  </section>
                );
              })()}
              <div className="zoom" role="group" aria-label="Map zoom">
                <button type="button" aria-label="Zoom in" disabled={zoom === ZOOMS.length - 1}
                        onClick={() => setZoom((z) => Math.min(ZOOMS.length - 1, z + 1))}>+</button>
                <button type="button" aria-label="Zoom out" disabled={zoom === 0}
                        onClick={() => setZoom((z) => Math.max(0, z - 1))}>−</button>
                <button type="button" className="explore" aria-pressed={settings.explore}
                        onClick={() => updateSettings({ explore: !settings.explore })}>
                  All quests
                </button>
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
              {current.type === 'accept' && current.video && <VideoScroll key={current.video.id} video={current.video} />}
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
        </div>
      </div>
    </div>
  );
}
