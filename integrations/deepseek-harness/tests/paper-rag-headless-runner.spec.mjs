import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, test, vi } from "vitest";

import { run } from "../src/paper-rag-headless-runner.mjs";

const integrationRoot = fileURLToPath(new URL("..", import.meta.url));

describe("Paper RAG live headless runner", () => {
  test("live patch replaces the stock headless runner with the Paper RAG preset runner", async () => {
    const patch = await readFile(resolve(integrationRoot, "live-headless.patch.yml"), "utf8");

    expect(patch).toContain("id: headless-runner");
    expect(patch).toContain("disabled: true");
    expect(patch).toContain("id: paper-rag-headless-runner");
    expect(patch).toContain("name: ./src/paper-rag-headless-runner.mjs");
    expect(patch).toContain("preset: paper-research");
  });

  test("mounts paper-research before publishing the one-shot agent", async () => {
    const agentCtx = {};
    const session = {
      seq: 1,
      events: [
        { seq: 1, type: "turn/start", data: { turn: 1 } },
        {
          seq: 2,
          type: "assistant/message",
          data: { message: { content: [{ type: "text", text: "done" }] } },
        },
        { seq: 3, type: "turn/end", data: { reason: { kind: "completed" } } },
      ],
    };
    const agent = {
      ctx: agentCtx,
      session,
      followup: vi.fn(),
      whenIdle: vi.fn().mockResolvedValue(undefined),
    };
    const mount = vi.fn().mockResolvedValue({ id: "paper-research" });
    const flush = vi.fn().mockResolvedValue(undefined);
    const create = vi.fn(async (options) => {
      await options.setup(agentCtx);
      return { agent };
    });
    const stdout = { write: vi.fn() };
    const stderr = { write: vi.fn() };
    const exit = vi.fn();
    const ctx = {
      get(name) {
        return {
          agentDefaultModel: {
            currentSelection: () => ({
              provider: "deepseek-official",
              model: "deepseek-v4-flash",
            }),
          },
          agentPresets: { mount },
          agents: { create },
          sessions: { flush },
        }[name];
      },
    };

    await run(ctx, { task: "answer from paper_qa", preset: "paper-research" }, { stdout, stderr, exit });

    expect(create).toHaveBeenCalledWith(
      expect.objectContaining({
        meta: expect.objectContaining({ agentPreset: "paper-research" }),
        agentOptions: {
          provider: "deepseek-official",
          model: "deepseek-v4-flash",
        },
      }),
    );
    expect(mount).toHaveBeenCalledWith(agentCtx, "paper-research");
    expect(agent.followup).toHaveBeenCalledWith(
      expect.objectContaining({
        content: [{ type: "text", text: "answer from paper_qa" }],
        source: { kind: "user" },
      }),
    );
    expect(flush).toHaveBeenCalledWith(session);
    expect(stdout.write).toHaveBeenCalledWith("done\n");
    expect(stderr.write).not.toHaveBeenCalled();
    expect(exit).toHaveBeenCalledWith(0);
  });
});
