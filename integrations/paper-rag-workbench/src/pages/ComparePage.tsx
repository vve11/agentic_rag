import { useState } from "react";

import { CompareMatrix } from "../components/CompareMatrix";
import { DshHandoffDialog } from "../components/DshHandoffDialog";
import { EmptyState } from "../components/EmptyState";
import { useProjectContext } from "../context/ProjectContext";
import { useI18n, type MessageKey } from "../i18n";
import type { CompareRun, DshHandoffData, WorkbenchClient } from "../types";

const dimensions = [
  { id: "method", labelKey: "compare.method" },
  { id: "limitation", labelKey: "compare.limitation" },
  { id: "contribution", labelKey: "compare.contribution" },
  { id: "dataset", labelKey: "compare.dataset" },
  { id: "experiment", labelKey: "compare.experiment" },
  { id: "evidence_strength", labelKey: "compare.evidenceStrength" },
] as const satisfies readonly { id: string; labelKey: MessageKey }[];

export function ComparePage({ client }: { client: WorkbenchClient }) {
  const { t } = useI18n();
  const { activeProject, activeProjectId, refreshActiveProject } = useProjectContext();
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [run, setRun] = useState<CompareRun | null>(null);
  const [handoff, setHandoff] = useState<DshHandoffData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggleDimension = (dimension: string) => {
    setSelectedDimensions((current) =>
      current.includes(dimension)
        ? current.filter((item) => item !== dimension)
        : [...current, dimension],
    );
  };

  const createCompare = async () => {
    if (!activeProjectId || !activeProject) return;
    setError(null);
    const result = await client.createCompareRun(activeProjectId, {
      paper_ids: activeProject.papers.map((paper) => paper.paper_id),
      dimensions: selectedDimensions.length ? selectedDimensions : ["method"],
    });
    setRun(result.run);
    await refreshActiveProject();
  };

  const sendToDsh = async () => {
    if (!activeProjectId || !run) return;
    setHandoff(await client.compareDshHandoff(activeProjectId, run.run_id));
  };

  return (
    <>
      <header className="page-header">
        <div>
          <h2>{t("compare.title")}</h2>
          <p>{t("compare.subtitle")}</p>
        </div>
      </header>
      {!activeProject ? <EmptyState title={t("workspace.noProject")} detail={t("workspace.empty")} /> : null}
      {activeProject ? (
        <section className="panel form-grid">
          <fieldset>
            <legend>{t("compare.dimensions")}</legend>
            <div className="checkbox-grid">
              {dimensions.map((dimension) => (
                <label key={dimension.id}>
                  <input
                    type="checkbox"
                    checked={selectedDimensions.includes(dimension.id)}
                    onChange={() => toggleDimension(dimension.id)}
                  />
                  <span>{t(dimension.labelKey)}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <section>
            <h3>{t("compare.papers")}</h3>
            <ul className="plain-list">
              {activeProject.papers.map((paper) => (
                <li key={paper.paper_id}>
                  <code>{paper.paper_id}</code>
                  <span>{paper.title_snapshot}</span>
                </li>
              ))}
            </ul>
          </section>
          <button type="button" onClick={createCompare}>
            {t("compare.run")}
          </button>
        </section>
      ) : null}
      {error ? <EmptyState title={t("compare.title")} detail={error} /> : null}
      {run ? (
        <>
          <div className="toolbar-row">
            <button type="button" onClick={sendToDsh}>
              {t("compare.sendToDsh")}
            </button>
          </div>
          <CompareMatrix run={run} />
        </>
      ) : null}
      {handoff ? <DshHandoffDialog data={handoff} onClose={() => setHandoff(null)} /> : null}
    </>
  );
}
