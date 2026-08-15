export function App() {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <h1>Paper RAG</h1>
        <nav>
          {["Overview", "Library", "Search", "Ask", "Discover", "DSH Chat"].map((item) => (
            <button key={item} type="button">
              {item}
            </button>
          ))}
        </nav>
      </aside>
      <section className="workspace">
        <h2>Paper RAG Workbench</h2>
        <p>Corpus overview loading through fixture mode.</p>
      </section>
    </main>
  );
}
