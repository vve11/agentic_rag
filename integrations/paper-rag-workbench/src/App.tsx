import { useMemo, useState } from "react";

import { createWorkbenchClient } from "./api/client";
import { Shell, type RouteId } from "./components/Shell";
import { I18nProvider } from "./i18n";
import { AskPage } from "./pages/AskPage";
import { DiscoverPage } from "./pages/DiscoverPage";
import { HealthPage } from "./pages/HealthPage";
import { LibraryPage } from "./pages/LibraryPage";
import { OverviewPage } from "./pages/OverviewPage";
import { SearchPage } from "./pages/SearchPage";

export function App() {
  const [route, setRoute] = useState<RouteId>("overview");
  const client = useMemo(() => createWorkbenchClient(), []);

  return (
    <I18nProvider>
      <Shell active={route} onNavigate={setRoute}>
        {route === "health" ? <HealthPage client={client} /> : null}
        {route === "library" ? <LibraryPage client={client} /> : null}
        {route === "search" ? <SearchPage client={client} /> : null}
        {route === "ask" ? <AskPage client={client} /> : null}
        {route === "discover" ? <DiscoverPage client={client} /> : null}
        {route === "overview" ? <OverviewPage client={client} /> : null}
      </Shell>
    </I18nProvider>
  );
}
