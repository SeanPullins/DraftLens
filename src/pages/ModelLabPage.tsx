import { DataGate } from "../components/DataGate";
import { EmptyState } from "../components/EmptyState";

export function ModelLabPage() {
  return (
    <DataGate>
      {(data) => (
        <div className="space-y-4">
          <h1 className="text-xl font-semibold text-slate-100">Model Lab</h1>
          <p className="text-sm text-slate-400">
            Walk-forward backtests: hit rate by tier, position, round, and class.
          </p>
          {!data.backtest.dataReady ? (
            <EmptyState
              title="No backtest yet"
              message="Backtests appear after the model trains on historical classes with NFL outcomes."
              showPipeline
            />
          ) : (
            <p className="rounded-lg border border-line bg-ink-900 p-6 text-sm text-slate-500">
              Backtest panels are wired up in the next build step.
            </p>
          )}
        </div>
      )}
    </DataGate>
  );
}
