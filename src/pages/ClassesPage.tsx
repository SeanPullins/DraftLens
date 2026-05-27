import { Link } from "react-router-dom";
import { DataGate } from "../components/DataGate";
import { EmptyState } from "../components/EmptyState";
import type { ClassSummary } from "../lib/types";

const KIND_LABEL: Record<ClassSummary["kind"], string> = {
  future: "Future prospects",
  recent: "Recent classes",
  historical: "Historical (backtested)",
};

const KIND_ORDER: ClassSummary["kind"][] = ["future", "recent", "historical"];

function ClassCard({ c }: { c: ClassSummary }) {
  return (
    <Link
      to={`/class/${c.year}`}
      className="group flex flex-col gap-2 rounded-xl border border-line bg-ink-900 p-4 transition-colors hover:border-ink-500 hover:bg-ink-850"
    >
      <div className="flex items-baseline justify-between">
        <span className="text-2xl font-bold text-slate-100">{c.year}</span>
        {c.hasOutcomes && (
          <span className="rounded bg-tier-elite/15 px-1.5 py-0.5 text-[10px] text-tier-elite">backtested</span>
        )}
      </div>
      <p className="text-xs text-slate-500">{c.playerCount} players scored</p>
      <p className="text-xs text-slate-500">{c.positionsCovered.slice(0, 8).join(" · ") || "—"}</p>
      <span className="mt-auto text-xs text-accent opacity-0 transition-opacity group-hover:opacity-100">
        Open board →
      </span>
    </Link>
  );
}

export function ClassesPage() {
  return (
    <DataGate>
      {(data) => {
        if (data.classes.length === 0) {
          return (
            <div className="space-y-6">
              <h1 className="text-xl font-semibold text-slate-100">Draft Classes</h1>
              <EmptyState title="No classes yet" message="Class boards appear once the model has scored players." showPipeline />
            </div>
          );
        }
        const grouped = KIND_ORDER.map((kind) => ({
          kind,
          items: data.classes.filter((c) => c.kind === kind).sort((a, b) => b.year - a.year),
        })).filter((g) => g.items.length > 0);

        return (
          <div className="space-y-8">
            <h1 className="text-xl font-semibold text-slate-100">Draft Classes</h1>
            {grouped.map((g) => (
              <section key={g.kind}>
                <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  {KIND_LABEL[g.kind]}
                </h2>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                  {g.items.map((c) => (
                    <ClassCard key={c.year} c={c} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        );
      }}
    </DataGate>
  );
}
