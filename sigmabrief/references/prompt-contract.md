# SigmaBrief prompt contract

## Contents

1. Chat output shape
2. Invariants every brief must carry
3. Worktree create (Windows)
4. Cleanup (worktree-on only)
5. Brief skeletons
6. Dry-run examples

## 1. Chat output shape

Return only:

### Dispatch

One line per item:

```text
#N or title | isolation: on|off|ask | type: greenfield|finish-PR|skip|blocked
```

### Briefs

One standalone fenced `text` block per executing agent. No prose inside the fence.

### Notes

Only when useful: overlaps, upstream waits, already fixed, human-only tests.

## 2. Invariants every brief must carry

1. Exact work target (issue URL and/or plain task).
2. Plan first; wait for approval. If trade-offs exist, executing agent uses `/grill-me` or focused questions — including worktree yes/no (parallel → on; sequential single → off OK).
3. Branch from latest `main` **or** continue existing PR branch (never duplicate in-flight work).
4. One-sentence definition of done.
5. Required reads when discoverable (concrete paths, not “read the docs”).
6. Validate (tests/checkpoints if known; else smoke the failure mode + adjust tests if present).
7. Commit, push, open PR for review (`Closes #N` when applicable).
8. **Do not merge.**
9. Self-review: high quality, docs, validation, low regression risk before opening the PR.
10. Explicit out-of-scope / do-not-touch list.
11. Windows-native commands/paths. No WSL assumptions.
12. **Do not merge. Keep any worktree while the PR is open. Cleanup only after human merge or user cancel/abandon.**

## 3. Worktree create (Windows)

When isolation is on, the **executing agent** creates the worktree (Approach A).

### Prerequisites (verify before add)

1. `git fetch origin`
2. Main checkout index clean enough that `git worktree add` succeeds (commit or stash if git refuses)
3. Branch name unique — not already checked out in another worktree
4. Sibling path does not already exist as a directory or worktree

**Failure line:** if `git worktree add` fails, fix the prerequisite. Do **not** fall back to editing the shared main checkout while other writers are active.

```powershell
git fetch origin
git worktree add -b <branch> <sibling-path> origin/main
# Example: C:\AI\RepoName_issue12
# Do all edits only inside <sibling-path>
```

Rules: one branch ↔ one worktree; sibling path next to the main repo (not under `.git`); never write to the shared main checkout while parallel agents are writing.

Host extras (Cursor `/worktree`, Pi/Lazy `worktree: true`, Codex after `cd` into the worktree) are optional — they do not replace agent-created `git worktree add` when isolation is on.

### Finish-PR isolation

Continue the existing PR branch. Create a worktree for that branch only if other writers will run in parallel. Otherwise continue on a normal checkout of the PR branch. Always: rebase on latest `main`, resolve conflicts carefully (keep both additive doc entries when both valid), re-validate, push, confirm mergeable. Do not start a second greenfield implementation.

## 4. Cleanup (worktree-on only)

Every worktree-enabled brief must mention cleanup in **three** places:

1. **Near the top (setup):** you own worktree lifecycle — create at start; remove after human merge or abandon; no orphans.
2. **Definition of Done / PR section:** after **human merge** or abandon — not after `gh pr create` — run the cleanup block.
3. **End checklist** with commands:

```powershell
# Only after human merge OR abandon — never while PR still open
gh pr view <N> --json state,mergedAt
git push origin --delete <branch>   # if remote still exists
git worktree remove <sibling-path>  # --force only if required
git worktree prune
git branch -d <branch>              # or -D if already gone remotely
git worktree list                   # path must be gone
```

Goal: no permanent disk/git bloat. If the PR is only open, **keep** the worktree until merge or explicit cancel.

Sequential briefs with isolation off: cleanup block is `N/A — no worktree`.

## 5. Brief skeletons

### Greenfield (isolation ask / on)

```text
<issue-url or task>

Research the local repo and this work item (gh issue/PR if applicable; web only if needed).
Plan first. If trade-offs exist, use /grill-me or ask focused questions — including whether to create an isolated Windows git worktree (recommended for parallel agents; optional for one sequential task). Wait for plan approval.

If isolation is on: YOU create the worktree (git fetch; verify clean-enough main checkout, unique branch, free sibling path; then git worktree add -b <branch> <Windows-sibling-path> origin/main). Do all work there. You own cleanup — do not leave worktrees/branches behind (see cleanup at end; this is critical). Do not merge. Keep the worktree while the PR is open. Cleanup only after human merge or abandon.

Solve the work. Follow repo standards and these required reads: <paths>.
Validate with: <tests/smoke>. Update docs/LEARNINGS only when something non-obvious was learned.
Commit, push, open a PR for review (Closes #<N> if an issue). Do NOT merge.
Self-review: high quality, docs, validation, low probability of bug introduction before opening the PR.

Out of scope: <boundaries>. Stay surgical. Prefer delete+simplify over new abstractions.

CLEANUP (if you created a worktree) — after human merge OR abandon only:
- confirm merge/abandon
- delete remote branch if still present
- git worktree remove <path>; git worktree prune; delete local branch
- verify with git worktree list
Remind: worktree cleanup is mandatory to avoid disk/git bloat.
```

### Finish-PR

```text
<issue-url>
Existing PR: <pr-url> (branch <name>)

Read the issue and the existing PR. Make a plan first. Do NOT start a second implementation.
Continue the existing PR branch. Rebase on latest main, resolve conflicts carefully, re-validate, push, confirm mergeable.
Ask whether other writers are running in parallel; create a Windows worktree for this PR branch only if yes (same create/cleanup rules as greenfield). Otherwise stay on a normal checkout of the PR branch.
Do NOT merge. Open/update the PR for review only after self-review for quality, docs, validation, and low bug risk.
Out of scope: unrelated issues.

CLEANUP: N/A unless you created a worktree — then cleanup only after human merge or abandon (same checklist as greenfield; mention lifecycle ownership at start and in DoD).
```

### Sequential (isolation off)

Same as greenfield but state `Isolation: off (sequential). Cleanup: N/A — no worktree.` and omit the triple cleanup blocks beyond that one-liner.

## 6. Dry-run examples

### A — Sequential single task

Dispatch:

```text
#12 Update Open WebUI safely | isolation: off | type: greenfield
```

Brief (shape only):

```text
https://github.com/owner/repo/issues/12

Research local repo + issue. Plan first; ask worktree only if unclear — recommend off for this sequential run. Wait for approval.
Isolation: off (sequential). Cleanup: N/A — no worktree.
Solve per issue. Required reads: CLAUDE.md, USER_GUIDE_OPENWEBUI.md.
Validate against those docs. Commit, push, PR with Closes #12. Do NOT merge.
Self-review before opening PR. Out of scope: other open issues.
```

### B — Parallel pair

Dispatch:

```text
#8 Lazy toolkit path parsing | isolation: on | type: greenfield
#11 Symfonium CrowdSec bans | isolation: on | type: greenfield
```

Each brief: isolation on; Windows sibling paths (`C:\AI\Repo_issue8`, `C:\AI\Repo_issue11`); create prereqs; cleanup ×3 (top ownership, DoD after human merge/abandon, end checklist); do not touch the other issue’s paths; do not merge; keep worktree while PR open.
