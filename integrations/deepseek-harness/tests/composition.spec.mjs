import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, test } from "vitest";

import { auditDshConfigDump } from "../src/config-audit.mjs";
import { pathsFor } from "../src/paths.mjs";
import { discoverPaperResearchPreset } from "../src/preset-discovery.mjs";
import { buildG0CompatReport } from "../src/report.mjs";
import { withRuntimeLock } from "../src/runtime-lock.mjs";
import { syncPaperResearchPreset } from "../src/sync-preset.mjs";

const integrationRoot = fileURLToPath(new URL("..", import.meta.url));
const repoRoot = resolve(integrationRoot, "../..");
const cleanup = [];

afterEach(async () => {
  while (cleanup.length > 0) {
    const path = cleanup.pop();
    await rm(path, { recursive: true, force: true });
  }
});

describe("repo-local DeepSeek Harness runtime", () => {
  test("uses versioned DSH_HOME and a credential store outside the session root", () => {
    const paths = pathsFor({ integrationRoot });

    expect(paths.repoRoot).toBe(repoRoot);
    expect(paths.dshVersion).toBe("0.1.0-rc.6");
    expect(paths.dshHome).toBe(
      join(repoRoot, "data/runtime/deepseek-harness/versions/0.1.0-rc.6"),
    );
    expect(paths.sessionRoot).toBe(join(paths.dshHome, "sessions"));
    expect(paths.credentialsPath).toBe(
      join(repoRoot, "data/runtime/deepseek-harness/credentials/.credentials.yaml"),
    );
    expect(paths.credentialsPath.startsWith(paths.dshHome)).toBe(false);
  });

  test("syncs the paper-research preset into DSH_HOME user presets", async () => {
    const dshHome = await mkdtemp(join(tmpdir(), "paper-rag-dsh-home-"));
    cleanup.push(dshHome);
    const paths = pathsFor({ integrationRoot, dshHome });

    const result = await syncPaperResearchPreset(paths);

    expect(result.id).toBe("paper-research");
    expect(result.destDir).toBe(join(dshHome, ".agent-presets/paper-research"));
    expect((await stat(result.destDir)).isDirectory()).toBe(true);
    await expect(readFile(join(result.destDir, "preset.yml"), "utf8")).resolves.toContain(
      "Paper Research",
    );
    await expect(
      readFile(join(result.destDir, "agent.cordis.yml"), "utf8"),
    ).resolves.toContain("@deepseek-ai/dsh-tool-ask-user");

    const discovered = await discoverPaperResearchPreset(paths);
    expect(discovered).toMatchObject({
      id: "paper-research",
      trust: "user",
      name: "Paper Research",
    });
    expect(discovered.broken).toBeUndefined();
    expect(discovered.path).toBe(join(result.destDir, "agent.cordis.yml"));
  });

  test("sync is safe when doctor and smoke bootstrap the same DSH_HOME concurrently", async () => {
    const dshHome = await mkdtemp(join(tmpdir(), "paper-rag-dsh-home-"));
    cleanup.push(dshHome);
    const paths = pathsFor({ integrationRoot, dshHome });

    await Promise.all([
      syncPaperResearchPreset(paths),
      syncPaperResearchPreset(paths),
      syncPaperResearchPreset(paths),
      syncPaperResearchPreset(paths),
    ]);

    const discovered = await discoverPaperResearchPreset(paths);
    expect(discovered.broken).toBeUndefined();
    await expect(
      readFile(join(dshHome, ".agent-presets/paper-research/preset.yml"), "utf8"),
    ).resolves.toContain("Paper Research");
  });

  test("runtime lock serializes DSH profile writers", async () => {
    const dshHome = await mkdtemp(join(tmpdir(), "paper-rag-dsh-home-"));
    cleanup.push(dshHome);
    const paths = pathsFor({ integrationRoot, dshHome });
    let active = 0;
    let maxActive = 0;

    await Promise.all(
      Array.from({ length: 4 }, () =>
        withRuntimeLock(paths, async () => {
          active += 1;
          maxActive = Math.max(maxActive, active);
          await new Promise((resolvePromise) => setTimeout(resolvePromise, 5));
          active -= 1;
        }),
      ),
    );

    expect(maxActive).toBe(1);
  });
});

describe("web profile config audit", () => {
  test("requires loopback, disabled telemetry, paper preset default, and timeout policy", () => {
    const dump = `
- id: session-telemetry-otel
  name: '@deepseek-ai/dsh-session-telemetry-otel'
  disabled: true
- id: credentials
  name: '@deepseek-ai/dsh-credentials-local'
  config:
    path: !!js process.env.PAPER_RAG_DSH_CREDENTIALS_PATH
- id: webserver
  name: '@deepseek-ai/dsh-host-webserver'
  config:
    host: 127.0.0.1
- id: timeout-policy
  name: '@deepseek-ai/dsh-tool-call-timeout-policy'
- id: agent-presets
  name: '@deepseek-ai/dsh-agent-presets'
  config:
    default: paper-research
`;

    const audit = auditDshConfigDump(dump);

    expect(audit.passed).toBe(true);
    expect(audit.checks.map((check) => check.id)).toEqual([
      "web-loopback",
      "telemetry-disabled",
      "credential-path",
      "timeout-policy",
      "paper-preset-default",
    ]);
  });

  test("fails closed when timeout policy is missing", () => {
    const audit = auditDshConfigDump(`
- id: webserver
  config:
    host: 127.0.0.1
- id: session-telemetry-otel
  disabled: true
- id: credentials
  config:
    path: !!js process.env.PAPER_RAG_DSH_CREDENTIALS_PATH
- id: agent-presets
  config:
    default: paper-research
`);

    expect(audit.passed).toBe(false);
    expect(audit.checks.find((check) => check.id === "timeout-policy")).toMatchObject({
      status: "FAIL",
    });
  });
});

describe("G0 component report", () => {
  test("marks deterministic DSH checks pass and unfinished live compatibility cases blocked", () => {
    const paths = pathsFor({ integrationRoot });
    const report = buildG0CompatReport({
      commit: "abc123",
      dirty: false,
      paths,
      configAudit: { passed: true, checks: [] },
      presetDiscovery: { id: "paper-research", broken: undefined },
    });

    expect(report.gate).toBe("G0");
    expect(report.component).toBe("dsh-g0-compat");
    expect(report.go_no_go).toBe("no-go");
    expect(report.versions).toMatchObject({
      dsh: "0.1.0-rc.6",
      cordis: "4.0.1",
    });
    expect(report.cases["DSH-G0-001"].status).toBe("PASS");
    expect(report.cases["DSH-G0-002"].status).toBe("PASS");
    expect(report.cases["DSH-G0-003"].status).toBe("PASS");
    expect(report.cases["DSH-G0-003"].evidence).toContain("discoverPresets");
    expect(report.cases["DSH-G0-004"].status).toBe("BLOCKED");
    expect(report.cases["DSH-G0-009"].status).toBe("BLOCKED");
  });
});
