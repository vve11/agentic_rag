import { mkdir, rename, writeFile } from "node:fs/promises";
import { dirname, relative } from "node:path";

const G0_CASES = [
  "DSH-G0-001",
  "DSH-G0-002",
  "DSH-G0-003",
  "DSH-G0-004",
  "DSH-G0-005",
  "DSH-G0-006",
  "DSH-G0-007",
  "DSH-G0-008",
  "DSH-G0-009",
];

function pass(evidence) {
  return { status: "PASS", evidence };
}

function blocked(reason) {
  return { status: "BLOCKED", reason };
}

export function buildG0CompatReport({
  commit,
  dirty,
  paths,
  configAudit,
  presetDiscovery,
  startedAt = new Date().toISOString(),
}) {
  const deterministicEvidence = {
    dsh_home: relative(paths.repoRoot, paths.dshHome),
    credentials_path: relative(paths.repoRoot, paths.credentialsPath),
    patch: relative(paths.repoRoot, paths.patchPath),
    preset_source: relative(paths.repoRoot, paths.presetSourceDir),
    preset_runtime: relative(paths.repoRoot, paths.presetDestDir),
  };
  const cases = {
    "DSH-G0-001": pass("package.json and pnpm-lock exact DSH/Cordis graph checks pass"),
    "DSH-G0-002": configAudit.passed
      ? pass("dump-config audit confirms loopback host and telemetry disabled")
      : blocked("dump-config audit failed"),
    "DSH-G0-003":
      presetDiscovery?.id === "paper-research" && presetDiscovery?.broken === undefined
        ? pass("DSH discoverPresets found paper-research in versioned DSH_HOME")
        : blocked(presetDiscovery?.broken ?? "paper-research preset was not discovered"),
    "DSH-G0-004": blocked("Native Broker + private stdio MCP fixture not implemented yet"),
    "DSH-G0-005": blocked("write-tool approval proof not implemented yet"),
    "DSH-G0-006": blocked("same-version DSH session resume proof not implemented yet"),
    "DSH-G0-007": blocked("MCP crash/reconnect proof not implemented yet"),
    "DSH-G0-008": blocked("cancel/timeout/credential bridge proof not implemented yet"),
    "DSH-G0-009": blocked("standing Broker generation proof not implemented yet"),
  };

  return {
    schema_version: 1,
    gate: "G0",
    component: "dsh-g0-compat",
    commit,
    dirty,
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    versions: {
      dsh: paths.dshVersion,
      cordis: paths.cordisVersion,
      node: process.version,
    },
    config_audit: configAudit,
    paths: deterministicEvidence,
    cases: Object.fromEntries(G0_CASES.map((caseId) => [caseId, cases[caseId]])),
    go_no_go: "no-go",
  };
}

export async function writeJsonAtomic(path, value) {
  await mkdir(dirname(path), { recursive: true });
  const tmp = `${path}.${process.pid}.tmp`;
  await writeFile(tmp, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  await rename(tmp, path);
}
