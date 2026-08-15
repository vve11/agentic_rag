import type { Candidate } from "../types";

export function CandidateTable({
  candidates,
  selectedIds,
  onToggle,
}: {
  candidates: Candidate[];
  selectedIds: number[];
  onToggle: (id: number) => void;
}) {
  if (candidates.length === 0) {
    return (
      <div className="table-empty" role="status">
        No discovery candidates returned.
      </div>
    );
  }

  return (
    <div className="table-frame">
      <table className="data-table">
        <thead>
          <tr>
            <th>Select</th>
            <th>Candidate</th>
            <th>Source</th>
            <th>Rank</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => (
            <tr key={candidate.id} className={selectedIds.includes(candidate.id) ? "selected-row" : ""}>
              <td>
                <input
                  aria-label={`Select candidate ${candidate.id}`}
                  checked={selectedIds.includes(candidate.id)}
                  type="checkbox"
                  onChange={() => onToggle(candidate.id)}
                />
              </td>
              <td>
                <strong>{candidate.title}</strong>
                <div className="muted">id {candidate.id}</div>
                <div>{candidate.rank_reason ?? candidate.reason ?? ""}</div>
              </td>
              <td>{candidate.source ?? ""}</td>
              <td>{candidate.rank ?? ""}</td>
              <td>Candidate-only; not answer evidence</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
