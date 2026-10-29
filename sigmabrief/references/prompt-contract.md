# SigmaBrief prompt contract

## Contents

1. Chat output shape
2. Invariants every brief must carry
3. Worktree create
4. Cleanup (worktree-on only)
5. Brief skeletons
6. Dry-run examples

## 1. Chat output shape

Return only:

### Dispatch

One line per item:

```text
wave N | #N or title | isolation: on|off|ask | type: greenfield|finish-PR|skip|blocked|session
```

### Briefs

One standalone fenced `text` block per executing agent. No prose inside the fence.

### Notes

Only when useful: overlaps, upstream waits, already fixed, human-only tests.

## 2. Invariants every brief must carry

1. Exact work target (issue URL and/or plain task).
2. With `approval: auto` (default), decide, record each decision as `Ruling: <what> — <why> — <cost if wrong>` in the PR body, and stop only for irreversible, security-sensitive, or outside-the-branch actions. With `approval: plan` (only when the user asked), post a plan and wait for approval.
3. Branch from latest `<base>` (default `main`) **or** continue existing PR branch (never duplicate in-flight work).
4. One-sentence definition of done.
5. Required reads when discoverable (concrete paths, not “read the docs”).
6. Big steps: the whole job in 10-20 tool calls; read each input whole; write each file in one Write. Validate once, at the end (tests/checkpoints if known; else smoke the failure mode). A red that is also red on `origin/<base>` is named, not fixed. For a SigmaReview finding, its proof test must fail before the fix and pass after. Long commands run in the background; no sleep or poll loops.
7. Commit each finished part as you go, push, open PR for review (`Closes #N` when applicable).
8. **Do not merge.**
9. Self-review: high quality, docs, validation, low regression risk before opening the PR.
10. Explicit out-of-scope / do-not-touch list.
11. Use the shell native to the executing machine (PowerShell on Windows, POSIX shell elsewhere). No WSL assumptions.
12. **Keep any worktree while the PR is open. Cleanup only after human merge or user cancel/abandon.**
13. Report back in this format: `Status: DONE | DONE_WITH_CONCERNS | BLOCKED` · PR URL · checks run and results · rulings or open questions · concerns.
14. Before you build, answer three questions in the PR body: "Is there a stupid simple solution?" "How hard is this before you build?" "Could a prompt answer this instead of a feature?"
15. Sub-agent honesty rule: read the real code for each claim, and cite no file you did not open.

## 3. Worktree create

When isolation is on, the **executing agent** creates the worktree. If the host has a native worktree tool (for example Cursor `/worktree`, a `--worktree` flag, or an `EnterWorktree` tool), use it: the host can then see and clean up the worktree. Otherwise use the git commands below. If the agent already runs inside a linked worktree, it creates no second one.

### Prerequisites (verify before add)

1. `git fetch origin`
2. Main checkout index clean enough that `git worktree add` succeeds (commit or stash if git refuses)
3. Branch name unique — not already checked out in another worktree
4. Sibling path does not already exist as a directory or worktree

**Failure line:** if `git worktree add` fails, fix the prerequisite. Do **not** fall back to editing the shared main checkout while other writers are active.

```text
git fetch origin
git worktree add -b <branch> <sibling-path> origin/<base>
# Example: ../repo-issue12
# Do all edits only inside <sibling-path>
```

Rules: one branch ↔ one worktree; sibling path next to the main repo (not under `.git`); never write to the shared main checkout while parallel agents are writing.


### Finish-PR isolation

Continue the existing PR branch. Create a worktree for that branch only if other writers will run in parallel. Otherwise continue on a normal checkout of the PR branch. Always: merge the latest `origin/<base>` into the branch (never rebase a pushed branch), resolve conflicts carefully (keep both additive doc entries when both valid), re-validate, push, confirm mergeable. Do not start a second greenfield implementation.

## 4. Cleanup (worktree-on only)

Every worktree-enabled brief ends with this block. The executing agent runs it after **human merge** or abandon, never after `gh pr create`:

```text
# Only after human merge OR abandon — never while PR still open
gh pr view <N> --json state,mergedAt
git push origin --delete <branch>   # if remote still exists
git worktree remove <sibling-path>  # --force only if required
git worktree prune
git branch -D <branch>              # only after the PR shows merged; a squash merge makes -d refuse
git worktree list                   # path must be gone
```

