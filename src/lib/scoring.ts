import type { Tier } from "./types";

// Color coding for the 1..99 DraftLens Score. Kept as discrete bands so the
// board reads consistently. These are display thresholds only; the model owns
// the actual tier assignment per player.
export interface ScoreStyle {
  text: string;
  bg: string;
  ring: string;
  bar: string;
}

export function scoreStyle(score: number): ScoreStyle {
  if (score >= 85) return { text: "text-tier-elite", bg: "bg-tier-elite/15", ring: "ring-tier-elite/40", bar: "bg-tier-elite" };
  if (score >= 75) return { text: "text-tier-high", bg: "bg-tier-high/15", ring: "ring-tier-high/40", bar: "bg-tier-high" };
  if (score >= 60) return { text: "text-tier-mid", bg: "bg-tier-mid/15", ring: "ring-tier-mid/40", bar: "bg-tier-mid" };
  if (score >= 45) return { text: "text-tier-low", bg: "bg-tier-low/15", ring: "ring-tier-low/40", bar: "bg-tier-low" };
  return { text: "text-tier-risk", bg: "bg-tier-risk/15", ring: "ring-tier-risk/40", bar: "bg-tier-risk" };
}

export const TIER_ORDER: Tier[] = ["Elite", "High", "Solid", "Developmental", "Risk"];

export function tierStyle(tier: Tier): { text: string; bg: string; border: string } {
  switch (tier) {
    case "Elite":
      return { text: "text-tier-elite", bg: "bg-tier-elite/10", border: "border-tier-elite/40" };
    case "High":
      return { text: "text-tier-high", bg: "bg-tier-high/10", border: "border-tier-high/40" };
    case "Solid":
      return { text: "text-tier-mid", bg: "bg-tier-mid/10", border: "border-tier-mid/40" };
    case "Developmental":
      return { text: "text-tier-low", bg: "bg-tier-low/10", border: "border-tier-low/40" };
    case "Risk":
      return { text: "text-tier-risk", bg: "bg-tier-risk/10", border: "border-tier-risk/40" };
  }
}

export const POSITION_GROUPS = [
  "QB",
  "RB",
  "WR",
  "TE",
  "OL",
  "DL",
  "EDGE",
  "LB",
  "CB",
  "S",
] as const;

export type PositionGroup = (typeof POSITION_GROUPS)[number];
