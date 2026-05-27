import { Link, useParams } from "react-router-dom";
import { DataGate } from "../components/DataGate";
import { EmptyState } from "../components/EmptyState";
import { ClassBoard } from "../components/ClassBoard";

export function ClassPage() {
  const { year } = useParams();
  const yearNum = Number(year);

  return (
    <DataGate>
      {(data) => {
        const summary = data.classes.find((c) => c.year === yearNum);
        const classPlayers = data.players.filter((p) => p.draftClass === yearNum);
        const years = data.classes.map((c) => c.year).sort((a, b) => b - a);

        return (
          <div className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Link to="/classes" className="hover:text-slate-300">
                    Classes
                  </Link>
                  <span>/</span>
                  <span>{yearNum || year}</span>
                </div>
                <h1 className="mt-1 text-xl font-semibold text-slate-100">{yearNum || year} Draft Board</h1>
                {summary && (
                  <p className="text-sm text-slate-400">
                    {summary.playerCount} players ·{" "}
                    {summary.hasOutcomes ? "backtested against NFL outcomes" : "projection only"}
                  </p>
                )}
              </div>
              {years.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {years.map((y) => (
                    <Link
                      key={y}
                      to={`/class/${y}`}
                      className={`rounded-md px-2 py-1 text-xs ${
                        y === yearNum ? "bg-ink-700 text-slate-100" : "text-slate-400 hover:bg-ink-800"
                      }`}
                    >
                      {y}
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {classPlayers.length === 0 ? (
              <EmptyState
                title={`No players for ${yearNum || year}`}
                message={
                  data.players.length === 0
                    ? "No model data has been generated yet."
                    : "This class has no scored players in the current dataset."
                }
                showPipeline={data.players.length === 0}
              />
            ) : (
              <ClassBoard players={classPlayers} />
            )}
          </div>
        );
      }}
    </DataGate>
  );
}
