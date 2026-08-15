import { useMemo, useState } from "react";

import { createWorkbenchClient } from "./api/client";
import { Shell, type RouteId } from "./components/Shell";
import { LibraryPage } from "./pages/LibraryPage";
import { OverviewPage } from "./pages/OverviewPage";

export function App() {
  const [route, setRoute] = useState<RouteId>("overview");
  const client = useMemo(() => createWorkbenchClient(), []);

  return (
    <Shell active={route} onNavigate={setRoute}>
      {route === "library" ? <LibraryPage client={client} /> : <OverviewPage client={client} />}
    </Shell>
  );
}
