import { Link, useParams } from "react-router-dom";
import { DataGate } from "../components/DataGate";
import { EmptyState } from "../components/EmptyState";
import { ClassBoard } from "../components/ClassBoard";
import type { DraftLensData } from "../lib/data";
import { uniqueSorted } from "../lib/filters";

function PositionsInner({ data, group }: { data: DraftLensData; group?: string }) {
  const groups = uniqueSorted(data.players.map((p) => p.positionGroup));
  const active = group && groups.includes(group) ? group : groups[0];
  const players = data.players.filter((p) => p.positionGroup === active);
  const summary = data.positions.positions.find((s) => s.positionGroup === active);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Position Boards</h1>
        <p className="mt-1 text-sm text-slate-400">Position-specific scoring across all classes.</p>
      </div>

      <div className="flex flex-wrap gap-1">
        {groups.map((g) => (
          <Link
            key={g}
            to={`/positions/${g}`}
            className={`rounded-md px-3 py-1.5 text-sm ${
              g === active ? "bg-ink-700 text-slate-100" : "text-slate-400 hover:bg-ink-800"
            }`}
          >
            {g}
          </Link>
        ))}
      </div>

      {summary && (
        <div className="flex flex-wrap gap-2 text-xs text-slate-500">
          <span className="rounded border border-line bg-ink-900 px-2 py-1">model: {summary.modelType}</span>
          {summary.featuresUsed.slice(0, 6).map((f) => (
            <span key={f} className="rounded border border-line bg-ink-900 px-2 py-1">
              {f}
            </span>
          ))}
        </div>
      )}

      <ClassBoard players={players} showClassColumn defaultSort="draftLensScore" />
    </div>
  );
}

export function PositionsPage() {
  const { group } = useParams();
  return (
    <DataGate>
      {(data) =>
        data.players.length === 0 ? (
          <div className="space-y-4">
            <h1 className="text-xl font-semibold text-slate-100">Position Boards</h1>
            <EmptyState title="No players yet" message="Position boards populate after the model runs." showPipeline />
          </div>
        ) : (
          <PositionsInner data={data} group={group} />
        )
      }
    </DataGate>
  );
}
