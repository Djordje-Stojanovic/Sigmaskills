# SigmaBrief method

## Contents

1. Who asks what
2. Resolve repository and work items
3. Light research
4. Classify each item
5. Emit and stop

## 1. Who asks what

| Actor | May ask |
|-------|---------|
| **SigmaBrief** | At most one question if the work target is missing (`Which issue URL(s), work statement, or repo for all open?`). Full grill-me only if the user explicitly asks SigmaBrief to grill them. |
| **Executing agent** (in the brief) | Plan first; `/grill-me` or focused questions when trade-offs exist — including whether to create an isolated Windows git worktree. |

SigmaBrief itself stays thin: research enough to write good simple briefs, then emit.

## 2. Resolve repository and work items

Prefer the repository implied by issue URLs or the current workspace. For `all open`, list open issues with GitHub tooling when authenticated.

Accept:

- one or more issue URLs;
- issue numbers when the repo is clear (`#12`, `12`);
- `all open` / simple label filters;
- non-GitHub work: features, upgrades, bugs, plain English tasks;
- constraints: skip N, do not merge, finish PR M only, max agents.

## 3. Light research

Do the minimum that prevents bad briefs:

```text
gh repo view --json nameWithOwner,url
gh issue list --state open --limit 50 --json number,title,labels,url
gh issue view <N> --json number,title,body,labels,state,comments,url
gh pr list --state open --json number,title,url,headRefName,body
```

Also:

- detect in-flight PRs/branches (`Closes #N`, `fix/issue-N-…`);
- skim local standards when present (`CLAUDE.md`, `AGENTS.md`, `README`, `CONTRIBUTING`, LEARNINGS, version pins) and pick a short required-reads list per brief;
- note obvious path/system overlaps across items;
- note upstream blockers (linked upstream issues);
- redact secrets from any quoted issue context.

Skip deep code archaeology. SigmaBrief is not SigmaReview.

## 4. Classify each item

Assign one prompt type:

| Type | When |
|------|------|
| `greenfield` | No open PR addresses the work |
| `finish-PR` | Open PR/branch already addresses it — rebase/finish only; never a second implementation |
| `skip` | Already on default branch / fixed / user said skip |
| `blocked` | Upstream-only or human-gate; smallest workaround or tracking note, no giant fork |

Recommend isolation defaults for the *executing* agent’s plan question:

- parallel / multi-writer → worktree on;
- single sequential → main checkout OK.

For `finish-PR`: continue the existing PR branch; worktree only if that branch will run in parallel with other writers.

## 5. Emit and stop

Produce the chat output in [prompt-contract.md](prompt-contract.md). Do not implement. Do not open product-repo PRs. Do not write report files into the target repository.
