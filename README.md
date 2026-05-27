# DraftLens

A transparent NFL Draft analytics platform. DraftLens turns your local NFL and
college data into one explainable **DraftLens Score (1–99)** per player, with
position-specific components, tiers, confidence, comps, and walk-forward
backtests — across historical, recent, and future draft classes.

## Architecture

```
local data  ──▶  Python pipeline  ──▶  public/data/model/*.json  ──▶  static React site
(private)        (runs on your box)     (committed, frontend-safe)      (GitHub Pages)
```

- **Local raw data builds model outputs.** The pipeline reads your data folder
  (read-only) and writes frontend-safe JSON. It is schema-agnostic: it profiles
  whatever files you have and never assumes a column exists.
- **The public site only consumes generated JSON.** It builds and deploys with
  no access to your private data. Until you generate data, it shows honest
  empty states with the commands to run.

## Quickstart

### 1. Web app

```bash
npm install
npm run dev          # http://localhost:5173/DraftLens/
npm run build        # production build -> dist/
```

### 2. Data + model pipeline (run where your data lives)

```bash
python3 -m pip install -r requirements.txt

# point it at your data folder (any one of these):
export DRAFTLENS_DATA_DIR="~/Documents/Draftwebsiteinfo"
#   or pass --data-dir, or edit config/pipeline.config.json

npm run data:inventory   # scan + profile every file -> docs/data_inventory.md
npm run data:build       # normalize, match players -> data/processed/
npm run model:train      # train + walk-forward backtest -> docs/backtest_report.md
npm run model:export     # write public/data/model/*.json for the site
```

Then `npm run dev` (or `build`) and the site is populated. Commit the refreshed
`public/data/model/*.json` to publish.

## Scripts

| Command | Does |
| --- | --- |
| `npm run dev` / `build` / `preview` | Vite dev / production build / preview |
| `npm run data:inventory` | Profile the data folder (schema-agnostic) |
| `npm run data:build` | Normalize + player identity matching |
| `npm run model:train` | Train model, run walk-forward backtest, score players |
| `npm run model:export` | Emit frontend-safe JSON contract |
| `npm run validate` | Typecheck + production build |

## Data privacy

`local_data/`, `data_private/`, `data/raw/`, `data/processed/`, and raw
spreadsheet/parquet/duckdb files are gitignored. Only frontend-safe outputs in
`public/data/model/` and the generated docs are committed. The pipeline never
writes to your source folder.

## Deployment

GitHub Pages, base path `/DraftLens/` (override with `VITE_BASE`). The Actions
workflow builds the committed JSON + app — no private data needed in CI. See
`docs/model_methodology.md` for how scoring and backtesting work.
