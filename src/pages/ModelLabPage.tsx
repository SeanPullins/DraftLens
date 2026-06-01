import { DataGate } from "../components/DataGate";
import { EmptyState } from "../components/EmptyState";
import { ScoreBadge } from "../components/ScoreBadge";
import { useOpenPlayer } from "../lib/ui";
import type { BacktestCall, ClassSummary, GroupStat, TierStat } from "../lib/types";
import { num, pct } from "../lib/format";

// Below this out-of-sample count, a per-group correlation is statistically
// meaningless (e.g. 6 long-snappers) — we show the sample but suppress the
// number rather than imply precision we don't have.
const MIN_RELIABLE_N = 30;

function GroupTable({
  title,
  rows,
  note,
  annotate,
}: {
  title: string;
  rows: GroupStat[];
  note?: string;
  annotate?: (r: GroupStat) => string | null;
}) {
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
          {rows.map((r) => {
            const lowN = r.count < MIN_RELIABLE_N;
            const tag = annotate?.(r);
            return (
              <tr key={r.key} className="border-t border-line/60">
                <td className="py-1.5 text-slate-200">
                  {r.key}
                  {tag && <span className="ml-1.5 text-[10px] uppercase tracking-wide text-amber-500/80">{tag}</span>}
                </td>
                <td className="py-1.5 tabular-nums text-slate-400">{r.count}</td>
                <td className={`py-1.5 tabular-nums ${lowN ? "text-slate-600" : "text-slate-400"}`}>
                  {lowN || r.correlation === null ? (
                    <span title={lowN ? `Only ${r.count} graded players — too few to be reliable` : "Not enough variance"}>
                      —
                    </span>
                  ) : (
                    num(r.correlation, 2)
                  )}
                </td>
                <td className="py-1.5 tabular-nums text-slate-400">{pct(r.hitRate)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {note && <p className="mt-2 text-[11px] leading-relaxed text-slate-500">{note}</p>}
    </section>
  );
}

function TierTable({ rows }: { rows: TierStat[] }) {
  if (rows.length === 0) return null;
  return (
    <section className="rounded-xl border border-line bg-ink-900 p-4">
      <h3 className="mb-1 text-sm font-semibold text-slate-100">Hit / bust rate by tier</h3>
      <p className="mb-2 text-[11px] leading-relaxed text-slate-500">
        Out-of-sample: each player is scored by a model trained only on earlier draft classes. A clean,
        monotonic drop from Elite to Risk is the signal that the tiers mean something.
      </p>
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

        // Map class year -> kind so we can flag classes whose careers are still
        // developing (recent/future). Their hit rates against career value are
        // necessarily low and must not be read as model failure.
        const kindByYear = new Map<string, ClassSummary["kind"]>();
        for (const c of data.classes) kindByYear.set(String(c.year), c.kind);
        const classNote =
          "Hit rate is measured against accumulated career value, so the most recent classes read low — " +
          "those players have barely begun their careers. Treat recent/future classes as projections that " +
          "cannot be scored yet, not as misses.";

        return (
          <div className="space-y-6">
            <div>
              <h1 className="text-xl font-semibold text-slate-100">Model Lab</h1>
              <p className="mt-1 text-sm text-slate-400">{b.validationScheme}</p>
            </div>

            {/* Honest framing up front */}
            <section className="rounded-xl border border-line bg-ink-900/60 p-4 text-sm leading-relaxed text-slate-300">
              <p>
                DraftLens predicts <span className="text-slate-100">career value</span> (weighted Approximate Value)
                from pre-draft information only. The headline number below is the{" "}
                <span className="text-slate-100">out-of-sample correlation</span> between predicted and actual
                career value, validated walk-forward: each class is scored by a model that never saw it.
              </p>
              <p className="mt-2 text-slate-400">
                A correlation near <span className="text-slate-100">{num(b.overallCorrelation, 2)}</span> is real,
                useful signal — in the range of published draft models — but it is not certainty. Some of it simply
                reflects that earlier picks pan out more often, since draft position is itself an input. The model is
                strongest in the trenches (DL, EDGE, OL, LB) and weakest exactly where the NFL itself struggles to
                predict (QB, TE). We show where it works and where it doesn't.
              </p>
            </section>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric label="Out-of-sample corr" value={num(b.overallCorrelation, 3)} />
              <Metric label="Classes tested" value={String(b.byClass.length)} />
              <Metric label="Positions" value={String(b.byPosition.length)} />
              <Metric label="Players graded" value={String(b.byTier.reduce((s, t) => s + t.count, 0))} />
            </div>

            <TierTable rows={b.byTier} />

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <GroupTable
                title="Accuracy by position"
                rows={b.byPosition}
                note={`Correlation is suppressed below ${MIN_RELIABLE_N} graded players (e.g. specialists) where it would be noise.`}
              />
              <GroupTable title="Accuracy by draft range" rows={b.byRound} />
              <GroupTable
                title="Accuracy by class"
                rows={b.byClass}
                note={classNote}
                annotate={(r) => {
                  const kind = kindByYear.get(r.key);
                  return kind === "recent" || kind === "future" ? "developing" : null;
                }}
              />
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
