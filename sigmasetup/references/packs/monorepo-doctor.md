# Monorepo Doctor pack setup

Source: [santoshyadavdev/monorepo-doctor](https://github.com/santoshyadavdev/monorepo-doctor) pinned to one commit. Two skills: `monorepo-doctor` (a read-only audit of a JS/TS workspace: boundaries, cycles, caching, CI coverage, test code in production) and `monorepo-boundaries-cleanup` (pays boundary findings down in small PRs). License: MIT.

- **Node 22.5 or later.** Check with `node --version`; the audit stops on older Node.
- It needs a workspace: `workspaces` in the root `package.json`, a `pnpm-workspace.yaml`, or Bazel `BUILD` files. A repo with none stops at its first step with `NO_WORKSPACE`.
- It downloads nothing unless you allow it in the request; then only its pinned `knip` and `publint`. Keys and MCP servers: none.
