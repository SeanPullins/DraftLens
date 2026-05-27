import type { Player } from "./types";

export type SortKey =
  | "overallRank"
  | "positionRank"
  | "draftLensScore"
  | "projectedValue"
  | "bustRisk"
  | "upsideScore"
  | "confidence"
  | "actualPick"
  | "valueVsPick";

export const SORT_LABELS: Record<SortKey, string> = {
  overallRank: "Overall Rank",
  positionRank: "Position Rank",
  draftLensScore: "DraftLens Score",
  projectedValue: "Projected NFL Value",
  bustRisk: "Bust Risk",
  upsideScore: "Upside",
  confidence: "Confidence",
  actualPick: "Actual Pick",
  valueVsPick: "Value vs Pick",
};

// Whether a higher raw value should sort first by default.
const DESC_BY_DEFAULT: Record<SortKey, boolean> = {
  overallRank: false,
  positionRank: false,
  draftLensScore: true,
  projectedValue: true,
  bustRisk: true,
  upsideScore: true,
  confidence: true,
  actualPick: false,
  valueVsPick: true,
};

export interface BoardFilters {
  position: string | "ALL";
  school: string | "ALL";
  tier: string | "ALL";
  minPick: number | null;
  maxPick: number | null;
  search: string;
}

export const EMPTY_FILTERS: BoardFilters = {
  position: "ALL",
  school: "ALL",
  tier: "ALL",
  minPick: null,
  maxPick: null,
  search: "",
};

function pickOf(p: Player): number | null {
  return p.actualPick ?? p.projectedPick ?? null;
}

export function applyFilters(players: Player[], f: BoardFilters): Player[] {
  const q = f.search.trim().toLowerCase();
  return players.filter((p) => {
    if (f.position !== "ALL" && p.positionGroup !== f.position) return false;
    if (f.school !== "ALL" && p.school !== f.school) return false;
    if (f.tier !== "ALL" && p.tier !== f.tier) return false;
    const pick = pickOf(p);
    if (f.minPick != null && (pick == null || pick < f.minPick)) return false;
    if (f.maxPick != null && (pick == null || pick > f.maxPick)) return false;
    if (q && !(`${p.name} ${p.school} ${p.position}`.toLowerCase().includes(q))) return false;
    return true;
  });
}

function valueFor(p: Player, key: SortKey): number | null {
  switch (key) {
    case "actualPick":
      return pickOf(p);
    case "valueVsPick":
      return p.valueVsPick;
    case "projectedValue":
      return p.projectedValue;
    default:
      return p[key];
  }
}

export function sortPlayers(players: Player[], key: SortKey, desc: boolean): Player[] {
  return [...players].sort((a, b) => {
    const av = valueFor(a, key);
    const bv = valueFor(b, key);
    // Nulls always sort to the bottom regardless of direction.
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return desc ? bv - av : av - bv;
  });
}

export function defaultDesc(key: SortKey): boolean {
  return DESC_BY_DEFAULT[key];
}

export function uniqueSorted(values: (string | null | undefined)[]): string[] {
  return Array.from(new Set(values.filter((v): v is string => !!v))).sort();
}
