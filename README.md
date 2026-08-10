# SigmaSkills

High-rigor, portable [Agent Skills](https://agentskills.io/) for Codex, Pi, Claude Code, Cursor, and other compatible coding agents.

## Available skills

### SigmaReview

A one-shot, single-agent, full-repository engineering audit. SigmaReview reviews correctness, feature completeness, architecture, data and concurrency, reliability, security, performance, tests, dependencies, delivery, operations, and applicable domain-specific engineering. It rejects speculative findings, writes exactly one evidence-rich Markdown report, and opens it as a pull request without changing runtime code.

### SigmaPerformance

A calibrated, audit-only, full-repository performance engineering system. It maps complete user journeys, uses controlled measurement and mechanically conclusive source evidence, separates confirmed bottlenecks from measurement-required opportunities, and publishes one structured report PR. Runtime code remains unchanged.

### SigmaBrief

A prompt factory for parallel or single-agent execution. SigmaBrief turns GitHub issues, features, upgrades, bugs, or plain work statements into short, copy-pastable briefs for other agents. It researches lightly (issues, open PRs, local standards), emits a dispatch list plus fenced briefs, and stops. It does not implement the work, audit the whole repository, or open fix PRs against the target product repository. Briefs default to plan → optional grill-me (including Windows worktree isolation) → approve → execute → validate → PR for review (do not merge), with agent-created worktrees when isolation is on and cleanup only after human merge or abandon.

### SigmaWrite

A short writing-voice skill inspired by ASD-STE100 Simplified Technical English. Soft steers (not hard numbered rules) push clear, high-quality, still-technical explanations a sharp outsider can follow, with hard bans on gibberish and invented words. Includes a pasteable system-prompt block. Chat style only — not certified STE, no dictionary, no report PR.

## Install

Install any skill with the cross-agent installer:

```bash
npx skills add https://github.com/Djordje-Stojanovic/Sigmaskills --skill sigmareview
npx skills add https://github.com/Djordje-Stojanovic/Sigmaskills --skill sigmaperformance
npx skills add https://github.com/Djordje-Stojanovic/Sigmaskills --skill sigmabrief
npx skills add https://github.com/Djordje-Stojanovic/Sigmaskills --skill sigmawrite
```

For Codex:

```text
$skill-installer install sigmareview from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmaperformance from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmabrief from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmawrite from https://github.com/Djordje-Stojanovic/Sigmaskills
```

Manual universal installation:

```bash
git clone https://github.com/Djordje-Stojanovic/Sigmaskills.git
mkdir -p ~/.agents/skills
cp -R Sigmaskills/sigmareview ~/.agents/skills/sigmareview
cp -R Sigmaskills/sigmaperformance ~/.agents/skills/sigmaperformance
cp -R Sigmaskills/sigmabrief ~/.agents/skills/sigmabrief
cp -R Sigmaskills/sigmawrite ~/.agents/skills/sigmawrite
```

## Run

Codex:

```text
$sigmareview https://github.com/owner/repository
$sigmaperformance https://github.com/owner/repository
$sigmabrief https://github.com/owner/repository/issues/12
$sigmabrief all open
$sigmawrite
```

Pi:

```text
/skill:sigmareview https://github.com/owner/repository
/skill:sigmaperformance https://github.com/owner/repository
/skill:sigmabrief https://github.com/owner/repository/issues/12
/skill:sigmabrief all open
/skill:sigmawrite
```

Other Agent Skills-compatible tools can invoke these skills through their normal skill picker or command syntax.

SigmaPerformance begins with two compact calibration batches covering agent topology, execution authority, stress permission, evidence access, performance priorities, and representative workloads. It then runs autonomously.

**SigmaBrief is user-triggered only.** Invoke it when you want briefs, handoffs, or parallel agent prompts. Do not treat it as an ambient skill for ordinary implement/audit chat even if the host allows implicit skill invocation.

## Output contracts

### SigmaReview

- `SIGMAREVIEW-FINDINGS-YYYY-MM-DD.md`
- One dedicated branch and report-only pull request
- Prioritized, confidence-gated findings with exact evidence
- Implementation-ready remediation and verification steps
- A full repository coverage ledger
- No source fixes, dependency installation, application execution, subagents, or auxiliary repository artifacts

### SigmaPerformance

- `SIGMAPERFORMANCE-REPORT-YYYY-MM-DD.md`
- One dedicated report-only pull request
- M1 measured bottlenecks and M2 mechanically proven bottlenecks
- Separately accounted M3 measurement-required opportunities, unsuccessful experiments, and unverified boundaries
- Structured future SigmaOptimize handoff
- Default single-agent execution; bounded subagents only through explicit run-specific calibration opt-in
- No runtime-source changes or temporary measurement artifacts in the repository diff

### SigmaBrief

- Chat-only dispatch list plus paste-ready fenced `text` briefs (no `SIGMABRIEF-*.md` in the target product repository)
- Prompt types: greenfield, finish-PR, skip, blocked
- Executing-agent briefs: plan first, optional grill-me (including worktree), do not merge, self-review before PR
- When isolation is on: agent-created Windows `git worktree add` with prerequisites; cleanup mentioned ≥3 times; cleanup only after human merge or abandon
- Never implements the work or opens fix PRs against the target product repository

### SigmaWrite

- Chat writing style only (no report file, no pull request)
- Soft STE-inspired steers plus hard bans on gibberish and invented words
- Optional pasteable system-prompt block in `SKILL.md`
- Does not rewrite code identifiers or override other skills’ output contracts

## Requirements

The agent needs read access to the target repository. SigmaReview and SigmaPerformance also need authenticated GitHub tooling with permission to push a branch or create a fork and pull request. SigmaPerformance execution additionally follows the authority and safety boundary selected during calibration. SigmaBrief needs GitHub read access (`gh`) when briefing from issues/PRs; it does not require push permission to the product repository. SigmaWrite needs no GitHub access; it only changes how the agent writes in chat.

## License

MIT
