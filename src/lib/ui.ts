import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

// Opening a player sets ?player=<id> on the current route; the globally-mounted
// PlayerDrawer reads it. Keeps detail views shareable and back-button friendly.
export function useOpenPlayer(): (id: string) => void {
  const [params, setParams] = useSearchParams();
  return useCallback(
    (id: string) => {
      const next = new URLSearchParams(params);
      next.set("player", id);
      setParams(next);
    },
    [params, setParams],
  );
}
