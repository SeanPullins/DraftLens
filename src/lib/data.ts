import { createContext, useContext } from "react";
import type {
  BacktestSummary,
  ClassSummary,
  ModelManifest,
  Player,
  PositionSummaries,
} from "./types";

export interface DraftLensData {
  players: Player[];
  classes: ClassSummary[];
  manifest: ModelManifest;
  backtest: BacktestSummary;
  positions: PositionSummaries;
  playersById: Map<string, Player>;
}

export type LoadState =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; data: DraftLensData };

// Base-aware path so fetches work under the GitHub Pages /DraftLens/ subpath.
function asset(path: string): string {
  return `${import.meta.env.BASE_URL}${path}`.replace(/\/{2,}/g, "/");
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(asset(path));
  if (!res.ok) throw new Error(`Failed to load ${path} (${res.status})`);
  return (await res.json()) as T;
}

export async function loadDraftLensData(): Promise<DraftLensData> {
  const [players, classes, manifest, backtest, positions] = await Promise.all([
    fetchJson<Player[]>("data/model/draftlens_players.json"),
    fetchJson<ClassSummary[]>("data/model/classes.json"),
    fetchJson<ModelManifest>("data/model/model_manifest.json"),
    fetchJson<BacktestSummary>("data/model/backtest_summary.json"),
    fetchJson<PositionSummaries>("data/model/position_summaries.json"),
  ]);

  const playersById = new Map(players.map((p) => [p.playerId, p]));
  return { players, classes, manifest, backtest, positions, playersById };
}

export const DataContext = createContext<LoadState | null>(null);

export function useData(): DraftLensData {
  const state = useContext(DataContext);
  if (!state) throw new Error("useData must be used within <DataProvider>");
  if (state.status !== "ready") {
    throw new Error("useData read before data was ready — guard with useDataState");
  }
  return state.data;
}

export function useDataState(): LoadState {
  const state = useContext(DataContext);
  if (!state) throw new Error("useDataState must be used within <DataProvider>");
  return state;
}
