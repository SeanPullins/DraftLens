import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useDataState } from "../lib/data";
import { useOpenPlayer } from "../lib/ui";
import type { Player } from "../lib/types";
import { ScoreBadge } from "./ScoreBadge";
import { scoreStyle, tierStyle } from "../lib/scoring";
import { confidenceLabel, num, pct, pickLabel, signed, valueVsPickLabel } from "../lib/format";

const COMPONENT_LABELS: Record<string, string> = {
  production: "Production",
  efficiency: "Efficiency",
  athletic: "Athletic",
  size: "Size",
  age: "Age",
  draftCapital: "Draft capital",
  positionValue: "Position value",
  risk: "Risk",
  upside: "Upside",
  confidence: "Confidence",
};

function ComponentBar({ label, value }: { label: string; value: number }) {
  const s = scoreStyle(value);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        <span className={`font-semibold tabular-nums ${s.text}`}>{Math.round(value)}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
        <div className={`h-full rounded-full ${s.bar}`} style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}

function DrawerBody({ p, onClose }: { p: Player; onClose: () => void }) {
  const open = useOpenPlayer();
  const tier = tierStyle(p.tier);
  const components = Object.entries(p.scoreComponents).filter(
    (e): e is [string, number] => typeof e[1] === "number",
  );
  // A player has a validated result only once career value has accrued. Until
  // then the score is a forward projection — we label it as such so a rookie's
  // grade is never mistaken for a known outcome.
  const validated = p.realizedValue != null;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between border-b border-line p-5">
        <div className="flex items-center gap-4">
          <ScoreBadge score={p.draftLensScore} size="lg" />
          <div>
            <h2 className="text-lg font-semibold text-slate-100">{p.name}</h2>
            <p className="text-sm text-slate-400">
              {p.position} · {p.school} · {p.draftClass}
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
              <span className={`rounded border px-1.5 py-0.5 ${tier.bg} ${tier.text} ${tier.border}`}>
                {p.tier}
              </span>
              <span
                className={`rounded border px-1.5 py-0.5 ${
                  validated
                    ? "border-slate-600 text-slate-300"
                    : "border-amber-500/40 bg-amber-500/10 text-amber-400"
                }`}
                title={
                  validated
                    ? "This player has accumulated NFL career value, so the grade can be checked against reality."
                    : "This player's NFL career hasn't played out yet — the grade is a forward projection."
                }
              >
                {validated ? "Validated" : "Projection"}
              </span>
              <span className="text-slate-500">{pickLabel(p)}</span>
              {p.actualTeam && <span className="text-slate-500">· {p.actualTeam}</span>}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-md px-2 py-1 text-slate-500 hover:bg-ink-700 hover:text-slate-200"
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto p-5">
        <div className="grid grid-cols-3 gap-3 text-center">
          <Stat label="Confidence" value={confidenceLabel(p.confidence)} sub={pct(p.confidence)} />
          <Stat label="Bust risk" value={pct(p.bustRisk)} />
          <Stat label="Value vs pick" value={valueVsPickLabel(p.valueVsPick)} sub={signed(p.valueVsPick)} />
        </div>

        <Section title={validated ? "Projection vs. reality" : "Forward projection"}>
          <p className="text-sm text-slate-300">{p.projectedOutcome}</p>
          {p.projectedValue != null && (
            <p className="mt-1 text-xs text-slate-500">Projected value: {num(p.projectedValue)}</p>
          )}
          {validated ? (
            p.realizedOutcome && (
              <p className="mt-2 text-xs text-slate-400">
                Actual NFL outcome: <span className="text-slate-200">{p.realizedOutcome}</span>
              </p>
            )
          ) : (
            <p className="mt-2 text-xs text-amber-500/80">
              This player's career hasn't played out — there's no result to check against yet.
            </p>
          )}
        </Section>

        {p.explanation && (
          <Section title="Summary">
            <p className="text-sm leading-relaxed text-slate-300">{p.explanation}</p>
          </Section>
        )}

        {components.length > 0 && (
          <Section title="Score components">
            <div className="grid grid-cols-2 gap-x-5 gap-y-3">
              {components.map(([key, value]) => (
                <ComponentBar key={key} label={COMPONENT_LABELS[key] ?? key} value={value} />
              ))}
            </div>
          </Section>
        )}

        {p.drivers.length > 0 && (
          <Section title="Model drivers">
            <ul className="space-y-1.5">
              {p.drivers.map((d, i) => (
                <li key={i} className="flex items-center justify-between text-sm">
                  <span className="text-slate-300">{d.label}</span>
                  <span className={`tabular-nums ${d.contribution >= 0 ? "text-tier-elite" : "text-tier-risk"}`}>
                    {signed(d.contribution)}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          {p.strengths.length > 0 && (
            <Section title="Strengths">
              <ul className="space-y-1 text-sm text-slate-300">
                {p.strengths.map((s, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-tier-elite">+</span>
                    {s}
                  </li>
                ))}
              </ul>
            </Section>
          )}
          {p.redFlags.length > 0 && (
            <Section title="Red flags">
              <ul className="space-y-1 text-sm text-slate-300">
                {p.redFlags.map((s, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-tier-risk">!</span>
                    {s}
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </div>

        {p.comps.length > 0 && (
          <Section title="Comparable players">
            <div className="flex flex-wrap gap-2">
              {p.comps.map((c, i) => {
                const cid = c.playerId;
                return cid ? (
                  <button
                    key={i}
                    onClick={() => open(cid)}
                    className="rounded-md border border-line bg-ink-800 px-2 py-1 text-xs text-slate-300 transition-colors hover:border-accent/50 hover:text-slate-100"
                    title={`Open ${c.name}`}
                  >
                    {c.name}
                    <span className="ml-1 text-slate-500">{pct(c.similarity)}</span>
                  </button>
                ) : (
                  <span key={i} className="rounded-md border border-line bg-ink-800 px-2 py-1 text-xs text-slate-300">
                    {c.name}
                    <span className="ml-1 text-slate-500">{pct(c.similarity)}</span>
                  </span>
                );
              })}
            </div>
          </Section>
        )}

        <p className="pt-2 text-right text-[11px] text-slate-600">
          model {p.modelVersion} · data completeness {pct(p.dataCompleteness)}
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-line bg-ink-800 p-3">
      <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-100">{value}</p>
      {sub && <p className="text-[11px] text-slate-500">{sub}</p>}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</h3>
      {children}
    </section>
  );
}

export function PlayerDrawer() {
  const [params, setParams] = useSearchParams();
  const state = useDataState();
  const id = params.get("player");

  const close = () => {
    const next = new URLSearchParams(params);
    next.delete("player");
    setParams(next, { replace: true });
  };

  useEffect(() => {
    if (!id) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!id || state.status !== "ready") return null;
  const player = state.data.playersById.get(id);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={close} />
      <div className="relative h-full w-full max-w-md border-l border-line bg-ink-900 shadow-2xl">
        {player ? (
          <DrawerBody p={player} onClose={close} />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <p className="text-sm text-slate-400">Player “{id}” not found in the current dataset.</p>
            <button onClick={close} className="rounded-md bg-ink-700 px-3 py-1.5 text-sm text-slate-200">
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
