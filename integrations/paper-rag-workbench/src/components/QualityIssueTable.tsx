import type { HealthSample } from "../types";

export function QualityIssueTable({ samples }: { samples: HealthSample[] }) {
  if (samples.length === 0) {
    return <p className="muted">No quality samples detected.</p>;
  }
  return (
    <table className="quality-table">
      <thead>
        <tr>
          <th>Kind</th>
          <th>Paper</th>
          <th>Chunks</th>
          <th>Preview</th>
        </tr>
      </thead>
      <tbody>
        {samples.map((sample, index) => (
          <tr key={`${sample.kind}-${sample.chunk_id || sample.chunk_ids?.join("-") || index}`}>
            <td>{sample.kind}</td>
            <td>{sample.paper_id || "unknown"}</td>
            <td>{sample.chunk_id || sample.chunk_ids?.join(", ") || "unknown"}</td>
            <td>{sample.preview || sample.warnings?.join(", ") || ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
