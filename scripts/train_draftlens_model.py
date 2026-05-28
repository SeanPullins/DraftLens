#!/usr/bin/env python3
"""Train DraftLens, run walk-forward backtests, and score every player.

Honest by design:
  - The outcome target is auto-selected from whatever outcome labels exist
    (config `outcomePreference` order). If none exist, the model falls back to a
    transparent unsupervised composite and says so — it never invents labels.
  - Pre-draft features only. Outcome labels are used solely as targets/labels.
  - Validation is walk-forward by draft class (train older, test newer). We never
    randomly split across years. Tier hit/bust rates use out-of-sample folds.

Writes data/processed/model_output.json (consumed by export_frontend_data.py)
and docs/backtest_report.md.

Usage: python3 scripts/train_draftlens_model.py
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

import dl_common as dl

# --- component feature grouping (by name substring; direction-aware) ---
LOWER_IS_BETTER = ("forty", "shuttle", "cone", "3cone", "twp", "_age", "age_", "turnover", "drop")
COMPONENT_PATTERNS = {
    "production": ("college_", "production", "yards", "reception", "touchdown", "_td", "carries", "tackles", "sacks", "pressures"),
    "efficiency": ("grade", "yprr", "btt", "epa", "completion", "rate", "twp", "success"),
    "athletic": ("forty", "vertical", "broad", "bench", "shuttle", "cone", "speed", "burst", "explos", "ras"),
    "size": ("weight", "height", "_bmi", "arm", "wing", "hand"),
}
POSITION_VALUE = {"QB": 95, "EDGE": 88, "WR": 85, "CB": 84, "OL": 80, "DL": 78, "S": 72, "TE": 70, "LB": 68, "RB": 60}


def _flip(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in LOWER_IS_BETTER)


def pct_rank(values: np.ndarray) -> np.ndarray:
    """Percentile rank in [0,1], NaN-safe (NaNs -> 0.5)."""
    v = np.asarray(values, dtype=float)
    mask = ~np.isnan(v)
    out = np.full(v.shape, 0.5)
    if mask.sum() <= 1:
        return out
    order = v[mask].argsort().argsort()
    out[mask] = order / max(1, mask.sum() - 1)
    return out


def score_from_pct(p: np.ndarray) -> np.ndarray:
    return np.clip(np.round(1 + 98 * p), 1, 99)


def humanize(feature: str) -> str:
    label = re.sub(r"^(college|combine|pffgrades|pff|src)_", "", feature)
    return label.replace("_", " ").strip().capitalize()


def _load_from_gold(gold_csv: "Path", pd) -> "tuple[list[dict], list[str], list[str]] | None":
    """Load players, features, and outcome fields from the gold CSV.

    Returns (players, feature_cols, outcome_cols) in the same shape that
    players_features.json provides, or None on any error.
    """
    try:
        df = pd.read_csv(gold_csv, low_memory=False)
    except Exception as exc:
        dl.log(f"gold dataset unreadable ({exc}); falling back to silver")
        return None

    out_prefix = "outcome_"
    id_cols = {"player_id", "name", "position", "position_group", "school",
               "draft_class", "actual_pick", "actual_round", "actual_team", "age",
               "data_completeness"}
    feature_cols = [c for c in df.columns if c not in id_cols and not c.startswith(out_prefix)]
    outcome_raw = [c for c in df.columns if c.startswith(out_prefix)]
    outcome_fields = [c[len(out_prefix):] for c in outcome_raw]

    players = []
    for _, row in df.iterrows():
        features_d = {f: (None if str(row.get(f, "")) in ("nan", "") else float(row[f]))  # type: ignore[arg-type]
                      for f in feature_cols if row.get(f) is not None}
        features_d = {k: v for k, v in features_d.items() if v is not None}
        outcomes_d = {}
        for raw_col, field in zip(outcome_raw, outcome_fields):
            v = row.get(raw_col)
            if v is not None and str(v) not in ("nan", ""):
                try:
                    outcomes_d[field] = float(v)
                except (TypeError, ValueError):
                    pass
        players.append({
            "playerId": row.get("player_id"),
            "name": row.get("name") or "",
            "position": row.get("position") or "",
            "positionGroup": row.get("position_group") or "UNK",
            "school": row.get("school") or "",
            "draftClass": int(row["draft_class"]) if str(row.get("draft_class", "")) not in ("nan", "") else None,
            "actualPick": (None if str(row.get("actual_pick", "")) in ("nan", "") else int(float(row["actual_pick"]))),
            "actualRound": (None if str(row.get("actual_round", "")) in ("nan", "") else int(float(row["actual_round"]))),
            "actualTeam": row.get("actual_team") or None,
            "age": (None if str(row.get("age", "")) in ("nan", "") else float(row["age"])),
            "dataCompleteness": float(row.get("data_completeness") or 0),
            "features": features_d,
            "outcomes": outcomes_d,
            "matched": {},
        })
    dl.log(f"loaded {len(players)} players from gold dataset {gold_csv.name}")
    return players, feature_cols, outcome_fields


def main() -> int:
    cfg = dl.load_config()
    proc = cfg["processedDir"]
    gold_dir = cfg.get("goldDir", "data/gold")
    gold_csv = dl.repo_path(gold_dir, "draftlens_training_dataset.csv")

    # Prefer gold layer (one tidy CSV); fall back to silver players_features.json.
    players_path = dl.repo_path(proc, "players_features.json")
    fm_path = dl.repo_path(proc, "feature_manifest.json")

    players: list[dict]
    features: list[str]
    outcome_fields: list[str]

    if gold_csv.exists():
        try:
            import pandas as pd  # type: ignore
        except ImportError:
            pd = None  # type: ignore

        gold_result = _load_from_gold(gold_csv, pd) if pd else None
        if gold_result:
            players, features, outcome_fields = gold_result
        else:
            # fall through to silver
            gold_result = None

        if gold_result is None:
            if not players_path.exists() or not fm_path.exists():
                dl.log("ERROR: run `npm run data:normalize` first (missing players_features/feature_manifest).")
                return 2
            players = json.loads(players_path.read_text())
            fm = json.loads(fm_path.read_text())
            features = fm["preDraftFeatures"]
            outcome_fields = fm["outcomeFields"]
    else:
        if not players_path.exists() or not fm_path.exists():
            dl.log("ERROR: run `npm run data:normalize` first (missing players_features/feature_manifest).")
            return 2
        players = json.loads(players_path.read_text())
        fm = json.loads(fm_path.read_text())
        features = fm["preDraftFeatures"]
        outcome_fields = fm["outcomeFields"]

    if not players:
        dl.log("ERROR: no players to score.")
        return 2

    # ---- select outcome target ----
    target = None
    for pref in cfg["outcomePreference"]:
        pat = re.compile(pref.replace("_", ".?"))
        for f in outcome_fields:
            if pat.search(f):
                target = f
                break
        if target:
            break
    if target is None and outcome_fields:
        target = outcome_fields[0]

    n = len(players)
    groups = np.array([p["positionGroup"] for p in players])
    classes = np.array([p["draftClass"] or 0 for p in players])

    # feature matrix with median imputation (medians from players that have the value)
    X = np.full((n, len(features)), np.nan)
    for j, f in enumerate(features):
        col = np.array([p["features"].get(f, np.nan) for p in players], dtype=float)
        X[:, j] = -col if _flip(f) else col
    medians = np.nanmedian(np.where(np.isnan(X), np.nan, X), axis=0)
    medians = np.where(np.isnan(medians), 0.0, medians)
    Xf = np.where(np.isnan(X), medians, X)
    mu, sd = Xf.mean(axis=0), Xf.std(axis=0)
    sd = np.where(sd == 0, 1.0, sd)
    Xs = (Xf - mu) / sd

    has_outcome = np.array([target is not None and target in p["outcomes"] for p in players])
    y = np.array([p["outcomes"].get(target, np.nan) if target else np.nan for p in players], dtype=float)

    warnings: list[str] = []
    backtest = {
        "dataReady": False,
        "overallCorrelation": None,
        "validationScheme": "not run",
        "byTier": [],
        "byPosition": [],
        "byRound": [],
        "byClass": [],
        "topHits": [],
        "topMisses": [],
        "notes": "",
    }

    supervised = target is not None and has_outcome.sum() >= 30
    coef = np.zeros(len(features))
    oos_pred = np.full(n, np.nan)
    final_pred = np.full(n, np.nan)
    bust_prob = np.full(n, np.nan)

    if supervised:
        from sklearn.linear_model import Ridge, LogisticRegression

        hist_years = sorted({int(c) for c, h in zip(classes, has_outcome) if h})
        # ---- walk-forward validation ----
        per_year_corr: dict[int, float] = {}
        if len(hist_years) >= 3:
            for ti in range(2, len(hist_years)):
                test_year = hist_years[ti]
                train_mask = has_outcome & (classes < test_year)
                test_mask = has_outcome & (classes == test_year)
                if train_mask.sum() < 20 or test_mask.sum() < 3:
                    continue
                m = Ridge(alpha=5.0).fit(Xs[train_mask], y[train_mask])
                pred = m.predict(Xs[test_mask])
                oos_pred[test_mask] = pred
                if test_mask.sum() >= 3 and np.std(pred) > 0:
                    per_year_corr[test_year] = float(np.corrcoef(pred, y[test_mask])[0, 1])
            backtest["validationScheme"] = (
                f"walk-forward {hist_years[2]}–{hist_years[-1]} (train older classes, test next)"
            )
        else:
            warnings.append("Too few historical classes for walk-forward; reporting in-sample only.")
            backtest["validationScheme"] = "in-sample (insufficient classes for walk-forward)"

        # ---- final production model on all historical ----
        ridge = Ridge(alpha=5.0).fit(Xs[has_outcome], y[has_outcome])
        coef = ridge.coef_
        final_pred = ridge.predict(Xs)

        # ---- bust classifier ----
        bust_thresh = np.nanquantile(y[has_outcome], cfg["bustThresholdPercentile"])
        hit_thresh = np.nanquantile(y[has_outcome], cfg["hitThresholdPercentile"])
        bust_label = (y[has_outcome] <= bust_thresh).astype(int)
        if bust_label.sum() >= 5 and bust_label.sum() < has_outcome.sum():
            clf = LogisticRegression(max_iter=1000).fit(Xs[has_outcome], bust_label)
            bust_prob = clf.predict_proba(Xs)[:, 1]
        else:
            bust_prob = 1 - pct_rank(final_pred)

        backtest["dataReady"] = True
        backtest["overallCorrelation"] = (
            round(float(np.nanmean(list(per_year_corr.values()))), 3) if per_year_corr else None
        )
    else:
        if target is None:
            warnings.append("No outcome labels found — using a transparent unsupervised composite score.")
        else:
            warnings.append(f"Only {int(has_outcome.sum())} labeled players for '{target}' (<30) — composite fallback.")
        backtest["notes"] = "Backtest unavailable without sufficient labeled outcomes."

    # ---- component sub-scores (percentile within position group, direction-aware) ----
    def component(group_feats: list[str]) -> np.ndarray:
        cols = [features.index(f) for f in group_feats if f in features]
        if not cols:
            return np.full(n, np.nan)
        comp = np.full(n, np.nan)
        for g in set(groups):
            gm = groups == g
            sub = Xs[np.ix_(gm, cols)].mean(axis=1)  # already direction-corrected + standardized
            comp[gm] = score_from_pct(pct_rank(sub))
        return comp

    feat_for = {k: [f for f in features if any(s in f.lower() for s in subs)] for k, subs in COMPONENT_PATTERNS.items()}
    comp_scores = {k: component(v) for k, v in feat_for.items()}
    # age (younger better) and draft capital
    ages = np.array([p["age"] if p["age"] else np.nan for p in players], dtype=float)
    comp_scores["age"] = score_from_pct(pct_rank(-ages))
    dc = np.array([p["features"].get("draft_capital", np.nan) for p in players], dtype=float)
    comp_scores["draftCapital"] = score_from_pct(pct_rank(dc))
    comp_scores["positionValue"] = np.array([POSITION_VALUE.get(g, 65) for g in groups], dtype=float)

    # ---- final DraftLens score ----
    if supervised:
        base_pct = pct_rank(final_pred)
    else:
        # transparent weighted composite of available components
        weights = {"production": 0.25, "efficiency": 0.25, "athletic": 0.15, "size": 0.05, "age": 0.1, "draftCapital": 0.2}
        acc = np.zeros(n)
        wsum = np.zeros(n)
        for k, w in weights.items():
            c = comp_scores.get(k)
            if c is None:
                continue
            valid = ~np.isnan(c)
            acc[valid] += w * c[valid]
            wsum[valid] += w
        composite = np.where(wsum > 0, acc / np.where(wsum == 0, 1, wsum), 50)
        base_pct = pct_rank(composite)
    score = score_from_pct(base_pct).astype(int)

    if np.all(np.isnan(bust_prob)):
        bust_prob = 1 - base_pct

    # upside: blend predicted/composite tail with athletic+efficiency
    ath = np.nan_to_num(comp_scores["athletic"], nan=50.0)
    eff = np.nan_to_num(comp_scores["efficiency"], nan=50.0)
    upside = score_from_pct(pct_rank(0.6 * base_pct * 100 + 0.25 * ath + 0.15 * eff)).astype(int)

    # confidence from data completeness
    completeness = np.array([p["dataCompleteness"] for p in players])
    confidence = np.clip(0.3 + 0.6 * completeness, 0.1, 0.95)

    # value vs pick: residual of score against expected score at that pick
    picks = np.array([p["actualPick"] if p["actualPick"] else np.nan for p in players], dtype=float)
    value_vs_pick = np.full(n, np.nan)
    pm = ~np.isnan(picks)
    if pm.sum() >= 10:
        z = np.polyfit(np.log(picks[pm]), score[pm], 1)
        expected = np.polyval(z, np.log(picks[pm]))
        value_vs_pick[pm] = np.round(score[pm] - expected, 1)

    # tiers
    def tier_of(s: int) -> str:
        return "Elite" if s >= 85 else "High" if s >= 75 else "Solid" if s >= 60 else "Developmental" if s >= 45 else "Risk"

    # ranks
    order_overall = (-score).argsort()
    overall_rank = np.empty(n, dtype=int)
    overall_rank[order_overall] = np.arange(1, n + 1)
    pos_rank = np.zeros(n, dtype=int)
    for g in set(groups):
        gm = np.where(groups == g)[0]
        gi = gm[(-score[gm]).argsort()]
        for r, idx in enumerate(gi, 1):
            pos_rank[idx] = r

    # comps: nearest within position group on standardized features
    def comps_for(i: int) -> list[dict]:
        g = groups[i]
        gm = np.where((groups == g) & (np.arange(n) != i))[0]
        if len(gm) == 0:
            return []
        d = np.linalg.norm(Xs[gm] - Xs[i], axis=1)
        nn = gm[d.argsort()[:3]]
        sims = np.exp(-d[d.argsort()[:3]] / (np.median(d) + 1e-6))
        res = []
        for idx, sim in zip(nn, sims):
            res.append(
                {
                    "name": players[idx]["name"],
                    "playerId": players[idx]["playerId"],
                    "similarity": round(float(min(0.99, max(0.3, sim))), 2),
                    "outcome": _outcome_label(players[idx], target),
                }
            )
        return res

    # projected outcome label from predicted value or composite percentile
    def projected(i: int) -> tuple[str, float | None]:
        p = base_pct[i]
        label = (
            "Franchise-caliber" if p >= 0.92 else
            "Perennial starter" if p >= 0.8 else
            "Multi-year starter" if p >= 0.62 else
            "Rotational contributor" if p >= 0.42 else
            "Depth / developmental" if p >= 0.22 else
            "Longshot"
        )
        val = round(float(final_pred[i]), 1) if supervised and not np.isnan(final_pred[i]) else None
        return label, val

    records = []
    for i, p in enumerate(players):
        s = int(score[i])
        comps_obj = {k: (round(float(v[i]), 0) if not np.isnan(v[i]) else None) for k, v in comp_scores.items()}
        comps_obj["risk"] = round(float(100 * bust_prob[i]), 0)
        comps_obj["upside"] = float(upside[i])
        comps_obj["confidence"] = round(float(100 * confidence[i]), 0)
        drivers = build_drivers(Xs[i], coef, features) if supervised else build_composite_drivers(comps_obj)
        strengths, red = build_notes(comps_obj, p, float(bust_prob[i]))
        proj_label, proj_val = projected(i)
        is_future = not has_outcome[i] and (p["actualPick"] is None)
        rec = {
            "playerId": p["playerId"],
            "name": p["name"],
            "position": p["position"] or p["positionGroup"],
            "positionGroup": p["positionGroup"],
            "school": p["school"],
            "draftClass": p["draftClass"],
            "actualPick": p["actualPick"],
            "actualTeam": p["actualTeam"],
            "projectedPick": None,
            "draftLensScore": s,
            "positionRank": int(pos_rank[i]),
            "overallRank": int(overall_rank[i]),
            "tier": tier_of(s),
            "confidence": round(float(confidence[i]), 3),
            "projectedOutcome": proj_label,
            "projectedValue": proj_val,
            "bustRisk": round(float(bust_prob[i]), 3),
            "upsideScore": int(upside[i]),
            "valueVsPick": (None if np.isnan(value_vs_pick[i]) else float(value_vs_pick[i])),
            "modelVersion": cfg["modelVersion"],
            "scoreComponents": comps_obj,
            "drivers": drivers,
            "flags": build_flags(p, s, float(bust_prob[i]), value_vs_pick[i]),
            "comps": comps_for(i),
            "strengths": strengths,
            "redFlags": red,
            "explanation": build_explanation(p, s, proj_label, supervised, target),
            "dataCompleteness": p["dataCompleteness"],
            "realizedOutcome": _outcome_label(p, target) if has_outcome[i] else None,
            "realizedValue": (round(float(y[i]), 1) if has_outcome[i] else None),
            "_isFuture": bool(is_future),
        }
        records.append(rec)

    # ---- backtest aggregates on OOS predictions ----
    if supervised and not np.all(np.isnan(oos_pred)):
        backtest.update(build_backtest(players, records, oos_pred, y, has_outcome, classes, cfg))

    positions_summary = build_positions(records, features, "ridge" if supervised else "composite")

    model_output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "modelVersion": cfg["modelVersion"],
        "outcomeTarget": target,
        "outcomeUnits": target,
        "supervised": supervised,
        "featuresUsed": features,
        "players": records,
        "backtest": backtest,
        "positions": positions_summary,
        "warnings": warnings,
    }
    dl.write_json(dl.repo_path(proc, "model_output.json"), model_output)
    write_backtest_report(cfg, model_output)

    dl.log(
        f"scored {n} players · target={target or 'composite'} · "
        f"{'walk-forward backtest' if backtest['dataReady'] else 'no backtest'} · "
        f"overall corr={backtest['overallCorrelation']}"
    )
    for w in warnings:
        dl.log("warning: " + w)
    return 0


def _outcome_label(player: dict, target: str | None) -> str | None:
    if not target or target not in player["outcomes"]:
        return None
    v = player["outcomes"][target]
    return f"{target.replace('_', ' ')}: {round(v, 1)}"


def build_drivers(xrow, coef, features) -> list[dict]:
    contrib = xrow * coef
    idx = np.argsort(-np.abs(contrib))[:4]
    scale = (np.max(np.abs(contrib)) or 1.0)
    return [
        {"label": humanize(features[j]), "contribution": round(float(10 * contrib[j] / scale), 1)}
        for j in idx
        if abs(contrib[j]) > 1e-6
    ]


def build_composite_drivers(comps: dict) -> list[dict]:
    items = [(k, v) for k, v in comps.items() if v is not None and k not in ("risk", "confidence")]
    items.sort(key=lambda kv: -abs(kv[1] - 50))
    return [{"label": k.capitalize(), "contribution": round((v - 50) / 5, 1)} for k, v in items[:4]]


def build_notes(comps: dict, player: dict, bust: float):
    labels = {"production": "production", "efficiency": "efficiency", "athletic": "athleticism", "size": "size", "draftCapital": "draft capital"}
    strengths, red = [], []
    for k, lab in labels.items():
        v = comps.get(k)
        if v is None:
            continue
        if v >= 72:
            strengths.append(f"Strong {lab}")
        elif v <= 38:
            red.append(f"Below-average {lab}")
    if player["age"] and player["age"] >= 23.5:
        red.append("Older prospect")
    if bust >= 0.5:
        red.append("Elevated bust risk")
    if player["dataCompleteness"] < 0.5:
        red.append("Limited data coverage")
    return strengths[:4], red[:4]


def build_flags(player, score, bust, vvp) -> list[dict]:
    flags = []
    if not np.isnan(vvp) and vvp >= 8:
        flags.append({"kind": "gem", "label": "Gem", "note": "Scores well above draft slot"})
    elif not np.isnan(vvp) and vvp >= 3:
        flags.append({"kind": "value", "label": "Value", "note": "Better than draft slot"})
    if bust >= 0.55:
        flags.append({"kind": "bust", "label": "Bust risk", "note": "High modeled bust probability"})
    if player["age"] and player["age"] >= 23.5:
        flags.append({"kind": "age", "label": "Age", "note": "Older entering the league"})
    if player["dataCompleteness"] < 0.5:
        flags.append({"kind": "data", "label": "Thin data", "note": "Incomplete feature coverage"})
    return flags


def build_explanation(player, score, proj, supervised, target) -> str:
    method = (
        f"trained to predict {target.replace('_', ' ')}" if supervised and target else "a transparent component composite"
    )
    return (
        f"DraftLens scores {player['name']} {score}/99 ({proj.lower()}). "
        f"The score comes from {method} using only pre-draft information."
    )


def build_backtest(players, records, oos_pred, y, has_outcome, classes, cfg) -> dict:
    mask = has_outcome & ~np.isnan(oos_pred)
    if mask.sum() < 5:
        return {}
    hit_thresh = float(np.nanquantile(y[has_outcome], cfg["hitThresholdPercentile"]))
    bust_thresh = float(np.nanquantile(y[has_outcome], cfg["bustThresholdPercentile"]))

    # OOS score from oos prediction percentile (within OOS set)
    oos_score = score_from_pct(pct_rank(np.where(mask, oos_pred, np.nan)))

    def tier_of(s):
        return "Elite" if s >= 85 else "High" if s >= 75 else "Solid" if s >= 60 else "Developmental" if s >= 45 else "Risk"

    by_tier = defaultdict(lambda: {"n": 0, "hit": 0, "bust": 0, "vals": []})
    idxs = np.where(mask)[0]
    for i in idxs:
        t = tier_of(int(oos_score[i]))
        d = by_tier[t]
        d["n"] += 1
        d["hit"] += int(y[i] >= hit_thresh)
        d["bust"] += int(y[i] <= bust_thresh)
        d["vals"].append(float(y[i]))
    tier_rows = []
    for t in ["Elite", "High", "Solid", "Developmental", "Risk"]:
        if t in by_tier:
            d = by_tier[t]
            tier_rows.append({
                "tier": t, "count": d["n"],
                "hitRate": round(d["hit"] / d["n"], 3),
                "bustRate": round(d["bust"] / d["n"], 3),
                "avgRealizedValue": round(sum(d["vals"]) / d["n"], 2),
            })

    def group_stats(key_fn):
        g = defaultdict(lambda: {"pred": [], "real": [], "hit": 0})
        for i in idxs:
            k = key_fn(i)
            if k is None:
                continue
            g[k]["pred"].append(float(oos_pred[i]))
            g[k]["real"].append(float(y[i]))
            g[k]["hit"] += int(y[i] >= hit_thresh)
        rows = []
        for k, d in g.items():
            corr = (float(np.corrcoef(d["pred"], d["real"])[0, 1]) if len(d["pred"]) >= 3 and np.std(d["pred"]) > 0 else None)
            rows.append({"key": str(k), "count": len(d["pred"]),
                         "correlation": (round(corr, 3) if corr is not None else None),
                         "hitRate": round(d["hit"] / len(d["pred"]), 3)})
        return sorted(rows, key=lambda r: r["key"])

    def round_bucket(i):
        pk = players[i]["actualPick"]
        if not pk:
            return None
        return "R1 (1-32)" if pk <= 32 else "R2-3 (33-100)" if pk <= 100 else "R4-7 (101+)"

    # top hits / misses by signed residual of realized vs predicted
    resid = np.full(len(players), np.nan)
    pr = pct_rank(np.where(mask, oos_pred, np.nan))
    yr = pct_rank(np.where(mask, y, np.nan))
    resid[mask] = yr[mask] - pr[mask]
    hit_idx = np.argsort(-np.where(mask, np.minimum(pr, yr), -1))[:8]  # high pred AND high real
    miss_idx = np.argsort(-np.where(mask, np.abs(resid), -1))[:8]

    def call(i, note):
        r = records[i]
        return {"playerId": r["playerId"], "name": r["name"], "draftClass": r["draftClass"],
                "position": r["position"], "draftLensScore": int(oos_score[i]),
                "actualPick": r["actualPick"], "realizedOutcome": r["realizedOutcome"], "note": note}

    return {
        "byTier": tier_rows,
        "byPosition": group_stats(lambda i: players[i]["positionGroup"]),
        "byRound": group_stats(round_bucket),
        "byClass": group_stats(lambda i: int(classes[i]) if classes[i] else None),
        "topHits": [call(i, "Correctly ranked high; produced") for i in hit_idx if mask[i]][:8],
        "topMisses": [call(i, "Largest prediction error") for i in miss_idx if mask[i]][:8],
        "notes": f"Out-of-sample walk-forward folds. hit≥{round(hit_thresh,1)}, bust≤{round(bust_thresh,1)} ({cfg['outcomePreference'][0]} units of selected target).",
    }


def build_positions(records, features, model_type) -> list[dict]:
    by_group = defaultdict(list)
    for r in records:
        by_group[r["positionGroup"]].append(r)
    _ = features
    out = []
    for g, recs in sorted(by_group.items()):
        # surface the model drivers most often cited for this position group
        present: dict[str, int] = defaultdict(int)
        for r in recs:
            for d in r["drivers"]:
                present[d["label"]] += 1
        used = [lbl for lbl, _c in sorted(present.items(), key=lambda kv: -kv[1])[:8]]
        top = [r["playerId"] for r in sorted(recs, key=lambda x: -x["draftLensScore"])[:10]]
        out.append({"positionGroup": g, "playerCount": len(recs), "featuresUsed": used, "topPlayerIds": top, "modelType": model_type})
    return out


def write_backtest_report(cfg, mo) -> None:
    b = mo["backtest"]
    lines = [
        "# DraftLens Backtest Report",
        "",
        f"_Generated {mo['generatedAt']} · model v{mo['modelVersion']}_",
        "",
        f"- Outcome target: **{mo['outcomeTarget'] or 'none (composite fallback)'}**",
        f"- Validation: {b['validationScheme']}",
        f"- Overall out-of-sample correlation: **{b['overallCorrelation']}**",
        "",
    ]
    if mo["warnings"]:
        lines.append("## Warnings\n")
        lines += [f"- {w}" for w in mo["warnings"]] + [""]
    if b["dataReady"]:
        lines.append("## Hit / bust rate by tier\n")
        lines.append("| Tier | n | Hit rate | Bust rate | Avg value |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for r in b["byTier"]:
            lines.append(f"| {r['tier']} | {r['count']} | {r['hitRate']:.0%} | {r['bustRate']:.0%} | {r['avgRealizedValue']} |")
        lines.append("\n## Accuracy by position\n")
        lines.append("| Position | n | Corr | Hit rate |\n| --- | ---: | ---: | ---: |")
        for r in b["byPosition"]:
            lines.append(f"| {r['key']} | {r['count']} | {r['correlation']} | {r['hitRate']:.0%} |")
        lines.append("\n## Accuracy by class\n")
        lines.append("| Class | n | Corr | Hit rate |\n| --- | ---: | ---: | ---: |")
        for r in b["byClass"]:
            lines.append(f"| {r['key']} | {r['count']} | {r['correlation']} | {r['hitRate']:.0%} |")
        lines.append("")
        lines.append("_Honesty note: these are out-of-sample walk-forward results. Treat correlations")
        lines.append("as directional, not precise, especially for small position/class cells._")
    else:
        lines.append("_No backtest: insufficient labeled outcomes. Scores use a transparent composite._")
    dl.write_text(dl.repo_path(cfg["docsDir"], "backtest_report.md"), "\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
