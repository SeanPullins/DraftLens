import { useEffect, useState } from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { DataContext, loadDraftLensData, type LoadState } from "./lib/data";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { ClassesPage } from "./pages/ClassesPage";
import { ClassPage } from "./pages/ClassPage";
import { PositionsPage } from "./pages/PositionsPage";
import { ComparePage } from "./pages/ComparePage";
import { ModelLabPage } from "./pages/ModelLabPage";
import { DataHealthPage } from "./pages/DataHealthPage";
import { PlayerDrawer } from "./components/PlayerDrawer";

export function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let live = true;
    loadDraftLensData()
      .then((data) => live && setState({ status: "ready", data }))
      .catch((err) => live && setState({ status: "error", error: String(err?.message ?? err) }));
    return () => {
      live = false;
    };
  }, []);

  return (
    <DataContext.Provider value={state}>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="classes" element={<ClassesPage />} />
            <Route path="class/:year" element={<ClassPage />} />
            <Route path="positions" element={<PositionsPage />} />
            <Route path="positions/:group" element={<PositionsPage />} />
            <Route path="compare" element={<ComparePage />} />
            <Route path="model" element={<ModelLabPage />} />
            <Route path="data" element={<DataHealthPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
        <PlayerDrawer />
      </HashRouter>
    </DataContext.Provider>
  );
}
