# SigmaLoop Briefs

Research enough to write good simple briefs, emit them in chat, stop. Implement nothing, open no PR and write no file in the target repository.

## Who asks what

- **SigmaLoop Briefs** asks at most one question, when the work target is missing (`Which issue URL(s), work statement, or repo for all open?`). A full `/grilling` only when the user asks for it.
- **The executing agent** asks nothing under `approval: auto` (default): it decides and logs rulings. Under `approval: plan`, it posts its plan and focused questions.

## Inputs

Prefer the repository implied by issue URLs or the current workspace. Accept:

- issue URLs, issue numbers when the repo is clear (`#12`, `12`), `all open` with simple label filters;
- a SigmaReview report (`SIGMAREVIEW-*.md`): one brief per finding or per tight group, reusing each finding's fix, proof test and `Done when` verbatim;
- SigmaImprove category issues: only entries marked `chosen`, with the chosen option and its sketch;
- features, upgrades, bugs and plain-English tasks outside GitHub;
- `this session`: a session brief so a fresh agent can continue this conversation. For a run under a loop harness it names the loop file, the handoff file, any scheduled wakes the harness holds and the goal line (one printed command);
- constraints: skip N, do not merge, finish PR M only, max agents.

## Light research

The minimum that prevents bad briefs:

```text
gh repo view --json nameWithOwner,url
gh issue list --state open --limit 50 --json number,title,labels,url
gh issue view <N> --json number,title,body,labels,state,comments,url
gh pr list --state open --json number,title,url,headRefName,body
```

Also: detect in-flight PRs and branches (`Closes #N`, `fix/issue-N-…`); skim local standards (`CLAUDE.md`, `AGENTS.md`, `README`, `CONTRIBUTING`, LEARNINGS, version pins) and pick a short required-reads list per brief; note path overlaps across items and upstream blockers; redact secrets from any quoted issue text. Skip deep code archaeology: that is SigmaReview.

## Classify each item

| Type | When |
|------|------|
| `greenfield` | No open PR addresses the work |
| `finish-PR` | An open PR or branch already addresses it: finish only, never a second implementation |
| `skip` | Already on the default branch, fixed, or the user said skip |
| `blocked` | Upstream-only or a human gate: the smallest workaround or a tracking note |
| `session` | Hand this conversation to a fresh agent |

Then group items into **waves**. Two items are independent only when they touch different files and no shared state (schema, config, lockfile, generated output, the same test fixtures). Independent items share a wave and run in parallel; the rest go in later waves or one after another. When in doubt, sequence: a merge conflict costs more than a wait.

Isolation: parallel writers get a worktree each; a single sequential item may use the main checkout; a `finish-PR` gets a worktree only when other writers run beside it.

## Chat output

Return only these three parts.

**Dispatch**, one line per item:

```text
wave N | #N or title | isolation: on|off|ask | type: greenfield|finish-PR|skip|blocked|session
```

**Briefs**: one standalone fenced `text` block per executing agent, no prose inside the fence.

**Notes**, only when useful: overlaps, upstream waits, already fixed, human-only tests.

## Invariants every brief carries

1. Exact work target (issue URL and/or plain task).
2. With `approval: auto` (default), decide, record each decision as `Ruling: <what> — <why> — <cost if wrong>` in the PR body, and stop only for irreversible, security-sensitive, or outside-the-branch actions. With `approval: plan` (only when the user asked), post a plan and wait for approval.
3. Branch from latest `<base>` (default `main`) **or** continue the existing PR branch (never duplicate in-flight work).
4. One-sentence definition of done.
5. Required reads when discoverable (concrete paths, not "read the docs").
6. Big steps: the whole job in 10-20 tool calls; read each input whole; write each file in one Write. Validate once, at the end (tests or checkpoints if known; else smoke the failure mode). A red that is also red on `origin/<base>` is named, not fixed. For a SigmaReview finding, its proof test must fail before the fix and pass after. Long commands run in the background; no sleep or poll loops.
7. Commit each finished part as you go, push, open a PR for review (`Closes #N` when applicable).
8. **Do not merge.**
9. Self-review: high quality, docs, validation, low regression risk before opening the PR.
10. Explicit out-of-scope / do-not-touch list.
11. Use the shell native to the executing machine (PowerShell on Windows, POSIX shell elsewhere). No WSL assumptions.
12. **Keep any worktree while the PR is open. Cleanup only after human merge or user cancel/abandon.**
13. Report back in this format: `Status: DONE | DONE_WITH_CONCERNS | BLOCKED` · PR URL · checks run and results · rulings or open questions · concerns.
14. Before you build, answer three questions in the PR body: "Is there a stupid simple solution?" "How hard is this before you build?" "Could a prompt answer this instead of a feature?"
15. Sub-agent honesty rule: read the real code for each claim, and cite no file you did not open.

