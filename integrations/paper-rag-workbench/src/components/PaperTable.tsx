import type { PaperSummary } from "../types";

export function PaperTable({
  papers,
  onAsk,
  onSearch,
  onSection,
}: {
  papers: PaperSummary[];
  onAsk: (paper: PaperSummary) => void;
  onSearch: (paper: PaperSummary) => void;
  onSection: (paper: PaperSummary) => void;
}) {
  if (papers.length === 0) {
    return (
      <div className="table-empty" role="status">
        No indexed papers match this filter.
      </div>
    );
  }

  return (
    <div className="table-frame">
      <table className="data-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Paper ID</th>
            <th>arXiv</th>
            <th>Chunks</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {papers.map((paper) => (
            <tr key={paper.paper_id}>
              <td>{paper.title}</td>
              <td>
                <code>{paper.paper_id}</code>
              </td>
              <td>{paper.arxiv_id || ""}</td>
              <td>{paper.chunk_count ?? 0}</td>
              <td className="row-actions">
                <button type="button" aria-label={`Ask ${paper.title}`} onClick={() => onAsk(paper)}>
                  Ask
                </button>
                <button type="button" aria-label={`Search ${paper.title}`} onClick={() => onSearch(paper)}>
                  Search
                </button>
                <button
                  type="button"
                  aria-label={`Open section ${paper.title}`}
                  onClick={() => onSection(paper)}
                >
                  Section
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
