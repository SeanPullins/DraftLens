import { DataGate } from "../components/DataGate";
import { EmptyState } from "../components/EmptyState";

export function PositionsPage() {
  return (
    <DataGate>
      {(data) => (
        <div className="space-y-4">
          <h1 className="text-xl font-semibold text-slate-100">Position Boards</h1>
          <p className="text-sm text-slate-400">Position-specific scoring and rankings.</p>
          {data.players.length === 0 ? (
            <EmptyState title="No players yet" message="Position boards populate after the model runs." showPipeline />
          ) : (
            <p className="rounded-lg border border-line bg-ink-900 p-6 text-sm text-slate-500">
              Position-specific boards are wired up in the next build step.
            </p>
          )}
        </div>
      )}
    </DataGate>
  );
}
