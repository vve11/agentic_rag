const SIDE_EFFECTS = [
  "write indexed paper and chunks",
  "update the configured Paper RAG corpus",
  "record ingestion metadata",
];

export function ApprovalDialog({
  open,
  candidateIds,
  onCancel,
  onApprove,
}: {
  open: boolean;
  candidateIds: number[];
  onCancel: () => void;
  onApprove: () => void;
}) {
  if (!open) return null;

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal" role="dialog" aria-modal="true" aria-label="Approve candidate ingest">
        <h3>Approve candidate ingest</h3>
        <p>Candidate ids: {candidateIds.join(", ")}</p>
        <ul>
          {SIDE_EFFECTS.map((effect) => (
            <li key={effect}>{effect}</li>
          ))}
        </ul>
        <div className="row-actions">
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="primary" onClick={onApprove}>
            Approve ingest
          </button>
        </div>
      </section>
    </div>
  );
}

export const candidateIngestSideEffects = SIDE_EFFECTS;
