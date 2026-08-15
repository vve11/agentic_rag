import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "../components/EmptyState";
import { PaperTable } from "../components/PaperTable";
import type { EvidenceChunk, PaperSummary, WorkbenchClient } from "../types";

export function LibraryPage({ client }: { client: WorkbenchClient }) {
  const [papers, setPapers] = useState<PaperSummary[] | null>(null);
  const [filter, setFilter] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [sectionPaper, setSectionPaper] = useState<PaperSummary | null>(null);
  const [sectionChunks, setSectionChunks] = useState<EvidenceChunk[]>([]);
  const [sectionLoading, setSectionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    client
      .papers(50)
      .then((envelope) => {
        if (!active) return;
        if (!envelope.ok || !envelope.data) {
          setError(envelope.error?.message ?? "Library is unavailable.");
          return;
        }
        setPapers(envelope.data.papers);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "Library is unavailable.");
      });

    return () => {
      active = false;
    };
  }, [client]);

  const filteredPapers = useMemo(() => {
    const normalized = filter.trim().toLowerCase();
    if (!papers || !normalized) return papers ?? [];

    return papers.filter((paper) =>
      [paper.title, paper.paper_id, paper.arxiv_id ?? ""].some((value) =>
        value.toLowerCase().includes(normalized),
      ),
    );
  }, [filter, papers]);

  const openSection = async (paper: PaperSummary) => {
    setMessage(null);
    setSectionPaper(paper);
    setSectionLoading(true);
    setSectionChunks([]);

    const envelope = await client.section({
      paper_id: paper.paper_id,
      section_name: "introduction",
    });

    if (!envelope.ok || !envelope.data) {
      setMessage(envelope.error?.message ?? "Section is unavailable.");
      setSectionLoading(false);
      return;
    }

    setSectionChunks(envelope.data.chunks);
    setSectionLoading(false);
  };

  if (error) {
    return <EmptyState title="Library unavailable" detail={error} />;
  }

  if (!papers) {
    return <p className="loading">Loading library...</p>;
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h2>Library</h2>
          <p>Inspect indexed papers and open source sections without writing to the corpus.</p>
        </div>
        <label className="filter-field">
          <span>Filter papers</span>
          <input value={filter} onChange={(event) => setFilter(event.target.value)} />
        </label>
      </header>
      <PaperTable
        papers={filteredPapers}
        onAsk={(paper) => setMessage(`Ask is ready for ${paper.title}.`)}
        onSearch={(paper) => setMessage(`Search is ready for ${paper.title}.`)}
        onSection={openSection}
      />
      {message ? <p className="inline-message">{message}</p> : null}
      {sectionPaper ? (
        <aside className="section-drawer" aria-label="Paper section">
          <div>
            <span>{sectionPaper.paper_id}</span>
            <h3>Introduction</h3>
          </div>
          {sectionLoading ? (
            <p className="loading">Loading section...</p>
          ) : (
            <div className="section-chunks">
              {sectionChunks.map((chunk) => (
                <article key={chunk.chunk_id}>
                  <span>{chunk.page ? `p${chunk.page}` : "source"}</span>
                  <p>{chunk.snippet ?? chunk.text}</p>
                </article>
              ))}
            </div>
          )}
        </aside>
      ) : null}
    </>
  );
}
