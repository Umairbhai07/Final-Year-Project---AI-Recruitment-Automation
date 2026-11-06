import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useEffect, useState } from "react";

/**
 * Thin moving bar at the top of the window while a page is loading data for the first time or something is being
 * saved, so a click always gets an immediate visible response. Quiet background refreshes don't show it.
 */
export function TopProgress() {
  const loading = useIsFetching({ predicate: (q) => q.state.data === undefined });
  const saving = useIsMutating();
  const busy = loading + saving > 0;
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!busy) return setShown(false);
    const t = window.setTimeout(() => setShown(true), 120); // skip the bar for answers that come back at once
    return () => window.clearTimeout(t);
  }, [busy]);
  if (!shown) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-[100] h-[3px] overflow-hidden bg-brand-100/60" role="progressbar" aria-label="Loading">
      <div className="h-full w-2/5 animate-progress rounded-full bg-neutral-950" />
    </div>
  );
}
