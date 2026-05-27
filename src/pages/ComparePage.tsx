import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DataGate } from "../components/DataGate";
import { EmptyState } from "../components/EmptyState";
import { ScoreBadge } from "../components/ScoreBadge";
import type { DraftLensData } from "../lib/data";
import type { Player } from "../lib/types";
import { confidenceLabel, num, pct, pickLabel, signed } from "../lib/format";
import { scoreStyle } from "../lib/scoring";

const COMPONENT_ROWS: { key: string; label: string }[] = [
  { key: "production", label: "Production" },
  { key: "efficiency", label: "Efficiency" },
  { key: "athletic", label: "Athletic" },
  { key: "size", label: "Size" },
  { key: "age", label: "Age" },
  { key: "draftCapital", label: "Draft capital" },
  { key: "positionValue", label: "Position value" },
  { key: "risk", label: "Risk" },
  { key: "upside", label: "Upside" },
];

function PlayerPicker({ players, onPick, disabledIds }: { players: Player[]; onPick: (id: string) => void; disabledIds: Set<string> }) {
  const [q, setQ] = useState("");
  const matches = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return [];
    return players
      .filter((p) => `${p.name} ${p.school} ${p.position}`.toLowerCase().includes(query))
      .slice(0, 8);
  }, [players, q]);

  return (
    <div className="relative">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Add a player…"
        className="w-full rounded-md border border-line bg-ink-800 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:border-accent focus:outline-none"
      />
      {matches.length > 0 && (
        <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-md border border-line bg-ink-850 shadow-xl">
          {matches.map((p) => (
            <button
              key={p.playerId}
              disabled={disabledIds.has(p.playerId)}
              onClick={() => {
                onPick(p.playerId);
                setQ("");
              }}
              className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-ink-700 disabled:opacity-40"
            >
              <span className="text-slate-200">{p.name}</span>
              <span className="text-xs text-slate-500">
                {p.position} · {p.draftClass}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function valueCell(value: number | null | undefined) {
  if (value == null) return <span className="text-slate-600">—</span>;
  const s = scoreStyle(value);
  return <span className={`font-semibold tabular-nums ${s.text}`}>{Math.round(value)}</span>;
}

function CompareInner({ data }: { data: DraftLensData }) {
  const [params, setParams] = useSearchParams();
  const ids = (params.get("ids") ?? "").split(",").filter(Boolean);
  const selected = ids.map((id) => data.playersById.get(id)).filter((p): p is Player => !!p);

  const setIds = (next: string[]) => {
    const p = new URLSearchParams(params);
    if (next.length) p.set("ids", next.join(","));
    else p.delete("ids");
    setParams(p);
  };

  const add = (id: string) => {
    if (selected.length >= 4 || ids.includes(id)) return;
    setIds([...ids, id]);
  };
  const remove = (id: string) => setIds(ids.filter((x) => x !== id));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Compare Players</h1>
        <p className="mt-1 text-sm text-slate-400">Add 2–4 prospects to compare scores, traits, and projections.</p>
      </div>

      <div className="max-w-md">
        <PlayerPicker players={data.players} onPick={add} disabledIds={new Set(ids)} />
      </div>

      {selected.length === 0 ? (
        <p className="rounded-lg border border-line bg-ink-900 p-8 text-center text-sm text-slate-500">
          Search above to add players.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-sm">
            <tbody>
              <tr className="border-b border-line">
                <Th>Player</Th>
                {selected.map((p) => (
                  <td key={p.playerId} className="border-l border-line p-3 align-top">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold text-slate-100">{p.name}</p>
                        <p className="text-xs text-slate-500">
                          {p.position} · {p.school} · {p.draftClass}
                        </p>
                      </div>
                      <button onClick={() => remove(p.playerId)} className="text-slate-600 hover:text-slate-300" aria-label="Remove">
                        ✕
                      </button>
                    </div>
                  </td>
                ))}
              </tr>
              <Row label="DraftLens Score">
                {selected.map((p) => (
                  <Cell key={p.playerId}>
                    <ScoreBadge score={p.draftLensScore} />
                  </Cell>
                ))}
              </Row>
              <Row label="Tier">{selected.map((p) => <Cell key={p.playerId}>{p.tier}</Cell>)}</Row>
              <Row label="Confidence">
                {selected.map((p) => (
                  <Cell key={p.playerId}>
                    {confidenceLabel(p.confidence)} <span className="text-slate-500">({pct(p.confidence)})</span>
                  </Cell>
                ))}
              </Row>
              <Row label="Draft slot">{selected.map((p) => <Cell key={p.playerId}>{pickLabel(p)}</Cell>)}</Row>
              <Row label="Value vs pick">{selected.map((p) => <Cell key={p.playerId}>{signed(p.valueVsPick)}</Cell>)}</Row>
              <Row label="Projected outcome">
                {selected.map((p) => <Cell key={p.playerId}>{p.projectedOutcome}</Cell>)}
              </Row>
              <Row label="Projected value">
                {selected.map((p) => <Cell key={p.playerId}>{num(p.projectedValue)}</Cell>)}
              </Row>
              <Row label="Bust risk">{selected.map((p) => <Cell key={p.playerId}>{pct(p.bustRisk)}</Cell>)}</Row>

              <tr className="border-b border-line bg-ink-850">
                <Th>Components</Th>
                {selected.map((p) => <td key={p.playerId} className="border-l border-line" />)}
              </tr>
              {COMPONENT_ROWS.map((row) => (
                <Row key={row.key} label={row.label}>
                  {selected.map((p) => (
                    <Cell key={p.playerId}>{valueCell(p.scoreComponents[row.key] as number | null | undefined)}</Cell>
                  ))}
                </Row>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <td className="w-40 bg-ink-850 p-3 text-xs font-medium uppercase tracking-wider text-slate-500">{children}</td>;
}
function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <tr className="border-b border-line/60 last:border-0">
      <td className="p-3 text-xs uppercase tracking-wider text-slate-500">{label}</td>
      {children}
    </tr>
  );
}
function Cell({ children }: { children: React.ReactNode }) {
  return <td className="border-l border-line/60 p-3 text-slate-300">{children}</td>;
}

export function ComparePage() {
  return (
    <DataGate>
      {(data) =>
        data.players.length === 0 ? (
          <div className="space-y-4">
            <h1 className="text-xl font-semibold text-slate-100">Compare Players</h1>
            <EmptyState title="No players yet" message="Comparison needs scored players." showPipeline />
          </div>
        ) : (
          <CompareInner data={data} />
        )
      }
    </DataGate>
  );
}
