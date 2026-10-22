# ForeverXP

A free leveling guide for WoW Forever: a step-by-step quest route from level 1 to 30 for every race, as a website and (later) an in-game addon.

> **Beta.** Routes are generated from open quest data and have not been played through yet. Found a wrong step? Use "Report this step" on the site or [open an issue](https://github.com/Erenkinik/forever-leveling/issues/new).

## How it works

- `pipeline/` (Python 3.14) builds a canonical quest database from open sources, then generates one route per race from a zone order (`data/zone-order/*.yaml`). See `docs/plan.md`.
- `site/` (Astro + React) shows the routes: race picker, step list, coordinate map, progress saved in the browser.
- `addon/ForeverXP/` will show the same routes in game.

## Development

```powershell
python -m venv .venv
.venv\Scripts\pip install pytest jsonschema PyYAML
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m pipeline validate --all

cd site
npm ci
npm run test:unit
npm run test:e2e
npm run dev
```

## License

Code: MIT (see `LICENSE`). Data sources and their licenses: `THIRD_PARTY.md`.
World of Warcraft and Blizzard Entertainment are trademarks of Blizzard Entertainment, Inc. This project is not affiliated with or endorsed by Blizzard.
