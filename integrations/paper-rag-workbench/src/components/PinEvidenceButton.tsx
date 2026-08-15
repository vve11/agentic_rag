import { useState } from "react";

import { useOptionalProjectContext } from "../context/ProjectContext";
import { useI18n } from "../i18n";
import type { EvidenceChunk } from "../types";

export function PinEvidenceButton({ chunk }: { chunk: EvidenceChunk }) {
  const { t } = useI18n();
  const project = useOptionalProjectContext();
  const [pinned, setPinned] = useState(
    Boolean(project?.activeProject?.evidence.some((pin) => pin.chunk_id === chunk.chunk_id)),
  );

  if (!project?.activeProjectId) return null;

  const pin = async () => {
    await project.pinEvidence({
      chunk_id: chunk.chunk_id,
      paper_id: chunk.paper_id,
      quote_snapshot: chunk.snippet ?? chunk.text ?? "",
      source: "search",
      score_snapshot: chunk.score,
    });
    setPinned(true);
  };

  return (
    <button
      type="button"
      onClick={pin}
      disabled={pinned}
      aria-label={t("pin.pinEvidenceAria", { id: chunk.chunk_id })}
    >
      {pinned ? t("pin.pinned") : t("pin.pinEvidence")}
    </button>
  );
}
