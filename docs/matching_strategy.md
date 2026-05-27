# DraftLens Matching Strategy

_This file is regenerated with real match counts by `scripts/normalize_data.py`
(`npm run data:build`). Below is the method; results populate after your first
local run._

## Method

1. **Spine** — draft tables (a table whose columns include a pick/overall
   column) define the player universe: one entity per **(normalized name, draft
   class)**, with a stable `playerId` slug.
2. **ID join** — source rows attach to the spine via shared `*_id` columns
   (gsis, pfr, pff, espn, sportradar, …) whenever values overlap.
3. **Name + position** — otherwise we match on normalized name + position group,
   disambiguating by same school and the nearest season (`draftClass - 1`).
4. **Manual overrides** — `data/processed/manual_player_overrides.csv` forces
   specific matches for hard cases (`source_name`, `source_position`,
   `source_season` → `override_player_id`). A blank template is created on first
   run.

## Normalization

- **Name:** lowercased; accents stripped; punctuation removed; suffixes
  (Jr, Sr, II–V) dropped; whitespace collapsed.
- **Position:** mapped to a DraftLens group — QB, RB, WR, TE, OL, DL, EDGE, LB,
  CB, S — via the alias table in `scripts/dl_common.py`.

## Outputs

| File | Contents |
| --- | --- |
| `data/processed/player_entity_map.json` | each `playerId` → how every source matched |
| `data/processed/unmatched_players.csv` | source rows that matched no spine entity |
| `data/processed/manual_player_overrides.csv` | your manual fixes (applied if present) |

Review `unmatched_players.csv` after each build; add overrides for the names
that matter and rebuild.
