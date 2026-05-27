import { NavLink, Outlet } from "react-router-dom";
import { useDataState } from "../lib/data";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/classes", label: "Classes", end: false },
  { to: "/positions", label: "Positions", end: false },
  { to: "/compare", label: "Compare", end: false },
  { to: "/model", label: "Model Lab", end: false },
  { to: "/data", label: "Data Health", end: false },
];

function DataStatus() {
  const state = useDataState();
  if (state.status === "loading") {
    return <span className="text-xs text-slate-500">loading…</span>;
  }
  if (state.status === "error") {
    return <span className="text-xs text-tier-risk">data error</span>;
  }
  const ready = state.data.manifest.dataReady;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs ${ready ? "text-tier-elite" : "text-tier-low"}`}
      title={ready ? "Model data loaded" : "No data generated yet — showing empty states"}
    >
      <span className={`h-2 w-2 rounded-full ${ready ? "bg-tier-elite" : "bg-tier-low"}`} />
      {ready ? `v${state.data.manifest.modelVersion}` : "no data"}
    </span>
  );
}

export function Layout() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-ink-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/20 text-accent">
              ◑
            </span>
            <span className="text-sm font-bold tracking-tight text-slate-100">
              Draft<span className="text-accent">Lens</span>
            </span>
          </NavLink>
          <nav className="flex flex-1 items-center gap-1 overflow-x-auto">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-md px-3 py-1.5 text-sm transition-colors ${
                    isActive
                      ? "bg-ink-700 text-slate-100"
                      : "text-slate-400 hover:bg-ink-800 hover:text-slate-200"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <DataStatus />
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        <Outlet />
      </main>

      <footer className="border-t border-line px-4 py-4 text-center text-xs text-slate-600">
        DraftLens — model outputs are transparent and backtested. Not affiliated with the NFL.
      </footer>
    </div>
  );
}
