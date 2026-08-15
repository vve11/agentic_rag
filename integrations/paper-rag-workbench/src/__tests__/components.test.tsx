import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

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
