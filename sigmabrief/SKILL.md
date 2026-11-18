---
name: sigmabrief
description: Use when asked for sigmabrief, briefs, handoffs or spawn prompts. Write copy-pastable agent briefs in safe parallel waves from issues or plans. Do not use to implement work or on ordinary chat.
---

# SigmaBrief

Turn actionable work into short, paste-ready briefs for other agents. SigmaBrief is a prompt factory: research lightly, emit dispatch lines and fenced briefs, stop. The executing agent implements, validates once at the end, and opens a PR for review.

Read [brief-method.md](references/brief-method.md) before researching and [prompt-contract.md](references/prompt-contract.md) before writing briefs.

## Operating contract

- **Brief factory only.** Briefs go to chat. The target repo stays as it was: no code, branch, commit, push, PR or file (no `SIGMABRIEF-*.md`).
- **One shot.** Work items present: research, write, return. No target at all: ask one question (which issues, which work, which repo for `all open`). Grill only when the user asks for it.
- **Anything actionable is input:** issue URLs, `#N`, `all open` (filtered or not), a SigmaReview report or wave, chosen SigmaImprove entries, plain-English work, or `this session`, with constraints already given (`do not merge`, skip N, max agents, `approval: auto|plan`) applied without asking again.
- **Waves before parallelism.** Items that touch the same files, schema or shared state run one after another in one lane; only independent items run in parallel. Honor `Depends on` lines. Rank the dispatch list by value: the next free agent takes the most valuable ready brief. An in-flight PR becomes a finish brief, never a second greenfield one.
- **Write for the worker's harness.** It is the one the user named, else the one you run in. Use its own tools where they help (a native worktree tool, sub-agents); when you do not know them, read its docs (context7, a web search) or write plain git and shell steps that work anywhere.
- **Every brief carries the invariants** in [prompt-contract.md](references/prompt-contract.md#2-invariants-every-brief-must-carry): approval mode, do not merge, keep the worktree while the PR is open, the native shell, no secrets, the three questions and the honesty rule. If the repo has `ENGINEERING.md` or `DESIGN.md`, each brief tells its worker to read and follow them.

## Final response

Return in chat only: a short dispatch list (one line per brief), the paste-ready fenced `text` briefs, and notes when needed (collisions, upstream waits, already fixed, human-only tests). No research dumps.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>

