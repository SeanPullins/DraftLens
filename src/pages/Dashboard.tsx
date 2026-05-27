import { useMemo } from "react";
import { Link } from "react-router-dom";
import { DataGate } from "../components/DataGate";
import { EmptyState } from "../components/EmptyState";
import { ScoreBadge } from "../components/ScoreBadge";
import { useOpenPlayer } from "../lib/ui";
import type { DraftLensData } from "../lib/data";
import type { Player } from "../lib/types";
import { pct, signed } from "../lib/format";

function PlayerRow({ player, sub }: { player: Player; sub?: string }) {
  const open = useOpenPlayer();
  return (
    <button
      onClick={() => open(player.playerId)}
      className="flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-ink-800"
    >
      <ScoreBadge score={player.draftLensScore} size="sm" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-100">{player.name}</p>
        <p className="truncate text-xs text-slate-500">
          {player.position} · {player.school}
        </p>
      </div>
      {sub && <span className="text-xs text-slate-400">{sub}</span>}
    </button>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-ink-900 p-4">
      <div className="mb-2">
        <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

export function Dashboard() {
  return (
    <DataGate>
      {(data) => {
        if (!data.manifest.dataReady || data.players.length === 0) {
          return (
            <div className="space-y-6">
              <Header manifest={data.manifest} playerCount={0} classCount={0} />
              <EmptyState
                title="No model data yet"
                message="DraftLens is scaffolded and ready. Generate real outputs from your local data and the dashboard will populate automatically."
                showPipeline
              />
            </div>
          );
        }
        return <Loaded data={data} />;
      }}
    </DataGate>
  );
}

function Header({
  manifest,
  playerCount,
  classCount,
}: {
  manifest: { modelVersion: string; outcomeTarget: string | null; dataReady: boolean };
  playerCount: number;
  classCount: number;
}) {
  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-100">Draft War Room</h1>
      <p className="mt-1 text-sm text-slate-400">
        {manifest.dataReady
          ? `${playerCount.toLocaleString()} players across ${classCount} classes · model v${manifest.modelVersion}` +
            (manifest.outcomeTarget ? ` · target: ${manifest.outcomeTarget}` : "")
          : "Transparent, backtested NFL Draft scoring."}
      </p>
    </div>
  );
}

function Loaded({ data }: { data: DraftLensData }) {
  const { players, classes } = data;

  const latestClass = useMemo(
    () => classes.slice().sort((a, b) => b.year - a.year)[0],
    [classes],
  );
  const byScore = useMemo(() => players.slice().sort((a, b) => b.draftLensScore - a.draftLensScore), [players]);
  const latestLeaders = useMemo(
    () =>
      latestClass
        ? players.filter((p) => p.draftClass === latestClass.year).sort((a, b) => b.draftLensScore - a.draftLensScore).slice(0, 8)
        : [],
    [players, latestClass],
  );
  const biggestValues = useMemo(
    () => players.filter((p) => p.valueVsPick != null).sort((a, b) => (b.valueVsPick ?? 0) - (a.valueVsPick ?? 0)).slice(0, 6),
    [players],
  );
  const bustRisks = useMemo(
    () => players.slice().sort((a, b) => b.bustRisk - a.bustRisk).slice(0, 6),
    [players],
  );
  const avgConfidence = useMemo(
    () => (players.length ? players.reduce((s, p) => s + p.confidence, 0) / players.length : 0),
    [players],
  );

  return (
    <div className="space-y-6">
      <Header manifest={data.manifest} playerCount={players.length} classCount={classes.length} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Players scored" value={players.length.toLocaleString()} />
        <Metric label="Draft classes" value={String(classes.length)} />
        <Metric label="Avg confidence" value={pct(avgConfidence)} />
        <Metric label="Model" value={`v${data.manifest.modelVersion}`} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel title="Top prospects overall" subtitle="Highest DraftLens Score across all classes">
          <div className="space-y-0.5">
            {byScore.slice(0, 8).map((p) => (
              <PlayerRow key={p.playerId} player={p} sub={`${p.draftClass}`} />
            ))}
          </div>
        </Panel>

        <Panel
          title={latestClass ? `${latestClass.year} class leaders` : "Latest class"}
          subtitle="Most recent draft class"
        >
          {latestLeaders.length ? (
            <div className="space-y-0.5">
              {latestLeaders.map((p) => (
                <PlayerRow key={p.playerId} player={p} sub={p.position} />
              ))}
            </div>
          ) : (
            <p className="px-2 py-4 text-sm text-slate-500">No players in the latest class.</p>
          )}
          {latestClass && (
            <Link to={`/class/${latestClass.year}`} className="mt-2 block text-xs text-accent hover:underline">
              View full {latestClass.year} board →
            </Link>
          )}
        </Panel>

        <div className="space-y-4">
          <Panel title="Biggest values" subtitle="Best score relative to draft slot">
            <div className="space-y-0.5">
              {biggestValues.length ? (
                biggestValues.map((p) => <PlayerRow key={p.playerId} player={p} sub={signed(p.valueVsPick)} />)
              ) : (
                <p className="px-2 py-3 text-sm text-slate-500">No draft-slot data yet.</p>
              )}
            </div>
          </Panel>
          <Panel title="Bust risks" subtitle="Highest modeled bust probability">
            <div className="space-y-0.5">
              {bustRisks.map((p) => (
                <PlayerRow key={p.playerId} player={p} sub={pct(p.bustRisk)} />
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-ink-900 p-3">
      <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-100">{value}</p>
    </div>
  );
}
