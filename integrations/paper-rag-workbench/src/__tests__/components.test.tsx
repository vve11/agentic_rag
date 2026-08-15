import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { AnswerPanel } from "../components/AnswerPanel";
import { CitationChips } from "../components/CitationChips";
import { EvidenceChunkCard } from "../components/EvidenceChunkCard";
import { PaperTable } from "../components/PaperTable";
import type { PaperSummary } from "../types";

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
