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
import gc
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


def read_table(source: str, fmt: str, pd, table_name: str | None = None) -> "Any":
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

        con = duckdb.connect(source, read_only=True)
        try:
            if table_name is None:
                tbl = con.execute("SHOW TABLES").fetchone()
                table_name = tbl[0] if tbl else None
            return con.execute(f'SELECT * FROM "{table_name}"').df()
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
    ap.add_argument("--include-unknown", action="store_true", help="Also load tables whose purpose was inferred as 'unknown'.")
    ap.add_argument("--max-rows", type=int, default=None, help="Skip any single table with more than N rows (e.g. play-by-play).")
    args = ap.parse_args()
    _ = dl.resolve_data_dir(args.data_dir)  # validated for parity; reads come from inventory paths

    inv_path = dl.repo_path(cfg["processedDir"], "inventory.json")
    if not inv_path.exists():
        dl.log("ERROR: inventory not found. Run `npm run data:inventory` first.")
        return 2
    inventory = json.loads(inv_path.read_text())
    tables = inventory["tables"]
    cls_lo, cls_hi = cfg["draftClassRange"]

    # ----- load relevant tables (with progress) -----
    relevant = {"draft", "combine", "pff_grades", "college", "outcomes", "player_table"}
    if args.include_unknown:
        relevant |= {"unknown"}
    candidates = [t for t in tables if t["rows"] and t["columns"] and t["purpose"] in relevant]
    skipped_purpose = [t for t in tables if t["purpose"] not in relevant and t["rows"]]
    dl.log(
        f"{len(candidates)} relevant tables to load; "
        f"skipping {len(skipped_purpose)} as unknown/irrelevant"
        + ("" if args.include_unknown else " (use --include-unknown to include them)")
    )

    max_rows_cfg = cfg.get("maxNormalizeRows", 2_000_000)
    max_rows_limit = args.max_rows or max_rows_cfg

    # Patterns for known play-by-play / snap-level tables we should not load.
    _PBP_NAMES = re.compile(r"(play.?by.?play|^pbp|_pbp|weekly|nextgen|tracking|participation|injuries|schedule)", re.I)

    def load_one(t: dict[str, Any]):
        """Load one table's DataFrame on demand, or None if skipped/unreadable.

        Tables are loaded one at a time and freed after use so peak memory stays
        bounded — holding all candidate frames in RAM at once OOMs on smaller
        machines (the old approach was killed by the OS on a 787-file dataset).
        """
        if max_rows_limit and t["rows"] > max_rows_limit:
            dl.log(f"  skip {t['name']} ({t['rows']:,} rows > row limit)")
            return None
        if _PBP_NAMES.search(t["name"]):
            dl.log(f"  skip {t['name']} (looks like PBP/tracking table)")
            return None
        # For duckdb tables the name is "file.duckdb::tablename"; extract the table part.
        tbl_name = t["name"].split("::", 1)[1] if (t["fmt"] == "duckdb" and "::" in t["name"]) else None
        try:
            df = read_table(t["source"], t["fmt"], pd, table_name=tbl_name)
        except Exception as exc:  # noqa: BLE001
            dl.log(f"  skip {t['name']}: {exc}")
            return None
        df.columns = [str(c).strip() for c in df.columns]
        return df

    cands_by_purpose: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in candidates:
        cands_by_purpose[t["purpose"]].append(t)

    # ----- build spine entities from draft tables (load → use → free) -----
    feature_names: set[str] = set()
    outcome_names: set[str] = set()
    entities: dict[str, dict[str, Any]] = {}
    norm_index: dict[tuple[str, str], list[str]] = defaultdict(list)  # (normName, posGroup) -> [playerId]
    name_index: dict[str, list[str]] = defaultdict(list)  # normName -> [playerId] (O(1) fallback)
    id_index: dict[tuple[str, str], str] = {}  # (idCol, idValue) -> playerId
    spine_keys: set[tuple[str, str]] = set()  # (source, name) of tables consumed as spine
    spine_names: list[str] = []

    for t in cands_by_purpose.get("draft", []):
        df = load_one(t)
        if df is None:
            continue
        roles = role_map(list(df.columns))
        if "pick" not in roles:
            del df  # draft-ish table without picks → treated as a feature source below
            continue
        spine_keys.add((t["source"], t["name"]))
        spine_names.append(t["name"])
        for rec in df.to_dict("records"):
            name = get_name(rec, roles)
            norm = dl.normalize_name(name)
            if not norm:
                continue
            season = to_num(rec.get(roles.get("season", "")))
            draft_class = int(season) if season else None
            # Only keep classes inside the configured window (drops e.g. pre-2014
            # draftees that bloat the spine). Future classes up to cls_hi allowed.
            if draft_class is None or not (cls_lo <= draft_class <= cls_hi):
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
                    "matched": {"_spine": t["name"]},
                },
            )
            norm_index[(norm, ent["positionGroup"])].append(pid)
            name_index[norm].append(pid)
            for role, col in roles.items():
                if role == "player_id":
                    val = rec.get(col)
                    if val not in (None, "", "nan"):
                        id_index[(col, str(val))] = pid
            # The draft (spine) table also carries canonical post-draft outcomes
            # (career AV, games, Pro Bowls). Capture them as LABELS only — never as
            # features — so nearly every player has a training target. These career
            # totals take precedence over season-level outcomes attached later.
            for col in df.columns:
                if dl.classify_outcome(col):
                    val = to_num(rec.get(col))
                    if val is not None:
                        low = str(col).strip().lower()
                        ent["outcomes"].setdefault(low, val)
                        outcome_names.add(low)
        del df
        gc.collect()

    if not spine_keys:
        dl.log("ERROR: no draft table with a pick column found — cannot build player spine.")
        dl.log("Inventory purposes seen: " + ", ".join(sorted(cands_by_purpose)))
        return 2

    per_class = defaultdict(int)
    for e in entities.values():
        per_class[e["draftClass"]] += 1
    dist = " ".join(f"{y}:{per_class[y]}" for y in sorted(per_class))
    dl.log(f"spine: {len(entities)} player entities  [{dist}]")

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
    unmatched: list[dict[str, Any]] = []

    id_cols = lambda roles: [c for r, c in roles.items() if r == "player_id"]  # noqa: E731

    def find_entity(rec: dict[str, Any], roles: dict[str, str], idcols: list[str]) -> tuple[str | None, str]:
        # 1) shared id (O(1))
        for col in idcols:
            val = rec.get(col)
            if val not in (None, "", "nan") and (col, str(val)) in id_index:
                return id_index[(col, str(val))], "id"
        name = get_name(rec, roles)
        norm = dl.normalize_name(name)
        if not norm:
            return None, ""
        pos = dl.normalize_position(rec.get(roles.get("position", "")))
        if (norm, pos) in overrides:
            return overrides[(norm, pos)], "override"
        # 2) name + position group, else name-only — both O(1) via prebuilt indexes
        cands = norm_index.get((norm, pos)) or name_index.get(norm) or []
        if not cands:
            return None, ""
        if len(cands) == 1:
            return cands[0], "name+pos"
        # disambiguate by school, then nearest draft class to season+1
        school = dl.normalize_name(rec.get(roles.get("school", ""), ""))
        season = to_num(rec.get(roles.get("season", "")))
        best, best_score = cands[0], -1e9
        for pid in cands:
            e = entities[pid]
            score = 0.0
            if school and dl.normalize_name(e["school"]) == school:
                score += 2
            if season and e["draftClass"]:
                score -= abs(e["draftClass"] - (int(season) + 1)) * 0.5
            if score > best_score:
                best, best_score = pid, score
        return best, "name+pos"

    def numeric_features(df, roles, prefix: str) -> list[tuple[str, str]]:
        skip = {roles[r] for r in NON_FEATURE_ROLES if r in roles} | {roles.get("age", ""), roles.get("pick", "")}
        feats = []
        for c in df.columns:
            if c in skip or c == "":
                continue
            # identity-ish or outcome columns are never features
            if dl.classify_column(c) or dl.classify_outcome(c):
                continue
            coerced = pd.to_numeric(df[c], errors="coerce")
            if len(coerced) and coerced.notna().mean() >= 0.5:
                feats.append((c, f"{prefix}_{c}"))
        return feats

    # Stream each non-spine table once, matching its rows to entities. We never
    # concatenate or materialize all rows at once (that OOMs). To fold a player's
    # multiple entries (e.g. one PFF file per season) into one record, we keep —
    # per feature — the value from the row whose season is closest to draftClass-1.
    # This is the online equivalent of "sort rows by season proximity, take the
    # first non-null". Accumulators are tiny (matched players × features), unlike
    # the source frames, so peak memory stays bounded to one file at a time.
    feat_acc: dict[str, dict[str, tuple[float, float]]] = defaultdict(dict)  # pid -> feat -> (dist, val)
    out_acc: dict[str, dict[str, tuple[float, float]]] = defaultdict(dict)   # pid -> outcome -> (dist, val)
    purpose_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # pid -> purpose -> rows

    UNMATCHED_CAP = 5000
    unmatched_count = 0
    match_summary: dict[str, dict[str, int]] = {}

    for purpose, metas in cands_by_purpose.items():
        prefix = re.sub(r"[^a-z0-9]+", "", purpose.lower()) or "src"
        methods: dict[str, int] = defaultdict(int)
        matched_players: set[str] = set()
        total_rows = 0
        n_files = 0
        for t in metas:
            if (t["source"], t["name"]) in spine_keys:
                continue  # already consumed as the spine
            df = load_one(t)
            if df is None:
                continue
            n_files += 1
            roles = role_map(list(df.columns))
            idcols = id_cols(roles)
            season_col = roles.get("season")
            is_outcome = purpose == "outcomes" or any(dl.classify_outcome(c) for c in df.columns)
            feat_cols = numeric_features(df, roles, prefix)
            outcome_cols = [(c, c.lower()) for c in df.columns if dl.classify_outcome(c)]
            for rec in df.to_dict("records"):
                total_rows += 1
                pid, method = find_entity(rec, roles, idcols)
                if pid is None:
                    unmatched_count += 1
                    if len(unmatched) < UNMATCHED_CAP:
                        unmatched.append(
                            {"purpose": purpose, "name": get_name(rec, roles), "position": str(rec.get(roles.get("position", ""), "") or "")}
                        )
                    continue
                methods[method] += 1
                matched_players.add(pid)
                purpose_counts[pid][purpose] += 1
                e = entities[pid]
                if season_col and e["draftClass"]:
                    s = to_num(rec.get(season_col))
                    tgt = e["draftClass"] - 1
                    dist_s = abs((s if s is not None else tgt) - tgt)
                else:
                    dist_s = 0.0
                fa = feat_acc[pid]
                for src_col, feat_name in feat_cols:
                    val = to_num(rec.get(src_col))
                    if val is None:
                        continue
                    prev = fa.get(feat_name)
                    if prev is None or dist_s < prev[0]:
                        fa[feat_name] = (dist_s, val)
                        feature_names.add(feat_name)
                if is_outcome:
                    oa = out_acc[pid]
                    for src_col, low in outcome_cols:
                        val = to_num(rec.get(src_col))
                        if val is None:
                            continue
                        prev = oa.get(low)
                        if prev is None or dist_s < prev[0]:
                            oa[low] = (dist_s, val)
                            outcome_names.add(low)
            del df
            gc.collect()
        if total_rows:
            match_summary[purpose] = {"matchedRows": sum(methods.values()), "players": len(matched_players), **methods}
            dl.log(f"matched '{purpose}': {total_rows:,} rows from {n_files} file(s) → {len(matched_players)} players")

    # Fold accumulated closest-season values into the entity records.
    for pid, fa in feat_acc.items():
        ef = entities[pid]["features"]
        for feat_name, (_, val) in fa.items():
            ef[feat_name] = val
    for pid, oa in out_acc.items():
        eo = entities[pid]["outcomes"]
        for low, (_, val) in oa.items():
            # Don't let a season-level value clobber a spine career total.
            eo.setdefault(low, val)
    for pid, pc in purpose_counts.items():
        em = entities[pid]["matched"]
        for purpose, cnt in pc.items():
            em[purpose] = "merged" if cnt > 1 else "matched"

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
        w = csv.DictWriter(fh, fieldnames=["purpose", "name", "position"])
        w.writeheader()
        w.writerows(unmatched)

    dl.write_json(
        dl.repo_path(out_dir, "normalize_diagnostics.json"),
        {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "spineEntities": len(players),
            "entitiesPerClass": {str(k): v for k, v in sorted(per_class.items())},
            "matchByPurpose": match_summary,
            "unmatchedRows": unmatched_count,
            "preDraftFeatureCount": len(all_feats),
            "outcomeFields": sorted(outcome_names),
        },
    )

    write_dictionary(cfg, players, all_feats, sorted(outcome_names))
    write_matching_strategy(cfg, players, spine_names, unmatched_count)

    dl.log(
        f"normalized {len(players)} players · {len(all_feats)} pre-draft features · "
        f"{len(outcome_names)} outcome fields · {unmatched_count} unmatched source rows"
    )
    dl.log("diagnostics → data/processed/normalize_diagnostics.json")
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


def write_matching_strategy(cfg, players, spine_names, unmatched_count: int) -> None:
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
        f"- Spine tables: {', '.join(spine_names)}",
        f"- Player entities: **{len(players)}**",
        f"- Unmatched source rows: **{unmatched_count}** (sampled in `unmatched_players.csv`)",
        "",
        "| Source purpose | Players matched |",
        "| --- | ---: |",
    ]
    for src, n in sorted(matched_counts.items()):
        lines.append(f"| {src} | {n} |")
    dl.write_text(dl.repo_path(cfg["docsDir"], "matching_strategy.md"), "\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