Goal: no permanent disk/git bloat. If the PR is only open, **keep** the worktree until merge or explicit cancel.

Sequential briefs with isolation off: cleanup block is `N/A — no worktree`.

## 5. Brief skeletons

### Greenfield (isolation on)

```text
<issue-url or task>

Read the work item and the files it touches (gh issue/PR if applicable; web only if needed). Decide trade-offs yourself and log each as a Ruling in the PR body.

If isolation is on: YOU create the worktree (git fetch; verify clean-enough main checkout, unique branch, free sibling path; then git worktree add -b <branch> <sibling-path> origin/<base>). Do all work there. Do not merge. Keep the worktree while the PR is open. Cleanup only after human merge or abandon.

Solve the work. Follow repo standards and these required reads: <paths>.
Work in big steps: the whole job in 10-20 tool calls, commit each finished part. Validate once at the end with: <tests/smoke>; a red also red on origin/<base> is named, not fixed. Update docs/LEARNINGS only when something non-obvious was learned.
Self-review the diff: quality, docs, validation, low bug risk. Push, open a PR for review (Closes #<N> if an issue). Do NOT merge.

Out of scope: <boundaries>. Stay surgical. Prefer delete+simplify over new abstractions.

CLEANUP (if you created a worktree) — after human merge OR abandon only:
- confirm merge/abandon
- delete remote branch if still present
- git worktree remove <path>; git worktree prune; delete local branch
- verify with git worktree list

REPORT BACK: Status: DONE | DONE_WITH_CONCERNS | BLOCKED · PR URL · checks run · rulings/open questions · concerns.
```

### Finish-PR

```text
<issue-url>
Existing PR: <pr-url> (branch <name>)

Read the issue and the existing PR. Do NOT start a second implementation.
Continue the existing PR branch. Merge the latest origin/<base> into the branch (never rebase a pushed branch), resolve conflicts carefully, re-validate, push, confirm mergeable.
Isolation: <on|off>. If on, create a worktree for this PR branch (same create/cleanup rules as greenfield). Otherwise stay on a normal checkout of the PR branch.
Do NOT merge. Open/update the PR for review only after self-review for quality, docs, validation, and low bug risk.
Out of scope: unrelated issues.

CLEANUP: N/A unless you created a worktree — then cleanup only after human merge or abandon (same checklist as greenfield).
```

### Session

```text
Continue this work: <one-sentence goal>.

Where it stands: <current state in three to six lines>.
Decided, with reasons: <decisions the next agent must not reopen>.
Artifacts (read these; they are the source of truth): <spec, issue, PR, branch, commit, file paths or URLs>.
Next step: <the first concrete action and how to know it is done>.
Open questions: <only the ones still open>.
Suggested skills: <e.g. $sigmareview, /tdd, $sigmawrite>.
```

Write it for an agent that has never seen this conversation. Point to artifacts instead of copying them. Redact secrets and personal data. Return it in chat like every other brief.

### Sequential (isolation off)

Same as greenfield but state `Isolation: off (sequential). Cleanup: N/A — no worktree.` and omit the cleanup block.

## 6. Dry-run examples

### A — Sequential single task

Dispatch:

```text
wave 1 | #12 Add CSV export to the report page | isolation: off | type: greenfield
```

Brief (shape only):

```text
https://github.com/owner/repo/issues/12

Read the issue and the files it touches. Decide trade-offs; log Rulings in the PR body.
Isolation: off (sequential). Cleanup: N/A — no worktree.
Solve per issue. Required reads: AGENTS.md, docs/exports.md.
Validate against those docs. Commit, push, PR with Closes #12. Do NOT merge.
Self-review before opening PR. Out of scope: other open issues.
```

### B — Parallel pair

Dispatch:

```text
wave 1 | #8 Parse config paths lazily | isolation: on | type: greenfield
wave 1 | #11 Rate-limit failed logins | isolation: on | type: greenfield
```

Each brief: isolation on; sibling paths (`../repo-issue8`, `../repo-issue11`); create prereqs; the cleanup block at the end; do not touch the other issue’s paths; do not merge; keep worktree while PR open.
