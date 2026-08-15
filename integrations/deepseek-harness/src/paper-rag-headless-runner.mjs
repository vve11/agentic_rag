import { randomUUID } from "node:crypto";

import { createUserMessage } from "@deepseek-ai/dsh-llm";
import { SessionId } from "@deepseek-ai/dsh-session";

import { cardTypeForTool } from "./paper-rag-cards.mjs";

export const name = "paper-rag-headless-runner";
export const inject = ["agentDefaultModel", "agentPresets", "agents", "sessions"];

export const internals = {
  stdout: process.stdout,
  stderr: process.stderr,
};

const ISOLATED_APPROVAL_MODE = "isolated";
const LIVE_SMOKE_WRITE_TOOLS = new Set([
  "paper_ingest",
  "discovery_candidate_ingest",
  "paper_deliver",
]);

function normalizeConfig(config) {
  return {
    task: String(config?.task ?? ""),
    preset: String(config?.preset ?? "paper-research"),
    includeWorkflow: Boolean(config?.includeWorkflow ?? config?.reportJson),
    reportJson: Boolean(config?.reportJson),
  };
}

function isLiveG2WorkspacePath(value) {
  return (
    typeof value === "string" &&
    /(?:^|[/\\])data[/\\]index[/\\]migration-gates[/\\]live-workspaces[/\\]G2[/\\]/.test(
      value,
    )
  );
}

export function shouldAllowIsolatedSmokeApproval(req, env = process.env) {
  if (env.PAPER_RAG_DSH_HEADLESS_APPROVE_WRITES !== ISOLATED_APPROVAL_MODE) {
    return false;
  }
  if (!LIVE_SMOKE_WRITE_TOOLS.has(req?.toolName)) {
    return false;
  }
  if (typeof req?.reason !== "string" || !req.reason.includes(req.toolName)) {
    return false;
  }
  return (
    isLiveG2WorkspacePath(env.PAPER_RAG_CONFIG) &&
    isLiveG2WorkspacePath(env.PAPER_RAG_ARTIFACT_ROOT)
  );
}

export function registerIsolatedSmokeApproval(ctx, env = process.env) {
  if (env.PAPER_RAG_DSH_HEADLESS_APPROVE_WRITES !== ISOLATED_APPROVAL_MODE) {
    return () => {};
  }
  if (typeof ctx?.on !== "function") {
    return () => {};
  }
  return (
    ctx.on("approval/request", async (req, next) => {
      if (shouldAllowIsolatedSmokeApproval(req, env)) {
        return "allowed-once";
      }
      return next();
    }) ?? (() => {})
  );
}

export function summarize(events, firstSeq, options = {}) {
  let started = false;
  let text = "";
  let reason;
  const toolCalls = [];
  const cards = [];
  for (const event of events) {
    if (event.seq < firstSeq) continue;
    if (event.type === "turn/start") {
      started = true;
      continue;
    }
    if (!started) continue;
    if (event.type === "tool/call") {
      const name = event.data?.name ?? event.data?.toolName;
      if (typeof name === "string") toolCalls.push(name);
    }
    if (event.type === "tool/result") {
      const structured =
        event.data?.meta ??
        event.data?.result?.structuredContent ??
        event.data?.result?.meta ??
        event.data?.value?.structuredContent ??
        event.data?.value;
      const cardType = cardTypeForTool(structured?.tool ?? event.data?.name);
      if (cardType !== undefined) cards.push(cardType);
    }
    if (event.type === "assistant/message") {
      const joined = event.data.message.content
        .filter((block) => block.type === "text")
        .map((block) => block.text)
        .join("");
      if (joined !== "") text = joined;
    }
    if (event.type === "turn/end") reason = event.data.reason;
  }
  if (options.includeWorkflow) {
    return { text, reason, tool_calls: toolCalls, cards };
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
  const outcome = summarize(agent.session.events, firstSeq, {
    includeWorkflow: config.includeWorkflow,
  });
  if (config.reportJson) {
    io.stdout.write(`${JSON.stringify({ preset: config.preset, ...outcome }, null, 2)}\n`);
  } else {
    io.stdout.write(`${outcome.text}\n`);
  }
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
  const unregisterApproval = registerIsolatedSmokeApproval(ctx);
  const io = {
    stdout: internals.stdout,
    stderr: internals.stderr,
    exit,
  };
  ctx.effect?.(
    () => () => {
      unregisterApproval();
    },
    "paper-rag-headless-runner-approval",
  );
  run(ctx, config, io).catch((error) => {
    fail(io, error);
  });
}
