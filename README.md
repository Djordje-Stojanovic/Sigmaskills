# SigmaSkills

High-rigor, portable [Agent Skills](https://agentskills.io/) for Codex, Pi, Claude Code, Cursor, and other compatible coding agents.

## Available skills

### SigmaReview

A one-shot, single-agent, full-repository engineering audit. SigmaReview reviews correctness, feature completeness, architecture, data and concurrency, reliability, security, performance, tests, dependencies, delivery, operations, and applicable domain-specific engineering. It rejects speculative findings, writes exactly one evidence-rich Markdown report, and opens it as a pull request without changing runtime code.

## Install

The easiest cross-agent installation:

```bash
npx skills add https://github.com/Djordje-Stojanovic/Sigmaskills --skill sigmareview
```

For Codex, you can also ask the built-in installer:

```text
$skill-installer install sigmareview from https://github.com/Djordje-Stojanovic/Sigmaskills
```

Manual universal installation:

```bash
git clone https://github.com/Djordje-Stojanovic/Sigmaskills.git
mkdir -p ~/.agents/skills
cp -R Sigmaskills/sigmareview ~/.agents/skills/sigmareview
```

## Run

Codex:

```text
$sigmareview https://github.com/owner/repository
```

Pi:

```text
/skill:sigmareview https://github.com/owner/repository
```

Other Agent Skills-compatible tools can invoke `sigmareview` through their normal skill picker or command syntax.

## What SigmaReview produces

- One file: `SIGMAREVIEW-FINDINGS-YYYY-MM-DD.md`
- One dedicated branch and pull request
- Prioritized, confidence-gated findings with exact evidence
- Implementation-ready remediation and verification steps
- A full repository coverage ledger
- No source fixes, dependency installation, application execution, subagents, or auxiliary analysis files

## Requirements

The agent needs read access to the target repository and authenticated GitHub tooling with permission to push a branch or create a fork and pull request.

## License

MIT
