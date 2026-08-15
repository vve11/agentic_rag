export function CitationChips({
  citations,
  onSelect,
}: {
  citations: string[];
  onSelect?: (citation: string) => void;
}) {
  if (citations.length === 0) {
    return <span className="muted">No citations</span>;
  }

  return (
    <div className="citation-chips" aria-label="Citations">
      {citations.map((citation) => (
        <button key={citation} type="button" onClick={() => onSelect?.(citation)}>
          {citation}
        </button>
      ))}
    </div>
  );
}
