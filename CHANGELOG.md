# Changelog

All notable changes to [Sigmaskills](https://github.com/Djordje-Stojanovic/Sigmaskills) are documented here.

## [Unreleased]

### Added

- The Sigma Installer recommended link method: Windows directory junctions and macOS/Linux symbolic links to the canonical `.agents/skills` copy, with an explicit copy alternative, informed copy fallback, and ownership records for canonical dependencies.
- The Sigma Installer Project Installation destination picker: every bundled Agent Host stays searchable, only `.agents/skills` is selected by default, host-specific destinations require an explicit choice, and ownership state records each managed copy.
- The Sigma Installer's interactive Project Installation through plain `npx sigmaskills`, with manifest-driven multi-skill selection, exact destination confirmation, cancellation-safe prompts, and no-color, static, and narrow-terminal modes.
- Structural regression tests (`npm test`) and GitHub Actions CI so skill registry, README wiring, templates, and SigmaWrite soft-steer invariants cannot silently drift.
- Root [`AGENTS.md`](AGENTS.md): mandatory work rules and clear-writing rules, project map, and the `KNOWN_SKILLS` + README + CHANGELOG update rule.

## [0.1.0] — 2026-08-11

First public release. Portable [Agent Skills](https://agentskills.io/) for Codex, Pi, Claude Code, Cursor, and compatible hosts.

### Idea

Ship high-rigor, installable agent skills (not apps): full-repo audits, performance investigation, parallel-agent briefing, and clear technical writing voice — each with a tight operating contract and `npx skills add` / Codex `$skill-installer` install paths.

### Skills

- **SigmaReview** (`sigmareview`) — One-shot full-repository engineering audit; single findings Markdown report opened as a report-only PR; no runtime code changes.
- **SigmaPerformance** (`sigmaperformance`) — Calibrated, audit-only performance investigation; measured and mechanically proven bottlenecks; single report PR; no runtime-source edits by default.
- **SigmaBrief** (`sigmabrief`) — Prompt factory: turns issues/work into paste-ready agent briefs; chat-only; does not implement or open product fix PRs.
- **SigmaWrite** (`sigmawrite`) — STE-inspired clear technical English for explanations; soft steers (not hard numbered rules); pasteable system-prompt block; chat style only.

### Repository

- MIT license and root README with multi-host install/run/output contracts (Codex, Claude Code, Cursor, Pi, OpenCode, LAPI-style paths, and Agent Skills–compatible TUIs).
- GitHub Issue Forms + PR template (from github-issue-kit), tailored to Agent Skills / prompts / templates work.
- Packaged GitHub Release **v0.1.0** with source zip of all skills.

### Commits since inception

| Date | Commit | Summary |
|------|--------|---------|
| 2026-07-11 | `1867a70` | Publish SigmaReview skill |
| 2026-07-11 | `ddca5b7` | Publish SigmaReview source files |
| 2026-07-12 | `2343d5b` | Add SigmaPerformance skill |
| 2026-07-29 | `71b2c09` | Add SigmaBrief prompt-factory skill |
| 2026-07-29 | `462d291` | Merge PR #1 (`feat/sigmabrief`) |
| 2026-08-10 | `8dcf2b4` | Add GitHub issue forms and PR template from github-issue-kit |
| 2026-08-10 | `3ef4cd8` | Tailor GitHub issue forms and PR template to SigmaSkills |
| 2026-08-11 | `9631834` | Add SigmaWrite skill for STE-inspired clear technical English |
| 2026-08-11 | `5dab832` | Add CHANGELOG and mark v0.1.0 as the first Sigmaskills release |
| 2026-08-11 | `124a666` | Polish v0.1.0 docs for multi-host install and use |

[0.1.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.1.0
