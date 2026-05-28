#!/usr/bin/env python3
"""Build the gold-layer training dataset (one row per drafted player).

Reads  data/processed/players_features.json  (silver, built by normalize_data.py)
and writes:

  data/gold/draftlens_training_dataset.csv     one row per player
  data/gold/draftlens_training_dataset.parquet (if pyarrow is installed)
  data/gold/dataset_manifest.json              column list + coverage stats

Column layout (all column names are safe for pandas / sklearn):

  Identity (never used as model features):
    player_id, name, position, position_group, school,
    draft_class, actual_pick, actual_round, actual_team, age,
    data_completeness

  Pre-draft features (model inputs):
    one column per feature found in entity["features"]
    column names are taken verbatim from the feature manifest

  Outcome labels (targets, never inputs):
    one column per outcome found in entity["outcomes"]
    prefixed with "outcome_" to make leakage impossible at a glance

The script enforces the no-leakage boundary:
  - Columns classified by OUTCOME_PATTERNS are always prefixed "outcome_"
  - A player's draft class is in "draft_class" — it must not be used as a
    feature by callers; train/test splits should be on this column.

Usage:
  python3 scripts/build_training_dataset.py [--data-dir PATH]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import dl_common as dl


def _require_pandas():
    try:
        import pandas as pd  # type: ignore
        return pd
    except ImportError:
        dl.log("ERROR: pandas is required. Run: pip install -r requirements.txt")
        raise SystemExit(2)


def main() -> int:
    pd = _require_pandas()
    cfg = dl.load_config()
    proc = cfg["processedDir"]
    gold = cfg.get("goldDir", "data/gold")

    players_path = dl.repo_path(proc, "players_features.json")
    fm_path = dl.repo_path(proc, "feature_manifest.json")
    if not players_path.exists():
        dl.log("ERROR: players_features.json not found. Run `npm run data:normalize` first.")
        return 2
    if not fm_path.exists():
        dl.log("ERROR: feature_manifest.json not found. Run `npm run data:normalize` first.")
        return 2

    players = json.loads(players_path.read_text())
    fm = json.loads(fm_path.read_text())
    feature_cols: list[str] = fm["preDraftFeatures"]
    outcome_cols: list[str] = fm["outcomeFields"]

    if not players:
        dl.log("ERROR: no players to export (players_features.json is empty).")
        return 2

    dl.log(f"building gold dataset from {len(players)} players, {len(feature_cols)} features, {len(outcome_cols)} outcome fields")

    # Build rows
    identity_keys = [
        ("player_id", "playerId"),
        ("name", "name"),
        ("position", "position"),
        ("position_group", "positionGroup"),
        ("school", "school"),
        ("draft_class", "draftClass"),
        ("actual_pick", "actualPick"),
        ("actual_round", "actualRound"),
        ("actual_team", "actualTeam"),
        ("age", "age"),
        ("data_completeness", "dataCompleteness"),
    ]

    rows = []
    for p in players:
        row: dict = {}
        for col, key in identity_keys:
            row[col] = p.get(key)
        for f in feature_cols:
            row[f] = p["features"].get(f)
        for o in outcome_cols:
            row[f"outcome_{o}"] = p["outcomes"].get(o)
        rows.append(row)

    df = pd.DataFrame(rows)

    # Ensure identity columns are first, then features, then outcomes
    id_cols = [c for c, _ in identity_keys]
    feat_cols_present = [f for f in feature_cols if f in df.columns]
    out_cols_present = [f"outcome_{o}" for o in outcome_cols if f"outcome_{o}" in df.columns]
    df = df[id_cols + feat_cols_present + out_cols_present]

    out_dir = dl.repo_path(gold)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "draftlens_training_dataset.csv"
    df.to_csv(csv_path, index=False)
    dl.log(f"wrote {csv_path}  ({len(df)} rows × {len(df.columns)} cols)")

    # Parquet (optional — requires pyarrow)
    try:
        import pyarrow  # type: ignore  # noqa: F401
        parquet_path = out_dir / "draftlens_training_dataset.parquet"
        df.to_parquet(parquet_path, index=False)
        dl.log(f"wrote {parquet_path}")
    except ImportError:
        dl.log("pyarrow not installed — skipping parquet output (CSV is sufficient)")

    # Coverage stats per column
    n = len(df)
    coverage = {col: round(df[col].notna().sum() / max(1, n), 3) for col in df.columns}

    manifest = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "playerCount": n,
        "identityCols": id_cols,
        "featureCols": feat_cols_present,
        "outcomeCols": out_cols_present,
        "coverage": coverage,
        "classBreakdown": df.groupby("draft_class").size().to_dict() if "draft_class" in df.columns else {},
    }
    dl.write_json(out_dir / "dataset_manifest.json", manifest)
    dl.log(f"wrote {out_dir}/dataset_manifest.json")
    dl.log(
        f"gold dataset: {n} players · "
        f"{len(feat_cols_present)} feature cols · "
        f"{len(out_cols_present)} outcome cols"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