## Worktrees

When isolation is on, the **executing agent** creates the worktree. A native worktree tool of the host (a `/worktree` command, a `--worktree` flag, an `EnterWorktree` tool) comes first: the host can then see and clean up the worktree. Else the git commands below. An agent that already runs inside a linked worktree creates no second one.

Before the add: `git fetch origin`; a main checkout clean enough that the add succeeds; a branch name no other worktree has checked out; a sibling path that does not exist yet. If `git worktree add` fails, fix the prerequisite; do not fall back to editing the shared main checkout while other writers are active.

```text
git fetch origin
git worktree add -b <branch> <sibling-path> origin/<base>    # e.g. ../repo-issue12; do all edits there
```

One branch, one worktree, on a sibling path next to the main repo (not under `.git`).

**Finish-PR:** continue the existing PR branch. Merge the latest `origin/<base>` into it (never rebase a pushed branch), resolve conflicts carefully (keep both additive doc entries when both are valid), re-validate, push, confirm mergeable.

**Cleanup.** Every worktree brief ends with this block. The executing agent runs it after human merge or abandon, never after `gh pr create`. A brief with no worktree says `Cleanup: N/A — no worktree`.

```text
# Only after human merge OR abandon — never while the PR is still open
gh pr view <N> --json state,mergedAt
git push origin --delete <branch>   # if remote still exists
git worktree remove <sibling-path>  # --force only if required
git worktree prune
git branch -D <branch>              # only after the PR shows merged; a squash merge makes -d refuse
git worktree list                   # path must be gone
```

## Brief skeletons

### Greenfield

```text
<issue-url or task>

Read the work item and the files it touches (gh issue/PR if applicable; web only if needed). Decide trade-offs yourself and log each as a Ruling in the PR body.

Isolation: <on: YOU create the worktree (git fetch; verify clean-enough main checkout, unique branch, free sibling path; then git worktree add -b <branch> <sibling-path> origin/<base>) and do all work there | off (sequential). Cleanup: N/A — no worktree>.

Solve the work. Follow repo standards and these required reads: <paths>.
Work in big steps: the whole job in 10-20 tool calls, commit each finished part. Validate once at the end with: <tests/smoke>; a red also red on origin/<base> is named, not fixed. Update docs/LEARNINGS only when something non-obvious was learned.
Before you build, answer in the PR body: "Is there a stupid simple solution?" "How hard is this before you build?" "Could a prompt answer this instead of a feature?" Read the real code for each claim; cite no file you did not open.
Self-review the diff: quality, docs, validation, low bug risk. Push, open a PR for review (Closes #<N> if an issue). Do not merge.

Out of scope: <boundaries>. Stay surgical. Prefer delete+simplify over new abstractions. Use the shell native to this machine. No secrets in commits, logs or PR text.

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

Read the issue and the existing PR. Do not start a second implementation.
Continue the existing PR branch. Merge the latest origin/<base> into the branch (never rebase a pushed branch), resolve conflicts carefully, re-validate, push, confirm mergeable.
Isolation: <on|off>. If on, create a worktree for this PR branch (same create/cleanup rules as greenfield). Otherwise stay on a normal checkout of the PR branch.
Do not merge. Open/update the PR for review only after self-review for quality, docs, validation, and low bug risk.
Out of scope: unrelated issues.

CLEANUP: N/A unless you created a worktree — then cleanup only after human merge or abandon (same checklist as greenfield).

REPORT BACK: Status: DONE | DONE_WITH_CONCERNS | BLOCKED · PR URL · checks run · rulings/open questions · concerns.
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

Write it for an agent that has never seen this conversation. Point to artifacts instead of copying them. Redact secrets and personal data.
