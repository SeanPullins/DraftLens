import type { ReactNode } from "react";
import { useDataState, type DraftLensData } from "../lib/data";

interface Props {
  children: (data: DraftLensData) => ReactNode;
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-24 text-slate-500">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-ink-600 border-t-accent" />
      <span className="ml-3 text-sm">Loading model data…</span>
    </div>
  );
}

export function DataGate({ children }: Props) {
  const state = useDataState();
  if (state.status === "loading") return <Spinner />;
  if (state.status === "error") {
    return (
      <div className="mx-auto max-w-lg rounded-xl border border-tier-risk/40 bg-tier-risk/10 p-6 text-center">
        <h3 className="text-sm font-semibold text-tier-risk">Could not load model data</h3>
        <p className="mt-2 text-sm text-slate-300">{state.error}</p>
        <p className="mt-2 text-xs text-slate-500">
          The site expects JSON under <code>public/data/model/</code>.
        </p>
      </div>
    );
  }
  return <>{children(state.data)}</>;
}
