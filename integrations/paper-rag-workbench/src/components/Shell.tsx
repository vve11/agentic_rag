import { Activity, BookOpen, Compass, Database, MessageSquare, Search, Sparkles } from "lucide-react";
import type { ReactNode } from "react";

const nav = [
  { id: "overview", label: "Overview", icon: Database },
  { id: "health", label: "Health", icon: Activity },
  { id: "library", label: "Library", icon: BookOpen },
  { id: "search", label: "Search", icon: Search },
  { id: "ask", label: "Ask", icon: MessageSquare },
  { id: "discover", label: "Discover", icon: Compass },
  { id: "dsh", label: "DSH Chat", icon: Sparkles },
] as const;

export type RouteId = (typeof nav)[number]["id"];

export function Shell({
  active,
  onNavigate,
  children,
}: {
  active: RouteId;
  onNavigate: (route: RouteId) => void;
  children: ReactNode;
}) {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <h1>Paper RAG</h1>
        <nav aria-label="Workbench navigation">
          {nav.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              aria-current={active === id ? "page" : undefined}
              className={active === id ? "active" : ""}
              onClick={() => {
                if (id === "dsh") {
                  window.open("http://127.0.0.1:3080", "_blank", "noopener,noreferrer");
                  return;
                }
                onNavigate(id);
              }}
            >
              <Icon aria-hidden="true" size={17} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>
      <section className="workspace">{children}</section>
    </main>
  );
}
