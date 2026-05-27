# DraftLens Model Methodology

DraftLens turns your local NFL/college data into one public **DraftLens Score
(1–99)** per player, plus transparent components, tiers, confidence, and
backtested accuracy. This document describes how — honestly, including the
limits.

## Principles

1. **No hallucination.** Every feature comes from a column that actually exists
   in your data. If a field is missing, the pipeline records a warning and falls
   back; it never invents values.
2. **No leakage.** Pre-draft features only. NFL outcome data (AV, games, starts,
   honors) is used *exclusively* as a training/validation label — never as a
   model input for a pre-draft score.
3. **Time-aware validation.** Draft modeling is temporal, so we use walk-forward
   validation (train older classes, test the next), never a random split.
4. **Interpretability first.** The core model is ridge/logistic regression with
   inspectable coefficients. We only adopt anything heavier if walk-forward
   results justify it.

## Pipeline

```
inventory_data.py   scan folder, profile every table, infer purpose/keys
normalize_data.py   build player spine, match sources, split features/labels
train_draftlens_model.py   select target, walk-forward backtest, score players
export_frontend_data.py    write public/data/model/*.json for the site
```

## Target selection (auto)

The trainer scans the outcome labels discovered during normalization and picks
the first match in this preference order (configurable in
`config/pipeline.config.json`):

```
weighted_av → wav → career_av → drafted_av → av → approximate_value
→ career_starts → starts → games_started → games → snaps
```

The chosen target and its units are recorded in `model_manifest.json` and shown
on the site. **If no usable outcome label exists**, the model switches to a
transparent unsupervised composite (weighted blend of component scores), marks
`backtest.dataReady = false`, and says so in warnings.

## Features → components

Pre-draft features are grouped into interpretable components (percentile-ranked
*within position group*, direction-aware so "lower is better" fields like the
40-yard dash are flipped):

| Component | Built from |
| --- | --- |
| Production | college counting/production stats |
| Efficiency | grades, YPRR, BTT, EPA, completion/“rate” fields |
| Athletic | 40, vertical, broad, bench, shuttle/3-cone |
| Size | weight, height, arm/wing/hand |
| Age | age at draft (younger scores higher) |
| Draft capital | derived from actual pick via a value-curve |
| Position value | positional priors (QB/EDGE/WR premium, etc.) |
| Risk | bust probability (logistic) |
| Upside | predicted-value tail blended with athletic/efficiency |
| Confidence | data completeness |

Position value priors are fixed and documented in
`scripts/train_draftlens_model.py` (`POSITION_VALUE`).

## DraftLens Score

- **Supervised:** ridge regression predicts the selected outcome from
  standardized pre-draft features; the prediction is percentile-mapped to 1–99.
- **Composite fallback:** a documented weighted average of components, 1–99.

Tiers are fixed score bands: Elite ≥ 85, High ≥ 75, Solid ≥ 60,
Developmental ≥ 45, Risk < 45.

**Value vs pick** is the residual of a player's score against the expected score
at their actual pick (log-pick regression). Positive = better than draft slot.
Future prospects (no pick) have `valueVsPick = null`.

## Backtesting

For each test class, the model trains on all earlier classes only and predicts
the held-out class. Out-of-sample predictions feed:

- overall correlation (mean across folds),
- hit/bust rate by tier (hit = outcome ≥ 60th pct, bust = outcome ≤ 25th pct of
  labeled players; thresholds configurable),
- correlation + hit rate by position, draft range, and class,
- biggest correct calls and biggest misses.

Full numbers land in `docs/backtest_report.md` and the Model Lab page.

## Honesty notes

- Small position/class cells produce noisy correlations — treat them as
  directional, not precise.
- The composite fallback is a ranking aid, not a validated predictor.
- DraftLens reports its measured accuracy; it does not claim accuracy it
  has not demonstrated on your data.
