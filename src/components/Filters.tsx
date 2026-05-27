import type { BoardFilters } from "../lib/filters";
import { TIER_ORDER } from "../lib/scoring";

interface Props {
  filters: BoardFilters;
  onChange: (next: BoardFilters) => void;
  positions: string[];
  schools: string[];
  resultCount: number;
  totalCount: number;
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wider text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-line bg-ink-800 px-2 py-1.5 text-sm text-slate-200 focus:border-accent focus:outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Filters({ filters, onChange, positions, schools, resultCount, totalCount }: Props) {
  const set = (patch: Partial<BoardFilters>) => onChange({ ...filters, ...patch });

  return (
    <div className="sticky top-[57px] z-20 -mx-4 mb-4 border-b border-line bg-ink-950/90 px-4 py-3 backdrop-blur">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-1 flex-col gap-1" style={{ minWidth: 180 }}>
          <span className="text-[11px] uppercase tracking-wider text-slate-500">Search</span>
          <input
            value={filters.search}
            onChange={(e) => set({ search: e.target.value })}
            placeholder="Player, school, position…"
            className="rounded-md border border-line bg-ink-800 px-3 py-1.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-accent focus:outline-none"
          />
        </label>

        <Select
          label="Position"
          value={filters.position}
          onChange={(v) => set({ position: v })}
          options={[{ value: "ALL", label: "All positions" }, ...positions.map((p) => ({ value: p, label: p }))]}
        />
        <Select
          label="School"
          value={filters.school}
          onChange={(v) => set({ school: v })}
          options={[{ value: "ALL", label: "All schools" }, ...schools.map((s) => ({ value: s, label: s }))]}
        />
        <Select
          label="Tier"
          value={filters.tier}
          onChange={(v) => set({ tier: v })}
          options={[{ value: "ALL", label: "All tiers" }, ...TIER_ORDER.map((t) => ({ value: t, label: t }))]}
        />

        <label className="flex flex-col gap-1">
          <span className="text-[11px] uppercase tracking-wider text-slate-500">Pick range</span>
          <div className="flex items-center gap-1">
            <input
              type="number"
              min={1}
              value={filters.minPick ?? ""}
              onChange={(e) => set({ minPick: e.target.value ? Number(e.target.value) : null })}
              placeholder="min"
              className="w-16 rounded-md border border-line bg-ink-800 px-2 py-1.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-accent focus:outline-none"
            />
            <span className="text-slate-600">–</span>
            <input
              type="number"
              min={1}
              value={filters.maxPick ?? ""}
              onChange={(e) => set({ maxPick: e.target.value ? Number(e.target.value) : null })}
              placeholder="max"
              className="w-16 rounded-md border border-line bg-ink-800 px-2 py-1.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-accent focus:outline-none"
            />
          </div>
        </label>

        <div className="ml-auto pb-1 text-xs text-slate-500">
          <span className="font-semibold text-slate-300">{resultCount}</span> / {totalCount}
        </div>
      </div>
    </div>
  );
}
