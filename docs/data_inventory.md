# DraftLens Data Inventory

_This file is regenerated from your real data by `scripts/inventory_data.py`
(`npm run data:inventory`). It is structure-only — column names and counts, no
raw player values._

Run the inventory to populate it. For each table you'll get:

- file path, format, row count, column count
- inferred purpose (draft / combine / pff_grades / college / outcomes / …)
- candidate join keys (player_id, name, position, school, season, pick, round, …)
- candidate outcome fields (used as labels only)
- sample columns and any read warnings

A summary table groups tables by inferred purpose with total row counts.

> Awaiting first local run. Point the pipeline at your data with
> `--data-dir`, the `DRAFTLENS_DATA_DIR` env var, or `config/pipeline.config.json`.
