import { DataGate } from "../components/DataGate";
import { formatDate } from "../lib/format";

export function DataHealthPage() {
  return (
    <DataGate>
      {(data) => {
        const m = data.manifest;
        const matched = data.players.length;
        return (
          <div className="space-y-6">
            <div>
              <h1 className="text-xl font-semibold text-slate-100">Data Health</h1>
              <p className="mt-1 text-sm text-slate-400">
                What the model loaded, what it matched, and any warnings.
              </p>
            </div>

            <div className="flex items-center gap-3 rounded-xl border border-line bg-ink-900 p-4">
              <span
                className={`h-3 w-3 rounded-full ${m.dataReady ? "bg-tier-elite" : "bg-tier-low"}`}
              />
              <div>
                <p className="text-sm font-medium text-slate-100">
                  {m.dataReady ? "Model data loaded" : "No data generated yet"}
                </p>
                <p className="text-xs text-slate-500">
                  model v{m.modelVersion} · last generated {formatDate(m.generatedAt)}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Players matched" value={matched.toLocaleString()} />
              <Stat label="Classes" value={String(m.classesAvailable.length)} />
              <Stat label="Datasets loaded" value={String(m.datasets.length)} />
              <Stat label="Outcome target" value={m.outcomeTarget ?? "—"} />
            </div>

            {m.datasets.length > 0 && (
              <section>
                <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Loaded datasets
                </h2>
                <div className="overflow-x-auto rounded-xl border border-line">
                  <table className="w-full min-w-[480px] text-sm">
                    <thead>
                      <tr className="border-b border-line bg-ink-850 text-left text-xs uppercase tracking-wider text-slate-500">
                        <th className="px-3 py-2 font-medium">Dataset</th>
                        <th className="px-3 py-2 font-medium">Rows</th>
                        <th className="px-3 py-2 font-medium">Cols</th>
                        <th className="px-3 py-2 font-medium">Purpose</th>
                      </tr>
                    </thead>
                    <tbody>
                      {m.datasets.map((d) => (
                        <tr key={d.name} className="border-b border-line/60 last:border-0">
                          <td className="px-3 py-2 text-slate-200">{d.name}</td>
                          <td className="px-3 py-2 tabular-nums text-slate-400">{d.rows.toLocaleString()}</td>
                          <td className="px-3 py-2 tabular-nums text-slate-400">{d.columns}</td>
                          <td className="px-3 py-2 text-slate-400">{d.purpose}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            <section>
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Warnings</h2>
              {m.warnings.length === 0 ? (
                <p className="rounded-lg border border-line bg-ink-900 p-3 text-sm text-slate-500">No warnings.</p>
              ) : (
                <ul className="space-y-2">
                  {m.warnings.map((w, i) => (
                    <li
                      key={i}
                      className="rounded-lg border border-tier-low/30 bg-tier-low/10 px-3 py-2 text-sm text-slate-300"
                    >
                      {w}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        );
      }}
    </DataGate>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-ink-900 p-3">
      <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-100">{value}</p>
    </div>
  );
}
