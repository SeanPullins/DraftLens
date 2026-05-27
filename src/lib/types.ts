// Shared data contract between the Python export pipeline and the React app.
// scripts/export_frontend_data.py MUST emit JSON matching these shapes.

export type Tier = "Elite" | "High" | "Solid" | "Developmental" | "Risk";

export type FlagKind = "gem" | "value" | "bust" | "injury" | "age" | "production" | "data";

export interface PlayerFlag {
  kind: FlagKind;
  label: string;
  // Optional longer note shown in the player detail view.
  note?: string;
}

export interface ScoreComponents {
  production: number | null;
  efficiency: number | null;
  athletic: number | null;
  size: number | null;
  age: number | null;
  draftCapital: number | null;
  positionValue: number | null;
  risk: number | null;
  upside: number | null;
  confidence: number | null;
  // Position-specific extras (e.g. QB BTT/TWP) live here, all optional.
  [extra: string]: number | null | undefined;
}

export interface ScoreDriver {
  // Human-readable model driver, e.g. "Yards per route run" or "Draft capital".
  label: string;
  // Signed contribution to the score (positive = helps, negative = hurts).
  contribution: number;
  // Optional raw value / percentile for display.
  value?: number | null;
  detail?: string;
}

export interface PlayerComp {
  name: string;
  playerId?: string | null;
  similarity: number; // 0..1
  outcome?: string | null;
}

export interface Player {
  playerId: string;
  name: string;
  position: string;
  positionGroup: string; // QB, RB, WR, TE, OL, DL, EDGE, LB, CB, S ...
  school: string;
  draftClass: number;

  // Historical players have actuals; future prospects have projections.
  actualPick: number | null;
  actualTeam: string | null;
  projectedPick: number | null;

  // The single public-facing score, 1..99.
  draftLensScore: number;
  positionRank: number;
  overallRank: number;
  tier: Tier;
  confidence: number; // 0..1

  projectedOutcome: string; // e.g. "Multi-year starter"
  projectedValue: number | null; // model's outcome estimate (units documented in manifest)
  bustRisk: number; // 0..1
  upsideScore: number; // 1..99

  valueVsPick: number | null; // positive = better than draft slot implied

  modelVersion: string;

  scoreComponents: ScoreComponents;
  drivers: ScoreDriver[];
  flags: PlayerFlag[];
  comps: PlayerComp[];
  strengths: string[];
  redFlags: string[];
  explanation: string; // one-paragraph summary

  // Data completeness 0..1 — how much of the expected feature set was present.
  dataCompleteness: number;

  // For historical players: realized outcome label used in backtests (never a feature).
  realizedOutcome?: string | null;
  realizedValue?: number | null;
}

export interface ClassSummary {
  year: number;
  kind: "historical" | "recent" | "future";
  playerCount: number;
  topPlayerIds: string[];
  positionsCovered: string[];
  // Whether the model could backtest this class (has realized outcomes).
  hasOutcomes: boolean;
  notes?: string;
}

export interface DatasetInfo {
  name: string;
  rows: number;
  columns: number;
  purpose: string;
}

export interface ModelManifest {
  modelVersion: string;
  generatedAt: string | null; // ISO timestamp
  dataReady: boolean;
  playerCount: number;
  classesAvailable: number[];
  // What outcome target the model actually trained on (auto-selected).
  outcomeTarget: string | null;
  outcomeUnits: string | null;
  datasets: DatasetInfo[];
  warnings: string[];
  message?: string;
}

export interface TierStat {
  tier: Tier;
  count: number;
  hitRate: number | null;
  bustRate: number | null;
  avgRealizedValue: number | null;
}

export interface GroupStat {
  key: string; // position, round bucket, or class year (as string)
  count: number;
  correlation: number | null;
  hitRate: number | null;
}

export interface BacktestCall {
  playerId: string;
  name: string;
  draftClass: number;
  position: string;
  draftLensScore: number;
  actualPick: number | null;
  realizedOutcome: string | null;
  note: string;
}

export interface BacktestSummary {
  dataReady: boolean;
  overallCorrelation: number | null;
  validationScheme: string; // e.g. "walk-forward 2014..2024"
  byTier: TierStat[];
  byPosition: GroupStat[];
  byRound: GroupStat[];
  byClass: GroupStat[];
  topHits: BacktestCall[];
  topMisses: BacktestCall[];
  notes?: string;
}

export interface PositionSummary {
  positionGroup: string;
  playerCount: number;
  featuresUsed: string[];
  topPlayerIds: string[];
  modelType: string; // e.g. "ridge", "position-specific", "draft-slot baseline"
}

export interface PositionSummaries {
  dataReady: boolean;
  positions: PositionSummary[];
}
