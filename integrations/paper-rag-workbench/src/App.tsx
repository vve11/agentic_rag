import { useMemo, useState } from "react";

import { createWorkbenchClient } from "./api/client";
import { Shell, type RouteId } from "./components/Shell";
import { AskPage } from "./pages/AskPage";
import { LibraryPage } from "./pages/LibraryPage";
import { OverviewPage } from "./pages/OverviewPage";
import { SearchPage } from "./pages/SearchPage";

export function App() {
  const [route, setRoute] = useState<RouteId>("overview");
  const client = useMemo(() => createWorkbenchClient(), []);

  return (
    <Shell active={route} onNavigate={setRoute}>
      {route === "library" ? <LibraryPage client={client} /> : null}
      {route === "search" ? <SearchPage client={client} /> : null}
      {route === "ask" ? <AskPage client={client} /> : null}
      {route === "overview" || route === "discover" ? <OverviewPage client={client} /> : null}
    </Shell>
  );
}
