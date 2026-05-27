import type { Player } from "./types";

export function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] ?? s[v] ?? s[0]);
}

// How a player's draft slot reads in the UI (actual vs projected vs none).
export function pickLabel(p: Player): string {
  if (p.actualPick != null) return `Pick ${p.actualPick}`;
  if (p.projectedPick != null) return `~Pick ${p.projectedPick}`;
  return "—";
}

export function pickShort(p: Player): string {
  if (p.actualPick != null) return `${p.actualPick}`;
  if (p.projectedPick != null) return `~${p.projectedPick}`;
  return "—";
}

export function pct(n: number | null | undefined, digits = 0): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

export function num(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

export function signed(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "—";
  const v = n.toFixed(digits);
  return n > 0 ? `+${v}` : v;
}

export function confidenceLabel(conf: number): "High" | "Medium" | "Low" {
  if (conf >= 0.7) return "High";
  if (conf >= 0.4) return "Medium";
  return "Low";
}

export function valueVsPickLabel(v: number | null): string {
  if (v == null) return "—";
  if (v > 8) return "Steal";
  if (v > 2) return "Value";
  if (v < -8) return "Reach";
  if (v < -2) return "Slight reach";
  return "Fair";
}

export function formatDate(iso: string | null): string {
  if (!iso) return "never";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
