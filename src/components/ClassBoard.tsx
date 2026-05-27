import { useMemo, useState } from "react";
import type { Player } from "../lib/types";
import {
  applyFilters,
  defaultDesc,
  EMPTY_FILTERS,
  SORT_LABELS,
  sortPlayers,
  uniqueSorted,
  type BoardFilters,
  type SortKey,
} from "../lib/filters";
import { Filters } from "./Filters";
import { ScoreBadge } from "./ScoreBadge";
import { tierStyle } from "../lib/scoring";
import { confidenceLabel, pickShort, signed, valueVsPickLabel } from "../lib/format";
import { useOpenPlayer } from "../lib/ui";

const COLUMNS: { key: SortKey; label: string; className?: string }[] = [
  { key: "draftLensScore", label: "Score" },
  { key: "confidence", label: "Conf" },
  { key: "actualPick", label: "Pick" },
  { key: "valueVsPick", label: "Value" },
];

function TierPill({ tier }: { tier: Player["tier"] }) {
  const s = tierStyle(tier);
  return <span className={`rounded border px-1.5 py-0.5 text-[11px] ${s.bg} ${s.text} ${s.border}`}>{tier}</span>;
}

function FlagDots({ player }: { player: Player }) {
  if (player.flags.length === 0) return <span className="text-slate-700">—</span>;
  return (
    <div className="flex gap-1">
      {player.flags.slice(0, 3).map((f, i) => (
        <span
          key={i}
          title={f.note ?? f.label}
          className={`rounded px-1 py-0.5 text-[10px] font-medium ${
            f.kind === "gem" || f.kind === "value"
              ? "bg-tier-elite/15 text-tier-elite"
              : f.kind === "bust" || f.kind === "injury"
                ? "bg-tier-risk/15 text-tier-risk"
                : "bg-ink-700 text-slate-400"
          }`}
        >
          {f.label}
        </span>
      ))}
    </div>
  );
}

function PlayerCard({ player, onOpen }: { player: Player; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="flex flex-col gap-3 rounded-xl border border-line bg-ink-900 p-4 text-left transition-colors hover:border-ink-500 hover:bg-ink-850"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="font-semibold text-slate-100">{player.name}</p>
          <p className="text-xs text-slate-400">
            {player.position} · {player.school}
          </p>
        </div>
        <ScoreBadge score={player.draftLensScore} />
      </div>
      <div className="flex items-center justify-between text-xs text-slate-500">
        <TierPill tier={player.tier} />
        <span>{pickShort(player) === "—" ? "Unranked pick" : `Pick ${pickShort(player)}`}</span>
      </div>
      <FlagDots player={player} />
    </button>
  );
}

interface Props {
  players: Player[];
  // Hide the class column when a board is already class-specific.
  showClassColumn?: boolean;
  defaultSort?: SortKey;
}

export function ClassBoard({ players, showClassColumn = false, defaultSort = "draftLensScore" }: Props) {
  const [filters, setFilters] = useState<BoardFilters>(EMPTY_FILTERS);
  const [sortKey, setSortKey] = useState<SortKey>(defaultSort);
  const [desc, setDesc] = useState<boolean>(defaultDesc(defaultSort));
  const [view, setView] = useState<"table" | "cards">("table");
  const openPlayer = useOpenPlayer();

  const positions = useMemo(() => uniqueSorted(players.map((p) => p.positionGroup)), [players]);
  const schools = useMemo(() => uniqueSorted(players.map((p) => p.school)), [players]);

  const filtered = useMemo(() => applyFilters(players, filters), [players, filters]);
  const sorted = useMemo(() => sortPlayers(filtered, sortKey, desc), [filtered, sortKey, desc]);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setDesc((d) => !d);
    else {
      setSortKey(key);
      setDesc(defaultDesc(key));
    }
  };

  const arrow = (key: SortKey) => (key === sortKey ? (desc ? " ↓" : " ↑") : "");

  return (
    <div>
      <Filters
        filters={filters}
        onChange={setFilters}
        positions={positions}
        schools={schools}
        resultCount={sorted.length}
        totalCount={players.length}
      />

      <div className="mb-3 flex items-center justify-between">
        <div className="inline-flex overflow-hidden rounded-md border border-line text-xs">
          {(["table", "cards"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-1.5 capitalize ${
                view === v ? "bg-ink-700 text-slate-100" : "text-slate-400 hover:bg-ink-800"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500 sm:hidden">
          <label>Sort</label>
          <select
            value={sortKey}
            onChange={(e) => toggleSort(e.target.value as SortKey)}
            className="rounded-md border border-line bg-ink-800 px-2 py-1 text-slate-200"
          >
            {Object.entries(SORT_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {sorted.length === 0 ? (
        <p className="rounded-lg border border-line bg-ink-900 p-8 text-center text-sm text-slate-500">
          No players match these filters.
        </p>
      ) : view === "cards" ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((p) => (
            <PlayerCard key={p.playerId} player={p} onOpen={() => openPlayer(p.playerId)} />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-line bg-ink-850 text-left text-xs uppercase tracking-wider text-slate-500">
                <th className="px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Player</th>
                <th className="px-3 py-2 font-medium">Pos</th>
                <th className="px-3 py-2 font-medium">School</th>
                {showClassColumn && <th className="px-3 py-2 font-medium">Class</th>}
                {COLUMNS.map((c) => (
                  <th key={c.key} className="cursor-pointer px-3 py-2 font-medium hover:text-slate-300" onClick={() => toggleSort(c.key)}>
                    {c.label}
                    {arrow(c.key)}
                  </th>
                ))}
                <th className="px-3 py-2 font-medium">Tier</th>
                <th className="px-3 py-2 font-medium">Flags</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((p, i) => (
                <tr
                  key={p.playerId}
                  onClick={() => openPlayer(p.playerId)}
                  className="cursor-pointer border-b border-line/60 transition-colors last:border-0 hover:bg-ink-850"
                >
                  <td className="px-3 py-2 tabular-nums text-slate-500">{i + 1}</td>
                  <td className="px-3 py-2">
                    <span className="font-medium text-slate-100">{p.name}</span>
                  </td>
                  <td className="px-3 py-2 text-slate-400">{p.position}</td>
                  <td className="px-3 py-2 text-slate-400">{p.school}</td>
                  {showClassColumn && <td className="px-3 py-2 tabular-nums text-slate-400">{p.draftClass}</td>}
                  <td className="px-3 py-2">
                    <ScoreBadge score={p.draftLensScore} size="sm" />
                  </td>
                  <td className="px-3 py-2 text-slate-400">{confidenceLabel(p.confidence)}</td>
                  <td className="px-3 py-2 tabular-nums text-slate-400">{pickShort(p)}</td>
                  <td
                    className={`px-3 py-2 tabular-nums ${
                      (p.valueVsPick ?? 0) > 2 ? "text-tier-elite" : (p.valueVsPick ?? 0) < -2 ? "text-tier-risk" : "text-slate-400"
                    }`}
                    title={signed(p.valueVsPick)}
                  >
                    {valueVsPickLabel(p.valueVsPick)}
                  </td>
                  <td className="px-3 py-2">
                    <TierPill tier={p.tier} />
                  </td>
                  <td className="px-3 py-2">
                    <FlagDots player={p} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
