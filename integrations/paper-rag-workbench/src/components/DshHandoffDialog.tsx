import type { DshHandoffData } from "../types";

export function DshHandoffDialog({
  data,
  onClose,
}: {
  data: DshHandoffData;
  onClose: () => void;
}) {
  const copy = async () => {
    await navigator.clipboard?.writeText(data.prompt);
  };

  return (
    <div className="dialog-backdrop">
      <section className="handoff-dialog" role="dialog" aria-label="Send to DSH">
        <header>
          <h3>Send to DSH</h3>
          <button type="button" onClick={onClose} aria-label="Close DSH handoff">
            Close
          </button>
        </header>
        <pre>{data.prompt}</pre>
        <footer>
          <button type="button" onClick={copy}>
            Copy prompt
          </button>
          <a href={data.dsh_url} target="_blank" rel="noreferrer">
            Open DSH
          </a>
        </footer>
      </section>
    </div>
  );
}
