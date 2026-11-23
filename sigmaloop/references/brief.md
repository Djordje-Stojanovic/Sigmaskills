# Briefs

Turn actionable work into short, paste-ready briefs for other agents (was SigmaBrief). Research lightly, write the dispatch list and the fenced briefs, stop. The target repo stays as it was: no code, branch, commit, PR or file.

## Input

Anything actionable: issue URLs or numbers, `all open` (filtered or not), a SigmaReview report (one brief per finding or tight group, reusing its fix, proof test and `Done when` verbatim), chosen SigmaImprove entries (the chosen option and its sketch), plain-English work, or `this session`. Apply constraints already given (`do not merge`, skip N, max agents, `approval: auto|plan`) without asking again. No target at all: ask one question (which issues, which work, which repo). Grill only when the user asks for it.

## Light research

Enough to write good simple briefs, no code archaeology:

```text
gh repo view --json nameWithOwner,url
gh issue list --state open --limit 50 --json number,title,labels,url
gh issue view <N> --json number,title,body,labels,state,comments,url
gh pr list --state open --json number,title,url,headRefName,body
```

Find in-flight PRs and branches (`Closes #N`, `fix/issue-N-...`), the required reads per brief (`AGENTS.md`, `CLAUDE.md`, `ENGINEERING.md`, `DESIGN.md`, `CONTRIBUTING`), overlaps between items, upstream blockers. Redact secrets from quoted issue text.

## Classify and wave

| Type | When |
|---|---|
| `greenfield` | No open PR addresses the work |
| `finish-PR` | An open PR or branch already does: finish it, never a second implementation |
| `skip` | Already on the default branch, fixed, or the user said skip |
| `blocked` | Upstream-only or a human gate: the smallest workaround or a tracking note |
| `session` | Hand this conversation to a fresh agent |

Two items are independent only when they touch different files and no shared state (schema, config, lockfile, generated output, test fixtures). Independent items share a wave and run in parallel; the rest run later or in one lane. When in doubt, sequence. Rank by value: the next free agent takes the most valuable ready brief. Parallel writers get a worktree each; a single sequential item may use the main checkout.

## What every brief carries

1. The exact work target, and a one-sentence definition of done.
2. `approval: auto` (default): decide, log each call as `Ruling: <what> - <why> - <cost if wrong>` in the PR body, stop only for irreversible, security-sensitive or outside-the-branch actions. `approval: plan` (only when asked): post a plan and wait.
3. Branch from the newest `origin/<base>`, or continue the existing PR branch: merge the newest base in, never rebase a pushed branch. Isolation on: the worker makes its own worktree (the host's native worktree tool when it has one, else `git fetch origin` and `git worktree add -b <branch> <sibling-path> origin/<base>`); if `worktree add` fails it fixes the cause, never edits the shared checkout.
4. Required reads as concrete paths; the repo's `ENGINEERING.md` and `DESIGN.md` when present.
5. Big steps: the whole job in 10-20 tool calls, each input read whole, each file in one write. Validate once at the end; a red that is also red on `origin/<base>` is named, not fixed. A SigmaReview proof test fails before the fix and passes after. Long commands run in the background, no sleep or poll loops.
6. Commit each finished part, push, open a PR (`Closes #N`). **Do not merge** unless the user's run says the planner merges. Keep the worktree while the PR is open; clean up (remote branch, `git worktree remove`, `git branch -D`) only after the merge or an abandon.
7. Before building, answer in the PR body: "Is there a stupid simple solution?" "How hard is this before you build?" "Could a prompt answer this instead of a feature?"
8. Out of scope, as a list. The shell native to the worker's machine. No secrets. Read the real code for each claim; cite no file you did not open.
9. Report back: `Status: DONE | DONE_WITH_CONCERNS | BLOCKED`, PR URL, checks run and results, rulings, concerns.

Write for the worker's harness: the one the user named, else yours; use its own tools where they help ([hosts.md](hosts.md)), else plain git and shell steps.

## Shapes

```text
<issue-url or task>   (finish-PR: Existing PR: <url> (branch <name>))
Read the work item and the files it touches. Decide trade-offs; log each as a Ruling in the PR body.
Isolation: <on: make your own worktree off origin/<base> | off (sequential)>.
Solve it. Required reads: <paths>. Validate once at the end with: <tests>.
Commit each finished part, push, PR with Closes #<N>. Do not merge. Out of scope: <list>.
REPORT BACK: Status, PR URL, checks, rulings, concerns.
```

A session brief: the goal in one sentence; where it stands (three to six lines); what is decided and why; the artifacts to read (spec, issue, PR, branch, files), linked, not copied; the next step and how to know it is done; open questions; suggested skills. For a run under a loop harness it also names the run file, the handoff file and the done command.

## Output

Chat only. A dispatch list, one line per item: `wave N | #N or title | isolation: on|off | type: greenfield|finish-PR|skip|blocked|session`. Then one fenced `text` block per brief, no prose inside. Notes only when useful: overlaps, upstream waits, already fixed, human-only tests.
