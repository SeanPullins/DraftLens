import { DataGate } from "../components/DataGate";
import { EmptyState } from "../components/EmptyState";
import { ScoreBadge } from "../components/ScoreBadge";
import { useOpenPlayer } from "../lib/ui";
import type { BacktestCall, GroupStat, TierStat } from "../lib/types";
import { num, pct } from "../lib/format";

function GroupTable({ title, rows }: { title: string; rows: GroupStat[] }) {
  if (rows.length === 0) return null;
  return (
    <section className="rounded-xl border border-line bg-ink-900 p-4">
      <h3 className="mb-2 text-sm font-semibold text-slate-100">{title}</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wider text-slate-500">
            <th className="py-1 font-medium">Group</th>
            <th className="py-1 font-medium">n</th>
            <th className="py-1 font-medium">Corr</th>
            <th className="py-1 font-medium">Hit rate</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-t border-line/60">
              <td className="py-1.5 text-slate-200">{r.key}</td>
              <td className="py-1.5 tabular-nums text-slate-400">{r.count}</td>
              <td className="py-1.5 tabular-nums text-slate-400">{num(r.correlation, 2)}</td>
              <td className="py-1.5 tabular-nums text-slate-400">{pct(r.hitRate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function TierTable({ rows }: { rows: TierStat[] }) {
  if (rows.length === 0) return null;
  return (
    <section className="rounded-xl border border-line bg-ink-900 p-4">
      <h3 className="mb-2 text-sm font-semibold text-slate-100">Hit / bust rate by tier</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wider text-slate-500">
            <th className="py-1 font-medium">Tier</th>
            <th className="py-1 font-medium">n</th>
            <th className="py-1 font-medium">Hit</th>
            <th className="py-1 font-medium">Bust</th>
            <th className="py-1 font-medium">Avg value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.tier} className="border-t border-line/60">
              <td className="py-1.5 text-slate-200">{r.tier}</td>
              <td className="py-1.5 tabular-nums text-slate-400">{r.count}</td>
              <td className="py-1.5 tabular-nums text-tier-elite">{pct(r.hitRate)}</td>
              <td className="py-1.5 tabular-nums text-tier-risk">{pct(r.bustRate)}</td>
              <td className="py-1.5 tabular-nums text-slate-400">{num(r.avgRealizedValue)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function CallList({ title, calls, tone }: { title: string; calls: BacktestCall[]; tone: "good" | "bad" }) {
  const open = useOpenPlayer();
  if (calls.length === 0) return null;
  return (
    <section className="rounded-xl border border-line bg-ink-900 p-4">
      <h3 className={`mb-2 text-sm font-semibold ${tone === "good" ? "text-tier-elite" : "text-tier-risk"}`}>{title}</h3>
      <div className="space-y-1">
        {calls.map((c) => (
          <button
            key={c.playerId}
            onClick={() => open(c.playerId)}
            className="flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-ink-800"
          >
            <ScoreBadge score={c.draftLensScore} size="sm" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-slate-200">
                {c.name} <span className="text-slate-500">· {c.position} · {c.draftClass}</span>
              </p>
              <p className="truncate text-xs text-slate-500">{c.note}</p>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}

export function ModelLabPage() {
  return (
    <DataGate>
      {(data) => {
        const b = data.backtest;
        if (!b.dataReady) {
          return (
            <div className="space-y-4">
              <h1 className="text-xl font-semibold text-slate-100">Model Lab</h1>
              <EmptyState
                title="No backtest yet"
                message="Backtests appear after the model trains on historical classes with NFL outcomes."
                showPipeline
              />
            </div>
          );
        }
        return (
          <div className="space-y-6">
            <div>
              <h1 className="text-xl font-semibold text-slate-100">Model Lab</h1>
              <p className="mt-1 text-sm text-slate-400">{b.validationScheme}</p>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric label="Overall correlation" value={num(b.overallCorrelation, 3)} />
              <Metric label="Classes tested" value={String(b.byClass.length)} />
              <Metric label="Positions" value={String(b.byPosition.length)} />
              <Metric label="Tiers" value={String(b.byTier.length)} />
            </div>

            <TierTable rows={b.byTier} />

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <GroupTable title="Accuracy by position" rows={b.byPosition} />
              <GroupTable title="Accuracy by draft range" rows={b.byRound} />
              <GroupTable title="Accuracy by class" rows={b.byClass} />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <CallList title="Biggest model hits" calls={b.topHits} tone="good" />
              <CallList title="Biggest model misses" calls={b.topMisses} tone="bad" />
            </div>

            {b.notes && <p className="text-xs text-slate-500">{b.notes}</p>}
          </div>
        );
      }}
    </DataGate>
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
