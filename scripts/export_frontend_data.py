#!/usr/bin/env python3
"""Export model output into the frontend-safe JSON contract (public/data/model).

Reads data/processed/model_output.json (from train) + inventory.json, and writes
the five files the React app consumes, matching src/lib/types.ts exactly:
  draftlens_players.json, classes.json, model_manifest.json,
  backtest_summary.json, position_summaries.json

Usage: python3 scripts/export_frontend_data.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

import dl_common as dl


def main() -> int:
    cfg = dl.load_config()
    proc, pub = cfg["processedDir"], cfg["publicModelDir"]
    mo_path = dl.repo_path(proc, "model_output.json")
    if not mo_path.exists():
        dl.log("ERROR: run `npm run model:train` first (missing model_output.json).")
        return 2
    mo = json.loads(mo_path.read_text())
    records = mo["players"]

    # ---- players (strip internal helper fields) ----
    players = []
    is_future = {}
    for r in records:
        r = dict(r)
        is_future[r["playerId"]] = bool(r.pop("_isFuture", False))
        players.append(r)
    dl.write_json(dl.repo_path(pub, "draftlens_players.json"), players)

    # ---- classes ----
    by_year = defaultdict(list)
    for r in players:
        if r["draftClass"]:
            by_year[r["draftClass"]].append(r)
    years_with_outcomes = [y for y, recs in by_year.items() if any(x["realizedValue"] is not None for x in recs)]
    max_outcome_year = max(years_with_outcomes) if years_with_outcomes else None

    classes = []
    for year in sorted(by_year):
        recs = by_year[year]
        has_out = any(x["realizedValue"] is not None for x in recs)
        if has_out:
            kind = "historical"
        elif max_outcome_year is not None and year > max_outcome_year:
            kind = "future"
        else:
            kind = "recent"
        top = [r["playerId"] for r in sorted(recs, key=lambda x: -x["draftLensScore"])[:5]]
        classes.append({
            "year": year,
            "kind": kind,
            "playerCount": len(recs),
            "topPlayerIds": top,
            "positionsCovered": sorted({r["positionGroup"] for r in recs}),
            "hasOutcomes": has_out,
        })
    dl.write_json(dl.repo_path(pub, "classes.json"), classes)

    # ---- manifest (datasets from inventory if available) ----
    datasets = []
    inv_path = dl.repo_path(proc, "inventory.json")
    if inv_path.exists():
        inv = json.loads(inv_path.read_text())
        for t in inv.get("tables", []):
            datasets.append({"name": t["name"], "rows": t["rows"], "columns": len(t["columns"]), "purpose": t["purpose"]})

    manifest = {
        "modelVersion": mo["modelVersion"],
        "generatedAt": mo.get("generatedAt") or datetime.now(timezone.utc).isoformat(),
        "dataReady": len(players) > 0,
        "playerCount": len(players),
        "classesAvailable": sorted(by_year.keys()),
        "outcomeTarget": mo.get("outcomeTarget"),
        "outcomeUnits": mo.get("outcomeUnits"),
        "datasets": datasets,
        "warnings": mo.get("warnings", []),
    }
    dl.write_json(dl.repo_path(pub, "model_manifest.json"), manifest)

    # ---- backtest summary (already shaped by train) ----
    dl.write_json(dl.repo_path(pub, "backtest_summary.json"), mo["backtest"])

    # ---- position summaries ----
    dl.write_json(
        dl.repo_path(pub, "position_summaries.json"),
        {"dataReady": len(mo["positions"]) > 0, "positions": mo["positions"]},
    )

    dl.log(
        f"exported {len(players)} players, {len(classes)} classes, "
        f"{len(datasets)} datasets to {pub}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
