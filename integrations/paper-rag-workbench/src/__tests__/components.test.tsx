import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { ApprovalDialog } from "../components/ApprovalDialog";
import { AgentTimeline } from "../components/AgentTimeline";
import { AnswerPanel } from "../components/AnswerPanel";
import { CandidateTable } from "../components/CandidateTable";
import { ChunkDetailPanel } from "../components/ChunkDetailPanel";
import { CitationChips } from "../components/CitationChips";
import { DshHandoffDialog } from "../components/DshHandoffDialog";
import { EvidenceChunkCard } from "../components/EvidenceChunkCard";
import { HealthSummary } from "../components/HealthSummary";
import { PaperDetailPanel } from "../components/PaperDetailPanel";
import { PaperTable } from "../components/PaperTable";
import { QualityIssueTable } from "../components/QualityIssueTable";
import { ScoreBreakdown } from "../components/ScoreBreakdown";
import { Shell } from "../components/Shell";
import { renderWithI18n } from "../test/render";
import {
  chunkDetailFixture,
  dshHandoffFixture,
  indexHealthFixture,
  paperDetailFixture,
  qaStreamFixture,
} from "../api/fixtures";
import type { PaperSummary } from "../types";

describe("Shell", () => {
  test("renders Chinese navigation by default", () => {
    window.localStorage.clear();

    renderWithI18n(
      <Shell active="overview" onNavigate={vi.fn()}>
        <p>body</p>
      </Shell>,
    );

    expect(screen.getByRole("navigation", { name: "工作台导航" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "概览" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "健康检查" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "DSH 对话" })).toBeInTheDocument();
  });

  test("language toggle switches navigation to English", async () => {
    window.localStorage.clear();
    const user = userEvent.setup();

    renderWithI18n(
      <Shell active="overview" onNavigate={vi.fn()}>
        <p>body</p>
      </Shell>,
    );

    await user.click(screen.getByRole("button", { name: "EN" }));

    expect(screen.getByRole("navigation", { name: "Workbench navigation" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Overview" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("button", { name: "中" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "EN" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("PaperTable", () => {
  test("renders indexed papers and dispatches row actions with the selected paper", async () => {
    const user = userEvent.setup();
    const paper: PaperSummary = {
      paper_id: "arxiv:2310.11511",
      title: "Self-RAG",
      arxiv_id: "2310.11511",
      chunk_count: 58,
    };
    const onAsk = vi.fn();
    const onSearch = vi.fn();
    const onSection = vi.fn();

    render(
      <PaperTable
        papers={[paper]}
        onAsk={onAsk}
        onSearch={onSearch}
        onSection={onSection}
      />,
    );

    expect(screen.getByText("Self-RAG")).toBeInTheDocument();
    expect(screen.getByText("arxiv:2310.11511")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /ask self-rag/i }));
    await user.click(screen.getByRole("button", { name: /search self-rag/i }));
    await user.click(screen.getByRole("button", { name: /open section self-rag/i }));

    expect(onAsk).toHaveBeenCalledWith(paper);
    expect(onSearch).toHaveBeenCalledWith(paper);
    expect(onSection).toHaveBeenCalledWith(paper);
  });
});

describe("Evidence components", () => {
  test("EvidenceChunkCard shows safe chunk metadata", () => {
    render(
      <EvidenceChunkCard
        chunk={{
          chunk_id: "c1",
          paper_id: "p1",
          title: "Paper",
          page: 3,
          text: "bounded evidence text",
        }}
      />,
    );

    expect(screen.getByText("Paper")).toBeInTheDocument();
    expect(screen.getByText("p1")).toBeInTheDocument();
    expect(screen.getByText("Page 3")).toBeInTheDocument();
    expect(screen.getByText("chunk:c1")).toBeInTheDocument();
  });

  test("CitationChips dispatches selected citation ids", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    render(<CitationChips citations={["c1", "c2"]} onSelect={onSelect} />);

    await user.click(screen.getByRole("button", { name: "c2" }));

    expect(onSelect).toHaveBeenCalledWith("c2");
  });

  test("AnswerPanel shows citation chips and evidence", () => {
    render(
      <AnswerPanel
        answer="Self-RAG critiques generations."
        citations={["c1"]}
        chunks={[{ chunk_id: "c1", paper_id: "p1", text: "reflection tokens" }]}
        abstain={{ decision: "answer" }}
      />,
    );

    expect(screen.getByText(/critiques generations/i)).toBeInTheDocument();
    expect(screen.getByText("c1")).toBeInTheDocument();
    expect(screen.getByText(/reflection tokens/i)).toBeInTheDocument();
  });
});

describe("Discovery approval components", () => {
  test("CandidateTable labels candidates as non-evidence", () => {
    render(
      <CandidateTable
        candidates={[
          {
            id: 11,
            title: "Candidate Paper",
            source: "arxiv",
            rank: 1,
            evidence_role: "discovery_only_not_answer_evidence",
          },
        ]}
        selectedIds={[]}
        onToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("Candidate Paper")).toBeInTheDocument();
    expect(screen.getByText(/not answer evidence/i)).toBeInTheDocument();
  });

  test("ApprovalDialog names side effects before approval", () => {
    render(
      <ApprovalDialog
        open
        candidateIds={[11]}
        onCancel={vi.fn()}
        onApprove={vi.fn()}
      />,
    );

    expect(screen.getByText(/candidate ids: 11/i)).toBeInTheDocument();
    expect(screen.getByText(/write indexed paper and chunks/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve ingest/i })).toBeInTheDocument();
  });
});

describe("Health diagnostics components", () => {
  test("health summary distinguishes degraded services", () => {
    render(<HealthSummary data={indexHealthFixture} />);

    expect(screen.getByRole("heading", { name: /index health/i })).toBeInTheDocument();
    expect(screen.getByText(/degraded/i)).toBeInTheDocument();
    expect(screen.getByText(/sparse fallback/i)).toBeInTheDocument();
    expect(screen.getByText("deepseek-v4-flash")).toBeInTheDocument();
  });

  test("quality issue table shows duplicate and parser samples", () => {
    render(<QualityIssueTable samples={indexHealthFixture.corpus_quality.samples} />);

    expect(screen.getByText(/duplicate_chunk/i)).toBeInTheDocument();
    expect(screen.getByText(/parser_artifact/i)).toBeInTheDocument();
    expect(screen.getByText(/05e56a78/)).toBeInTheDocument();
  });
});

describe("Paper and chunk drilldown components", () => {
  test("paper detail panel lists sections and chunks", () => {
    render(<PaperDetailPanel detail={paperDetailFixture} onInspectChunk={() => {}} />);

    expect(screen.getByRole("heading", { name: /Self-RAG/i })).toBeInTheDocument();
    expect(screen.getByText("Abstract")).toBeInTheDocument();
    expect(screen.getByText("Introduction")).toBeInTheDocument();
    expect(screen.getByText(/parser_artifacts_detected/i)).toBeInTheDocument();
  });

  test("chunk detail panel shows full text and neighbors", () => {
    render(<ChunkDetailPanel detail={chunkDetailFixture} onOpenPaper={() => {}} />);

    expect(screen.getByText(/critiques its own generations/i)).toBeInTheDocument();
    expect(screen.getByText(/html_comment/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open paper detail/i })).toBeInTheDocument();
  });

  test("score breakdown renders known score fields", () => {
    render(
      <ScoreBreakdown
        chunk={{
          ...chunkDetailFixture.chunk,
          score: 0.92,
          dense_score: 0.81,
          sparse_score: 0.74,
        }}
      />,
    );

    expect(screen.getByText(/score 0.92/i)).toBeInTheDocument();
    expect(screen.getByText(/dense 0.81/i)).toBeInTheDocument();
    expect(screen.getByText(/sparse 0.74/i)).toBeInTheDocument();
  });
});

describe("DSH handoff components", () => {
  test("dsh handoff dialog shows prompt and open link", () => {
    render(<DshHandoffDialog data={dshHandoffFixture} onClose={() => {}} />);

    expect(screen.getByRole("dialog", { name: /send to dsh/i })).toBeInTheDocument();
    expect(screen.getByText(/基于 Paper RAG Workbench/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open dsh/i })).toHaveAttribute(
      "href",
      "http://127.0.0.1:3080",
    );
  });
});

describe("Streaming timeline components", () => {
  test("agent timeline renders stage progress", () => {
    render(<AgentTimeline stages={qaStreamFixture.stages} running={false} />);

    expect(screen.getByRole("heading", { name: /agent timeline/i })).toBeInTheDocument();
    expect(screen.getByText(/Understanding question/i)).toBeInTheDocument();
    expect(screen.getByText(/Retrieved 2 chunks/i)).toBeInTheDocument();
  });
});
