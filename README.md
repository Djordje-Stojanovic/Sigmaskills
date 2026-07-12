# SigmaSkills

High-rigor, portable [Agent Skills](https://agentskills.io/) for Codex, Pi, Claude Code, Cursor, and other compatible coding agents.

## Available skills

### SigmaReview

A one-shot, single-agent, full-repository engineering audit. SigmaReview reviews correctness, feature completeness, architecture, data and concurrency, reliability, security, performance, tests, dependencies, delivery, operations, and applicable domain-specific engineering. It rejects speculative findings, writes exactly one evidence-rich Markdown report, and opens it as a pull request without changing runtime code.

### SigmaPerformance

A calibrated, audit-only, full-repository performance engineering system. It maps complete user journeys, uses controlled measurement and mechanically conclusive source evidence, separates confirmed bottlenecks from measurement-required opportunities, and publishes one structured report PR. Runtime code remains unchanged.

## Install

Install either skill with the cross-agent installer:

```bash
npx skills add https://github.com/Djordje-Stojanovic/Sigmaskills --skill sigmareview
npx skills add https://github.com/Djordje-Stojanovic/Sigmaskills --skill sigmaperformance
```

For Codex:

```text
$skill-installer install sigmareview from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmaperformance from https://github.com/Djordje-Stojanovic/Sigmaskills
```

Manual universal installation:

```bash
git clone https://github.com/Djordje-Stojanovic/Sigmaskills.git
mkdir -p ~/.agents/skills
cp -R Sigmaskills/sigmareview ~/.agents/skills/sigmareview
cp -R Sigmaskills/sigmaperformance ~/.agents/skills/sigmaperformance
```

## Run

Codex:

```text
$sigmareview https://github.com/owner/repository
$sigmaperformance https://github.com/owner/repository
```

Pi:

```text
/skill:sigmareview https://github.com/owner/repository
/skill:sigmaperformance https://github.com/owner/repository
```

Other Agent Skills-compatible tools can invoke either skill through their normal skill picker or command syntax.

SigmaPerformance begins with two compact calibration batches covering agent topology, execution authority, stress permission, evidence access, performance priorities, and representative workloads. It then runs autonomously.

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

## Requirements

The agent needs read access to the target repository and authenticated GitHub tooling with permission to push a branch or create a fork and pull request. SigmaPerformance execution additionally follows the authority and safety boundary selected during calibration.

## License

MIT
