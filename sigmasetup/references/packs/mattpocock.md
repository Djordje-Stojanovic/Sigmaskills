# Matt Pocock pack setup

Source: [mattpocock/skills](https://github.com/mattpocock/skills). Everything here is per repo; the pack has no user-level mode.

## Needed before most skills

- **`/setup-matt-pocock-skills`, once per repo.** The owner types it; no other skill can start it. It asks where issues live (GitHub with `gh`, GitLab with `glab`, local markdown under `.scratch/`, or other) and writes `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, `docs/agents/triage-labels.md` (only with `triage` installed) and an `## Agent skills` block in `CLAUDE.md`, else `AGENTS.md`. `to-tickets`, `to-spec` and `triage` give wrong output without these files; `code-review`, `implement-spec` and `wayfinder` ask for them. Undo: delete the `docs/agents/` files and the `## Agent skills` block.
- **Triage labels** (with `triage`): `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Check with `gh label list`; create a missing one with `gh label create <name>`. Undo: `gh label delete <name>`.
- **Wayfinder labels** (with `wayfinder` on GitHub): `wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task`. Setup does not create them, and `gh issue create --label` fails on a missing label. Create them before the first wayfinder run.

## Optional, ask first

- **Git guard.** Use this skill's guard (`../git-guard.md`), per repo. The pack's own `git-guardrails-claude-code` offers a global install and blocks every push and `git branch -D`; it is frozen upstream.
- **`setup-pre-commit`** (JavaScript repos only): adds `husky`, `lint-staged` and `prettier` as dev dependencies, runs `npx husky init`, writes `.husky/pre-commit`, `.lintstagedrc` and `.prettierrc` when missing, and adds `"prepare": "husky"`. Undo: remove those dev dependencies, files and the script.
- **`setup-ts-deep-modules`** (marked in progress upstream): adds `dependency-cruiser`, `.dependency-cruiser.cjs` and a `lint:boundaries` script.
