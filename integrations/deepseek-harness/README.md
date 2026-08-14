# Paper RAG DeepSeek Harness Integration

This directory owns the G0 DeepSeek Harness compatibility spike. It keeps DSH
package pins, profile patches, preset source, and deterministic scripts outside
the Python domain core.

Runtime state is repo-local and ignored:

- `data/runtime/deepseek-harness/versions/<dsh-version>/` is `DSH_HOME`.
- `data/runtime/deepseek-harness/credentials/.credentials.yaml` is the local
  credential provider path and is outside the versioned session root.
- `data/artifacts/` and `data/imports/` are reserved for later G2 artifact and
  import flows.

Useful commands:

```bash
pnpm install --frozen-lockfile
pnpm test
pnpm dsh:dump-config
pnpm smoke
pnpm g0:compat --report ../../data/index/migration-gates/components/G0/dsh-g0-compat.json
node scripts/start.mjs
```
