import { randomUUID } from "node:crypto";

import { createUserMessage } from "@deepseek-ai/dsh-llm";
import { SessionId } from "@deepseek-ai/dsh-session";

export const name = "paper-rag-headless-runner";
export const inject = ["agentDefaultModel", "agentPresets", "agents", "sessions"];

export const internals = {
  stdout: process.stdout,
  stderr: process.stderr,
};

function normalizeConfig(config) {
  return {
    task: String(config?.task ?? ""),
    preset: String(config?.preset ?? "paper-research"),
  };
}

export function summarize(events, firstSeq) {
  let started = false;
  let text = "";
  let reason;
  for (const event of events) {
    if (event.seq < firstSeq) continue;
    if (event.type === "turn/start") {
      started = true;
      continue;
    }
    if (!started) continue;
    if (event.type === "assistant/message") {
      const joined = event.data.message.content
        .filter((block) => block.type === "text")
        .map((block) => block.text)
        .join("");
      if (joined !== "") text = joined;
    }
    if (event.type === "turn/end") reason = event.data.reason;
  }
  return { text, reason };
}

function fail(io, error) {
  io.stderr.write(`dsh: ${error instanceof Error ? error.message : String(error)}\n`);
  io.exit(1);
}

export async function run(ctx, rawConfig, io) {
  io ??= internals;
  const config = normalizeConfig(rawConfig);
  if (config.task.trim() === "") {
    throw new Error("paper-rag-headless-runner: task is required");
  }

  await ctx.get("loader")?.await();
  const agents = ctx.get("agents");
  const defaultModel = ctx.get("agentDefaultModel");
  const agentPresets = ctx.get("agentPresets");
  const sessions = ctx.get("sessions");
  if (
    agents === undefined ||
    defaultModel === undefined ||
    agentPresets === undefined ||
    sessions === undefined
  ) {
    return;
  }

  const selection = defaultModel.currentSelection();
  const { agent } = await agents.create({
    sessionId: SessionId(`session-${randomUUID()}`),
    meta: { cwd: process.cwd(), agentPreset: config.preset },
    agentOptions: {
      provider: selection.provider,
      model: selection.model,
    },
    setup: async (agentCtx) => {
      await agentPresets.mount(agentCtx, config.preset);
    },
  });

  await agent.whenIdle();
  const firstSeq = agent.session.seq;
  agent.followup(
    createUserMessage({
      content: [
        {
          type: "text",
          text: config.task,
        },
      ],
      source: { kind: "user" },
    }),
  );
  await agent.whenIdle();
  await sessions.flush(agent.session);
  const outcome = summarize(agent.session.events, firstSeq);
  io.stdout.write(`${outcome.text}\n`);
  if (outcome.reason?.kind === "error") {
    io.stderr.write(`dsh: ${outcome.reason.error.code}: ${outcome.reason.error.message}\n`);
  }
  io.exit(outcome.reason?.kind === "completed" ? 0 : 1);
}

export function apply(ctx, config) {
  const exit = ctx.get("appExit");
  if (exit === undefined) {
    throw new Error("paper-rag-headless-runner: the launcher must provide ctx.appExit");
  }
  const io = {
    stdout: internals.stdout,
    stderr: internals.stderr,
    exit,
  };
  run(ctx, config, io).catch((error) => {
    fail(io, error);
  });
}
