import { join } from "node:path";

import {
  PaperRagNativeBroker,
  buildPaperRagMcpChildEnv,
  environmentCredentialProvider,
  registerPaperRagNativeTools,
} from "./broker.mjs";

const DEFAULT_CREDENTIAL_REFS = Object.freeze(["OPENAI_API_KEY"]);
export const DEFAULT_MCP_ARGS = Object.freeze(["-m", "paper_rag.mcp"]);

export const name = "paper-rag-native-broker";
export const inject = ["tools"];

function parseJsonArrayEnv(name, fallback) {
  const value = process.env[name];
  if (value === undefined || value.trim() === "") {
    return [...fallback];
  }
  const parsed = JSON.parse(value);
  if (!Array.isArray(parsed) || parsed.some((item) => typeof item !== "string")) {
    throw new Error(`${name} must be a JSON array of strings`);
  }
  return parsed;
}

export async function apply(ctx) {
  const repoRoot = process.env.PAPER_RAG_REPO_ROOT ?? process.cwd();
  const broker = new PaperRagNativeBroker({
    command: process.env.PAPER_RAG_MCP_COMMAND ?? join(repoRoot, ".venv/bin/python"),
    args: parseJsonArrayEnv("PAPER_RAG_MCP_ARGS", DEFAULT_MCP_ARGS),
    cwd: repoRoot,
    credentials: environmentCredentialProvider(),
    credentialRefs: parseJsonArrayEnv("PAPER_RAG_MCP_CREDENTIAL_REFS", DEFAULT_CREDENTIAL_REFS),
    childEnv: buildPaperRagMcpChildEnv({
      repoRoot,
      artifactRoot: process.env.PAPER_RAG_ARTIFACT_ROOT ?? join(repoRoot, "data/artifacts"),
      importRoot: process.env.PAPER_RAG_IMPORT_ROOT ?? join(repoRoot, "data/imports"),
      sourceEnv: process.env,
      toolset: process.env.PAPER_RAG_MCP_TOOLSET ?? "readonly",
      actorId: process.env.PAPER_RAG_ACTOR_ID ?? "system",
    }),
    activePresetId: process.env.PAPER_RAG_DSH_PRESET_ID ?? "paper-research",
    approval: ctx.get?.("approval"),
  });

  try {
    await broker.activate();
    const unregisterTools = registerPaperRagNativeTools(ctx, broker);
    ctx.effect(
      () => async () => {
        unregisterTools();
        await broker.close();
      },
      "paper-rag-native-broker",
    );
  } catch (error) {
    await broker.close().catch(() => {});
    throw error;
  }
}
