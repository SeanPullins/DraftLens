import { DataGate } from "../components/DataGate";
import { EmptyState } from "../components/EmptyState";

export function ComparePage() {
  return (
    <DataGate>
      {(data) => (
        <div className="space-y-4">
          <h1 className="text-xl font-semibold text-slate-100">Compare Players</h1>
          <p className="text-sm text-slate-400">Compare 2–4 prospects side by side.</p>
          {data.players.length === 0 ? (
            <EmptyState title="No players yet" message="Comparison needs scored players." showPipeline />
          ) : (
            <p className="rounded-lg border border-line bg-ink-900 p-6 text-sm text-slate-500">
              The comparison view is wired up in the next build step.
            </p>
          )}
        </div>
      )}
    </DataGate>
  );
}
