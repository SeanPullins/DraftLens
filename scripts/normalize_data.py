#!/usr/bin/env python3
"""Normalize the inventoried data into a single player feature table.

Strategy (documented in docs/matching_strategy.md):
  1. Use draft tables (purpose=draft) as the player spine — one entity per
     (normalized name, draft class).
  2. Attach features from other tables by shared ID columns first, then by
     normalized name + position group (preferring same school / nearest season).
  3. Tag every attached field as a pre-draft FEATURE or a post-draft OUTCOME
     label by column-name provenance. Outcomes are never used as features.

Outputs (data/processed/):
  players_features.json        unified table: identity + features + outcomes
  player_entity_map.json       playerId -> how each source matched
  feature_manifest.json        pre-draft feature list + outcome field list
  unmatched_players.csv        source rows that matched no spine entity
  manual_player_overrides.csv  template (created if missing); applied if present
Plus docs/data_dictionary.md and docs/matching_strategy.md.

Usage: python3 scripts/normalize_data.py [--data-dir PATH]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dl_common as dl

# Identity-ish roles that are never treated as model features.
NON_FEATURE_ROLES = {"player_id", "name", "first_name", "last_name", "position", "team", "school", "season", "round"}


def _require_pandas():
    try:
        import pandas as pd  # type: ignore

        return pd
    except ImportError:
        dl.log("ERROR: pandas is required. Run: python3 -m pip install -r requirements.txt")
        raise SystemExit(2)


def read_table(source: str, fmt: str, pd) -> "Any":
    p = Path(source)
    if fmt in ("csv", "tsv"):
        return pd.read_csv(p, sep="\t" if fmt == "tsv" else None, engine="python", encoding="utf-8-sig")
    if fmt in ("xlsx", "xls"):
        return pd.read_excel(p)
    if fmt == "json":
        return pd.read_json(p)
    if fmt == "ndjson":
        return pd.read_json(p, lines=True)
    if fmt == "parquet":
        return pd.read_parquet(p)
    if fmt == "duckdb":
        import duckdb  # type: ignore

        path, table = source, None
        con = duckdb.connect(path, read_only=True)
        try:
            tbl = con.execute("SHOW TABLES").fetchone()
            table = tbl[0] if tbl else None
            return con.execute(f'SELECT * FROM "{table}"').df()
        finally:
            con.close()
    raise ValueError(f"unsupported format: {fmt}")


def role_map(columns: list[str]) -> dict[str, str]:
    """Map role -> first column name that fills it."""
    out: dict[str, str] = {}
    for c in columns:
        r = dl.classify_column(c)
        if r and r not in out:
            out[r] = c
    return out


def get_name(row: dict[str, Any], roles: dict[str, str]) -> str:
    if "name" in roles:
        return str(row.get(roles["name"], "") or "")
    first = str(row.get(roles.get("first_name", ""), "") or "")
    last = str(row.get(roles.get("last_name", ""), "") or "")
    return f"{first} {last}".strip()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def to_num(v: Any):
    if v is None:
        return None
    try:
        import math

        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def main() -> int:
    pd = _require_pandas()
    cfg = dl.load_config()
    ap = argparse.ArgumentParser(description="Normalize inventoried data into a player feature table.")
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args()
    _ = dl.resolve_data_dir(args.data_dir)  # validated for parity; reads come from inventory paths

    inv_path = dl.repo_path(cfg["processedDir"], "inventory.json")
    if not inv_path.exists():
        dl.log("ERROR: inventory not found. Run `npm run data:inventory` first.")
        return 2
    inventory = json.loads(inv_path.read_text())
    tables = inventory["tables"]
    cls_lo, cls_hi = cfg["draftClassRange"]

    # ----- load all readable tables -----
    loaded: list[dict[str, Any]] = []
    for t in tables:
        if t["rows"] == 0 or not t["columns"]:
            continue
        try:
            df = read_table(t["source"], t["fmt"], pd)
        except Exception as exc:  # noqa: BLE001
            dl.log(f"skip {t['name']}: {exc}")
            continue
        df.columns = [str(c).strip() for c in df.columns]
        loaded.append({"meta": t, "df": df, "roles": role_map(list(df.columns))})

    spines = [x for x in loaded if x["meta"]["purpose"] == "draft" and "pick" in x["roles"]]
    if not spines:
        dl.log("ERROR: no draft table with a pick column found — cannot build player spine.")
        dl.log("Inventory purposes seen: " + ", ".join(sorted({x['meta']['purpose'] for x in loaded})))
        return 2

    # ----- build spine entities -----
    entities: dict[str, dict[str, Any]] = {}
    norm_index: dict[tuple[str, str], list[str]] = defaultdict(list)  # (normName, posGroup) -> [playerId]
    id_index: dict[tuple[str, str], str] = {}  # (idCol, idValue) -> playerId

    for sp in spines:
        df, roles = sp["df"], sp["roles"]
        for rec in df.to_dict("records"):
            name = get_name(rec, roles)
            norm = dl.normalize_name(name)
            if not norm:
                continue
            season = to_num(rec.get(roles.get("season", "")))
            draft_class = int(season) if season else None
            if draft_class is None or not (cls_lo <= draft_class <= cls_hi + 5):
                # Keep within a sane window; still allow future-ish classes.
                if draft_class is None:
                    continue
            pos_group = dl.normalize_position(rec.get(roles.get("position", "")))
            base = slug(norm) or f"player-{len(entities)}"
            pid = f"{base}-{draft_class}"
            n = 1
            while pid in entities and entities[pid]["normName"] != norm:
                n += 1
                pid = f"{base}-{draft_class}-{n}"
            pick = to_num(rec.get(roles.get("pick", "")))
            rnd = to_num(rec.get(roles.get("round", "")))
            ent = entities.setdefault(
                pid,
                {
                    "playerId": pid,
                    "name": name,
                    "normName": norm,
                    "position": str(rec.get(roles.get("position", ""), "") or ""),
                    "positionGroup": pos_group or "UNK",
                    "school": str(rec.get(roles.get("school", ""), "") or ""),
                    "draftClass": draft_class,
                    "actualPick": int(pick) if pick else None,
                    "actualRound": int(rnd) if rnd else None,
                    "actualTeam": str(rec.get(roles.get("team", ""), "") or "") or None,
                    "age": to_num(rec.get(roles.get("age", ""))),
                    "features": {},
                    "outcomes": {},
                    "matched": {"_spine": sp["meta"]["name"]},
                },
            )
            norm_index[(norm, ent["positionGroup"])].append(pid)
            for role, col in roles.items():
                if role == "player_id":
                    val = rec.get(col)
                    if val not in (None, "", "nan"):
                        id_index[(col, str(val))] = pid

    dl.log(f"spine: {len(entities)} player entities")

    # ----- manual overrides -----
    overrides_path = dl.repo_path(cfg["processedDir"], "manual_player_overrides.csv")
    overrides: dict[tuple[str, str], str] = {}
    if overrides_path.exists():
        with open(overrides_path, newline="") as fh:
            for row in csv.DictReader(fh):
                key = (dl.normalize_name(row.get("source_name", "")), dl.normalize_position(row.get("source_position", "")))
                if row.get("override_player_id"):
                    overrides[key] = row["override_player_id"].strip()
    else:
        dl.write_text(
            overrides_path,
            "source_name,source_position,source_season,override_player_id,note\n",
        )

    # ----- attach features / outcomes from non-spine tables -----
    feature_names: set[str] = set()
    outcome_names: set[str] = set()
    unmatched: list[dict[str, Any]] = []

    def find_entity(rec: dict[str, Any], roles: dict[str, str]) -> str | None:
        # 1) shared id
        for role, col in roles.items():
            if role == "player_id":
                val = rec.get(col)
                if val not in (None, "", "nan") and (col, str(val)) in id_index:
                    return id_index[(col, str(val))]
        name = get_name(rec, roles)
        norm = dl.normalize_name(name)
        pos = dl.normalize_position(rec.get(roles.get("position", "")))
        if (norm, pos) in overrides:
            return overrides[(norm, pos)]
        # 2) name + position group
        cands = norm_index.get((norm, pos)) or []
        if not cands:
            # fall back to name-only across any position
            cands = [pid for (n, _), ids in norm_index.items() if n == norm for pid in ids]
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        # disambiguate by school, then nearest draft class to season+1
        school = dl.normalize_name(rec.get(roles.get("school", ""), ""))
        season = to_num(rec.get(roles.get("season", "")))
        best, best_score = None, -1e9
        for pid in cands:
            e = entities[pid]
            score = 0.0
            if school and dl.normalize_name(e["school"]) == school:
                score += 2
            if season and e["draftClass"]:
                score -= abs(e["draftClass"] - (int(season) + 1)) * 0.5
            if score > best_score:
                best, best_score = pid, score
        return best

    def numeric_features(df, roles, prefix: str) -> list[str]:
        skip = {roles[r] for r in NON_FEATURE_ROLES if r in roles} | {roles.get("age", ""), roles.get("pick", "")}
        feats = []
        for c in df.columns:
            if c in skip or c == "":
                continue
            if dl.classify_outcome(c):
                continue
            if pd.api.types.is_numeric_dtype(df[c]):
                feats.append((c, f"{prefix}_{c}"))
        return feats

    # choose best season row per entity for player-season tables
    for x in loaded:
        meta, df, roles = x["meta"], x["df"], x["roles"]
        if meta in [s["meta"] for s in spines]:
            continue
        is_outcome = meta["purpose"] == "outcomes" or any(dl.classify_outcome(c) for c in df.columns)
        prefix = re.sub(r"[^a-z0-9]+", "", meta["purpose"].lower()) or "src"
        feat_cols = numeric_features(df, roles, prefix)
        outcome_cols = [(c, c.lower()) for c in df.columns if dl.classify_outcome(c)]

        records = df.to_dict("records")
        # group rows by matched entity, keep the season closest to draftClass-1
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rec in records:
            pid = find_entity(rec, roles)
            if pid is None:
                unmatched.append(
                    {"table": meta["name"], "name": get_name(rec, roles), "position": str(rec.get(roles.get("position", ""), "") or "")}
                )
                continue
            grouped[pid].append(rec)

        for pid, recs in grouped.items():
            e = entities[pid]
            if "season" in roles and len(recs) > 1 and e["draftClass"]:
                target = e["draftClass"] - 1
                recs = sorted(recs, key=lambda r: abs((to_num(r.get(roles["season"])) or target) - target))
            rec = recs[0]
            e["matched"][meta["name"]] = "id" if any(
                r == "player_id" for r in roles
            ) else "name+pos"
            for src_col, feat_name in feat_cols:
                val = to_num(rec.get(src_col))
                if val is not None:
                    e["features"][feat_name] = val
                    feature_names.add(feat_name)
            if is_outcome:
                for src_col, _ in outcome_cols:
                    val = to_num(rec.get(src_col))
                    if val is not None:
                        e["outcomes"][src_col.lower()] = val
                        outcome_names.add(src_col.lower())

    # derived pre-draft feature: draft capital from pick (value-curve style)
    for e in entities.values():
        if e["actualPick"]:
            e["features"]["draft_capital"] = round(100.0 * (1.0 - (e["actualPick"] - 1) / 262.0) ** 1.5, 3)
            feature_names.add("draft_capital")

    # data completeness = fraction of all known features present
    all_feats = sorted(feature_names)
    for e in entities.values():
        e["dataCompleteness"] = round(
            sum(1 for f in all_feats if f in e["features"]) / max(1, len(all_feats)), 3
        )

    # ----- write outputs -----
    players = list(entities.values())
    out_dir = cfg["processedDir"]
    dl.write_json(dl.repo_path(out_dir, "players_features.json"), players)
    dl.write_json(
        dl.repo_path(out_dir, "player_entity_map.json"),
        {e["playerId"]: {"name": e["name"], "draftClass": e["draftClass"], "matched": e["matched"]} for e in players},
    )
    dl.write_json(
        dl.repo_path(out_dir, "feature_manifest.json"),
        {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "preDraftFeatures": all_feats,
            "outcomeFields": sorted(outcome_names),
            "playerCount": len(players),
        },
    )
    with open(dl.repo_path(out_dir, "unmatched_players.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["table", "name", "position"])
        w.writeheader()
        w.writerows(unmatched)

    write_dictionary(cfg, players, all_feats, sorted(outcome_names))
    write_matching_strategy(cfg, players, spines, unmatched)

    dl.log(
        f"normalized {len(players)} players · {len(all_feats)} pre-draft features · "
        f"{len(outcome_names)} outcome fields · {len(unmatched)} unmatched source rows"
    )
    return 0


def _coverage(players: list[dict], key_space: str, field: str) -> float:
    if not players:
        return 0.0
    return round(sum(1 for p in players if field in p[key_space]) / len(players), 3)


def write_dictionary(cfg, players, features, outcomes) -> None:
    lines = [
        "# DraftLens Data Dictionary",
        "",
        "_Auto-generated by `scripts/normalize_data.py` from the real local data._",
        "",
        "## Identity fields",
        "",
        "| Field | Description |",
        "| --- | --- |",
        "| playerId | Stable slug `name-draftClass` (deduped). |",
        "| name / normName | Display name and normalized join key. |",
        "| position / positionGroup | Raw position and DraftLens group (QB,RB,WR,TE,OL,DL,EDGE,LB,CB,S). |",
        "| school | College/team. |",
        "| draftClass | Draft year (spine). |",
        "| actualPick / actualRound / actualTeam | Draft result (null for future prospects). |",
        "| age | Age at draft if present. |",
        "| dataCompleteness | Fraction of known pre-draft features present for the player. |",
        "",
        "## Pre-draft features (model inputs)",
        "",
        "| Feature | Coverage |",
        "| --- | ---: |",
    ]
    for f in features:
        lines.append(f"| {f} | {_coverage(players, 'features', f) * 100:.0f}% |")
    lines += [
        "",
        "## Outcome labels (targets only — never features)",
        "",
        "| Field | Coverage |",
        "| --- | ---: |",
    ]
    for o in outcomes:
        lines.append(f"| {o} | {_coverage(players, 'outcomes', o) * 100:.0f}% |")
    if not outcomes:
        lines.append("| _none detected_ | — |")
    dl.write_text(dl.repo_path(cfg["docsDir"], "data_dictionary.md"), "\n".join(lines) + "\n")


def write_matching_strategy(cfg, players, spines, unmatched) -> None:
    matched_counts: dict[str, int] = defaultdict(int)
    for p in players:
        for src in p["matched"]:
            if not src.startswith("_"):
                matched_counts[src] += 1
    lines = [
        "# DraftLens Matching Strategy",
        "",
        "_Auto-generated by `scripts/normalize_data.py`._",
        "",
        "## Method",
        "",
        "1. **Spine**: draft tables define one entity per (normalized name, draft class).",
        "2. **ID join**: source rows attach via shared `*_id` columns when values overlap.",
        "3. **Name + position**: otherwise match on normalized name + position group,",
        "   disambiguating by same school and nearest season (`draftClass - 1`).",
        "4. **Manual overrides**: `data/processed/manual_player_overrides.csv` forces",
        "   specific matches (source_name + source_position -> override_player_id).",
        "",
        "Name normalization lowercases, strips accents/punctuation, and drops suffixes",
        "(Jr, Sr, II–V).",
        "",
        "## Results",
        "",
        f"- Spine tables: {', '.join(s['meta']['name'] for s in spines)}",
        f"- Player entities: **{len(players)}**",
        f"- Unmatched source rows: **{len(unmatched)}** (see `unmatched_players.csv`)",
        "",
        "| Source table | Players matched |",
        "| --- | ---: |",
    ]
    for src, n in sorted(matched_counts.items()):
        lines.append(f"| {src} | {n} |")
    dl.write_text(dl.repo_path(cfg["docsDir"], "matching_strategy.md"), "\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
