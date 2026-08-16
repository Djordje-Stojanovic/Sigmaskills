---
name: sigmabrief
description: Prepare copy-pastable parallel-agent or single-agent execution briefs from GitHub issues, features, upgrades, bugs, or plain work statements. Use only when the user explicitly asks for briefs, handoffs, spawn/dispatch prompts, or parallel agent prompts. Do not use to implement the work, audit a whole repository, open fix PRs against the target product repository, or auto-fire on ordinary chat.
---

# SigmaBrief

Turn actionable work into short, paste-ready briefs for other agents. SigmaBrief is a prompt factory: research lightly, emit dispatch lines and fenced briefs, stop. The executing agent plans, optionally grills, implements, validates, and opens a PR for review.

Read [brief-method.md](references/brief-method.md) before researching. Read [prompt-contract.md](references/prompt-contract.md) before writing briefs.

## Operating contract

Apply these invariants throughout the run:

- **Explicit-only.** Invoke this skill only when the user asks for briefs, handoffs, spawn/dispatch prompts, or parallel agent prompts. Never treat ambient chat, implement requests, or audit requests as SigmaBrief work even if the host allows implicit skill invocation.
- **Brief factory only.** Do not implement, branch, commit, push, or open fix pull requests in the *target* product repository. Do not create `SIGMABRIEF-*.md` or other files there.
- **One shot for briefing.** When work items are present, research → synthesize → return briefs in chat. Do not pause for taste questions.
- **Ask at most one question** when no work target can be resolved: which issue URL(s), work statement, or repo for `all open`. Do not run a full grill-me session unless the user explicitly asks SigmaBrief to grill them. Planning depth and the worktree question belong in the *generated* brief for the *executing* agent.
- **Accept anything actionable:** issue URLs, `#N`, `all open` (optionally filtered), features, upgrades, bugs, plain English work, plus optional constraints (`do not merge`, skip N, max agents).
- **Light research then emit.** Read local standards when present (`CLAUDE.md`, `AGENTS.md`, `README`, `CONTRIBUTING`, LEARNINGS, version pins). For GitHub work, inspect issues and open PRs so an in-flight PR becomes a finish/rebase brief, never a second greenfield. Use the web only when needed.
- **Simple briefs.** Short fenced `text` blocks. No collision-matrix novels. Still mark overlaps and out-of-scope boundaries when obvious.
- **Quality gate in every brief:** plan first → (executing agent may use `/grill-me` or focused questions, including worktree yes/no) → wait for plan approval → execute → validate → update docs only when needed → commit → push → open PR (`Closes #N` when applicable) → **do not merge** → self-review for high quality, docs, validation, and low bug-introduction risk before opening the PR.
- **Do not merge. Keep any worktree while the PR is open. Cleanup only after human merge or user cancel/abandon.**
- **Windows-native** defaults: PowerShell-friendly commands and Windows sibling paths. Do not assume WSL.
- **No secrets** in briefs. Redact tokens, keys, and credentials from issue bodies or notes.

## Resolve inputs

Resolve work items in this order:

1. Explicit issue URLs, numbers, `all open`, or plain work statements in the invocation.
2. Otherwise the current Git repository’s open issues when the user asked for `all open` / dispatch without listing IDs.
3. Otherwise ask only for the missing work target.

Apply user constraints already present (skip N, do not merge, prefer rebase for PR M, max agents) without re-asking.

## Execute

Follow [brief-method.md](references/brief-method.md). Emit the chat output required by [prompt-contract.md](references/prompt-contract.md).

## Final response

Return in chat only:

1. A short dispatch list (one line per brief).
2. Paste-ready fenced `text` briefs.
3. Brief notes when needed (collisions, upstream waits, already fixed, human-only tests).

Do not paste long research dumps. Do not create files in the target product repository.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>

