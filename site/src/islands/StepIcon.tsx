import { stepIcon, type Step } from '../lib/steps.ts';

// The game's own map icons (yellow ! and ?, swords, loot sack, gear, skull); line icons for travel and skips.
export default function StepIcon({ step }: { step: Step }) {
  const icon = stepIcon(step);
  if (icon) {
    return <img className={`step-icon game ${icon}`} src={`/art/icon-${icon}.webp`} alt="" width={28} height={28} />;
  }
  return (
    <svg className={`step-icon ${step.type}`} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={PATHS[step.type === 'travel' && step.mode && step.mode !== 'walk' ? 'ship' : step.type] ?? PATHS.travel} />
    </svg>
  );
}

const PATHS: Record<string, string> = {
  // crossed swords
  complete: 'M4 4l7 7M4 4h4M4 4v4M20 4l-7 7M20 4h-4M20 4v4M9 15l-4 4M15 15l4 4M7 13l4 4M17 13l-4 4',
  // footsteps arrow
  travel: 'M4 12h13M13 7l5 5-5 5',
  // ship
  ship: 'M3 16l2 4h14l2-4H3zM12 3v11M12 4l6 8h-6M12 6l-5 6h5',
  // circular arrow
  grind: 'M19 12a7 7 0 1 1-2.05-4.95M19 4v4h-4',
  // dashed circle with a bar: skipped
  gap: 'M12 3a9 9 0 1 0 0.01 0M8 12h8',
  sethearth: 'M5 20h14M7 20V9l5-5 5 5v11',
  train: 'M12 3l2.5 5 5.5.8-4 3.9.9 5.5L12 15.6 7.1 18.2l.9-5.5-4-3.9 5.5-.8z',
};
