# DraftLens Data Dictionary

_This file is regenerated from your real data by `scripts/normalize_data.py`
(`npm run data:build`). It lists identity fields, every pre-draft feature with
its coverage %, and outcome labels with coverage %. Below is the fixed schema;
the feature/outcome tables fill in after your first local run._

## Identity fields

| Field | Description |
| --- | --- |
| playerId | Stable slug `name-draftClass` (deduped). |
| name / normName | Display name and normalized join key. |
| position / positionGroup | Raw position and DraftLens group (QB, RB, WR, TE, OL, DL, EDGE, LB, CB, S). |
| school | College / team. |
| draftClass | Draft year (from the spine). |
| actualPick / actualRound / actualTeam | Draft result (null for future prospects). |
| age | Age at draft, if present. |
| dataCompleteness | Fraction of known pre-draft features present for the player. |

## Pre-draft features (model inputs)

Discovered from your data and prefixed by source (e.g. `combine_forty`,
`pffgrades_yprr`, `college_rec_yards`), plus a derived `draft_capital`. The
generated table lists each feature and its coverage across players.

## Outcome labels (targets only — never features)

Discovered outcome fields (e.g. AV/wAV, games, starts, honors) with coverage.
These are used solely as training/validation labels. If none are found, the
model uses a transparent composite and records a warning.
