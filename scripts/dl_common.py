"""Shared helpers for the DraftLens local pipeline.

Everything here is schema-agnostic: we never assume a specific column exists.
Instead we classify columns by name patterns and report what we actually find.
The pipeline is strictly read-only with respect to the source data directory.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "pipeline.config.json"


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def load_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve_data_dir(cli_value: str | None = None) -> Path:
    """Resolve the source data directory. Precedence: CLI > env > config."""
    cfg = load_config()
    raw = cli_value or os.environ.get("DRAFTLENS_DATA_DIR") or cfg.get("dataDir", "")
    return Path(os.path.expanduser(raw)).resolve()


def repo_path(*parts: str) -> Path:
    return REPO_ROOT.joinpath(*parts)


# --------------------------------------------------------------------------- #
# Name / position normalization
# --------------------------------------------------------------------------- #
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize_name(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [t for t in text.split() if t and t not in _SUFFIXES]
    return " ".join(tokens)


# Map a raw position label onto a DraftLens position group.
_POSITION_GROUPS: list[tuple[str, set[str]]] = [
    ("QB", {"qb"}),
    ("RB", {"rb", "hb", "fb", "tb"}),
    ("WR", {"wr"}),
    ("TE", {"te"}),
    ("OL", {"ol", "ot", "og", "c", "g", "t", "iol", "lt", "rt", "lg", "rg"}),
    ("EDGE", {"edge", "de", "olb"}),
    ("DL", {"dl", "dt", "nt", "idl", "di"}),
    ("LB", {"lb", "ilb", "mlb"}),
    ("CB", {"cb", "db"}),
    ("S", {"s", "fs", "ss", "saf"}),
]
_POSITION_LOOKUP = {alias: group for group, aliases in _POSITION_GROUPS for alias in aliases}


def normalize_position(value: Any) -> str:
    if value is None:
        return ""
    raw = re.sub(r"[^a-z]", "", str(value).strip().lower())
    if not raw:
        return ""
    return _POSITION_LOOKUP.get(raw, str(value).strip().upper())


# --------------------------------------------------------------------------- #
# Column classification (pattern-based, never positional)
# --------------------------------------------------------------------------- #
COLUMN_ROLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("player_id", re.compile(r"(^|_)(gsis|pfr|pff|espn|sportradar|nfl|sleeper|player|cfb|rotowire)?_?id$")),
    ("first_name", re.compile(r"^(first|first_name|firstname|fname)$")),
    ("last_name", re.compile(r"^(last|last_name|lastname|lname)$")),
    ("name", re.compile(r"(full_?name|player_?name|display_?name|^name$|^player$|^pfr_player_name$)")),
    ("position", re.compile(r"^(pos|position|pos_group|position_group|fantasy_pos)$")),
    ("team", re.compile(r"^(team|tm|recent_team|nfl_team|franchise|club|posteam)$")),
    ("school", re.compile(r"^(school|college|college_team|college_name|cfb_team)$")),
    ("season", re.compile(r"^(season|year|draft_year|class|draft_class|season_year)$")),
    ("pick", re.compile(r"(^pick$|overall|draft_pick|pick_overall|selection|^ovr$)")),
    ("round", re.compile(r"^(round|rnd|draft_round)$")),
    ("age", re.compile(r"^(age|draft_age|age_at_draft)$")),
]

# Outcome / post-draft fields — used ONLY as labels, never as features.
OUTCOME_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("approximate_value", re.compile(r"(weighted_av|^wav$|career_av|drafted_av|^av$|approximate_value|^av_|_av$)")),
    ("starts", re.compile(r"(games_started|^starts$|career_starts|^gs$)")),
    ("games", re.compile(r"(games_played|^games$|^g$|^gp$)")),
    ("snaps", re.compile(r"(snaps|snap_share|offense_snaps|defense_snaps)")),
    ("honors", re.compile(r"(pro_?bowl|all_?pro|probowls|allpros|accolades)")),
]


def classify_column(col: str) -> str | None:
    key = str(col).strip().lower()
    for role, pat in COLUMN_ROLE_PATTERNS:
        if pat.search(key):
            return role
    return None


def classify_outcome(col: str) -> str | None:
    key = str(col).strip().lower()
    for role, pat in OUTCOME_PATTERNS:
        if pat.search(key):
            return role
    return None


# Heuristic purpose guess for a file based on name + columns present.
def infer_purpose(filename: str, columns: Iterable[str]) -> str:
    fn = filename.lower()
    cols = {str(c).lower() for c in columns}
    roles = {classify_column(c) for c in columns}
    has = lambda r: r in roles  # noqa: E731

    if any(k in fn for k in ("combine", "athletic", "testing")) or {"forty", "vertical", "broad", "shuttle"} & cols:
        return "combine"
    if any(k in fn for k in ("draft", "picks")) and (has("pick") or has("round")):
        return "draft"
    if "pff" in fn or any("grade" in c for c in cols):
        return "pff_grades"
    if any(k in fn for k in ("college", "cfb", "ncaa")):
        return "college"
    if any(classify_outcome(c) for c in columns):
        return "outcomes"
    if has("pick") or has("round"):
        return "draft"
    if has("name") or has("player_id"):
        return "player_table"
    return "unknown"


# --------------------------------------------------------------------------- #
# IO
# --------------------------------------------------------------------------- #
def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False, default=_json_default)
        fh.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _json_default(obj: Any) -> Any:
    # Tolerate numpy / pandas scalar types without importing them at module load.
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:  # pragma: no cover
            pass
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def log(msg: str) -> None:
    print(f"[draftlens] {msg}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# File discovery
# --------------------------------------------------------------------------- #
@dataclass
class SourceFile:
    path: Path
    ext: str
    size_bytes: int


def discover_files(data_dir: Path, exts: Iterable[str]) -> list[SourceFile]:
    wanted = {e.lower().lstrip(".") for e in exts}
    found: list[SourceFile] = []
    if not data_dir.exists():
        return found
    for p in sorted(data_dir.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower().lstrip(".")
        if ext in wanted:
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            found.append(SourceFile(path=p, ext=ext, size_bytes=size))
    return found


@dataclass
class TableProfile:
    """Profiling result for a single table (file or duckdb table)."""

    name: str
    source: str
    fmt: str
    rows: int
    columns: list[str]
    dtypes: dict[str, str] = field(default_factory=dict)
    sample_columns: list[str] = field(default_factory=list)
    purpose: str = "unknown"
    join_keys: list[str] = field(default_factory=list)
    outcome_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
