# Monorepo Doctor pack setup

Source: [santoshyadavdev/monorepo-doctor](https://github.com/santoshyadavdev/monorepo-doctor) pinned to one commit. Three skills: `monorepo-doctor` (a read-only audit of a JS/TS workspace: boundaries, cycles, caching, CI coverage, test code in production), `monorepo-boundaries-cleanup` (pays boundary findings down in small PRs) and `polyrepo-tax` (what several repos cost in drift, bumps and duplicated fixes, from their git history, with a migration plan; an authenticated `gh` adds real CI minutes). License: MIT; each skill folder gets the repo's `LICENSE`.

- **Node 22.5 or later.** Check with `node --version`; the audit stops on older Node.
- It needs a workspace: `workspaces` in the root `package.json`, a `pnpm-workspace.yaml`, or Bazel `BUILD` files. A repo with none stops at its first step with `NO_WORKSPACE`.
- It downloads nothing unless you allow it in the request; then only its pinned `knip` and `publint`. Keys and MCP servers: none.
