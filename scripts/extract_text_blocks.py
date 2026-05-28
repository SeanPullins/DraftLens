#!/usr/bin/env python3
"""Extract candidate player blocks from unstructured text files.

Scans .txt, .md, .log, and .html files in the data directory. Splits each file
into blank-line-separated blocks, applies conservative heuristics to identify
blocks that likely describe a draft prospect, and writes them to:

  data/bronze/raw_player_blocks.jsonl   (one JSON object per candidate block)

Each output record:
  {
    "source":     relative path from data_dir,
    "blockIndex": integer index within the file,
    "year":       inferred draft year (int) or null,
    "position":   inferred position string or null,
    "confidence": "low" | "medium" | "high",
    "text":       raw block text (stripped)
  }

Heuristics (conservative — false positives are harmless, false negatives waste data):
  - A block qualifies if it contains what looks like a player name (two+ capitalized words
    on the same line, not pure stopwords) AND at least one of: a position token, a school
    name keyword, a draft-style number (round/pick), or a measurable (height/weight pattern).
  - Year is inferred from the filename (4-digit year) or a "YYYY draft" phrase in the block.
  - Position is inferred from known position tokens found in the block.
  - Confidence is "high" if ≥3 signals present, "medium" if 2, "low" if 1.

Usage:
  python3 scripts/extract_text_blocks.py [--data-dir PATH] [--output PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import dl_common as dl

# --------------------------------------------------------------------------- #
# Pattern library
# --------------------------------------------------------------------------- #

_YEAR_RE = re.compile(r"\b(20[1-3]\d)\b")
_DRAFT_YEAR_RE = re.compile(r"\b(20[1-3]\d)\s+draft\b", re.I)

_POSITION_TOKENS = {
    "QB", "RB", "FB", "WR", "TE", "OL", "OT", "OG", "C",
    "DE", "DT", "NT", "LB", "ILB", "OLB", "MLB",
    "CB", "DB", "S", "FS", "SS", "EDGE", "DL", "IOL",
}
_POS_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in _POSITION_TOKENS) + r")\b"
)

# Two or more capitalized words (name-like), not all stopwords.
_NAME_RE = re.compile(r"\b([A-Z][a-z]{1,}(?:\s+[A-Z][a-z]{1,})+)\b")

_STOPWORDS = {
    "The", "His", "Her", "But", "And", "For", "With", "From", "That", "This",
    "They", "Their", "Which", "When", "Where", "What", "Who", "How",
    "All", "Not", "Can", "Will", "May", "Has", "Had", "Was", "Were",
    "Are", "Been", "Being", "Have", "More", "Most", "Such", "Also",
    "Into", "Over", "After", "Before", "During", "Both", "Each", "Few",
    "Very", "Just", "Even", "Only", "Than", "Then", "Thus", "Well",
    "New", "Last", "First", "Second", "Third", "One", "Two", "Three",
    "Round", "Pick", "Draft", "Class", "Season", "Year",
    "College", "University", "School", "National", "American",
    "Pro", "Bowl", "Super", "Conference", "Division",
}

# Measurables / combine-style tokens
_MEASURABLE_RE = re.compile(
    r"\b(\d{1,3}(?:\.\d+)?\s*(?:lbs?|pounds?|inches?|in\b|mph|mph|s\b)|\d'\d{1,2}"
    r"|40\s*(?:yard|yd)|\d\.\d{2}\s*(?:sec|s\b)|vertical|broad jump|shuttle|cone|bench|rep)\b",
    re.I,
)

# Round/pick style numbers
_PICK_RE = re.compile(r"\b(round\s*\d|pick\s*\d{1,3}|\d(?:st|nd|rd|th)\s+round)\b", re.I)

# School keywords — common football program indicators
_SCHOOL_RE = re.compile(
    r"\b(alabama|georgia|ohio\s*state|michigan|clemson|lsu|oklahoma|notre\s*dame"
    r"|florida|penn\s*state|texas|tennessee|auburn|oregon|washington|iowa"
    r"|miami|nebraska|arkansas|baylor|tcu|usc|utah|kentucky|mississippi"
    r"|stanford|northwestern|wisconsin|illinois|purdue|indiana|minnesota"
    r"|colorado|arizona|california|louisville|virginia|pittsburgh|nc\s*state)\b",
    re.I,
)


def _infer_year_from_filename(path: Path) -> int | None:
    m = _YEAR_RE.search(path.stem)
    return int(m.group(1)) if m else None


def _infer_year_from_block(text: str) -> int | None:
    m = _DRAFT_YEAR_RE.search(text)
    if m:
        return int(m.group(1))
    years = _YEAR_RE.findall(text)
    if len(years) == 1:
        return int(years[0])
    if years:
        # take the most common year
        from collections import Counter
        return int(Counter(years).most_common(1)[0][0])
    return None


def _infer_position(text: str) -> str | None:
    m = _POS_RE.search(text.upper())
    return m.group(1) if m else None


def _has_player_name(text: str) -> bool:
    for m in _NAME_RE.finditer(text):
        words = m.group(1).split()
        if not all(w in _STOPWORDS for w in words):
            return True
    return False


def _score_block(text: str) -> int:
    """Return a 0-4 signal count for this block."""
    score = 0
    if _has_player_name(text):
        score += 1
    if _POS_RE.search(text.upper()):
        score += 1
    if _SCHOOL_RE.search(text):
        score += 1
    if _MEASURABLE_RE.search(text):
        score += 1
    if _PICK_RE.search(text):
        score += 1
    return score


def _confidence(signal_count: int) -> str:
    if signal_count >= 3:
        return "high"
    if signal_count >= 2:
        return "medium"
    return "low"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


# --------------------------------------------------------------------------- #
# Per-file extraction
# --------------------------------------------------------------------------- #

def extract_blocks(path: Path, file_year: int | None) -> list[dict]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    if path.suffix.lower() in (".html", ".htm"):
        raw = _strip_html(raw)

    # Split on blank lines (one or more)
    raw_blocks = re.split(r"\n{2,}", raw)
    results = []
    for idx, block in enumerate(raw_blocks):
        text = block.strip()
        if len(text) < 20:
            continue
        signals = _score_block(text)
        if signals < 1:
            continue
        year = _infer_year_from_block(text) or file_year
        pos = _infer_position(text)
        results.append({
            "source": str(path),
            "blockIndex": idx,
            "year": year,
            "position": pos,
            "confidence": _confidence(signals),
            "text": text[:2000],  # cap to 2000 chars
        })
    return results


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    cfg = dl.load_config()
    ap = argparse.ArgumentParser(description="Extract player blocks from text files.")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--output", default=None, help="Output JSONL path (default: data/bronze/raw_player_blocks.jsonl)")
    args = ap.parse_args()

    data_dir = dl.resolve_data_dir(args.data_dir)
    if not data_dir.exists():
        dl.log(f"ERROR: data directory does not exist: {data_dir}")
        return 2

    text_exts = set(cfg.get("textFileTypes", ["txt", "md", "log", "html"]))
    files = dl.discover_files(data_dir, text_exts)
    dl.log(f"found {len(files)} text files in {data_dir}")

    out_path = Path(args.output) if args.output else dl.repo_path(cfg.get("bronzeDir", "data/bronze"), "raw_player_blocks.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total_blocks = 0
    by_conf: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    with open(out_path, "w", encoding="utf-8") as fh:
        for sf in files:
            file_year = _infer_year_from_filename(sf.path)
            blocks = extract_blocks(sf.path, file_year)
            for b in blocks:
                fh.write(json.dumps(b, ensure_ascii=False) + "\n")
                total_blocks += 1
                by_conf[b["confidence"]] = by_conf.get(b["confidence"], 0) + 1

    dl.log(
        f"wrote {total_blocks} blocks to {out_path}  "
        f"[high={by_conf['high']} medium={by_conf['medium']} low={by_conf['low']}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
