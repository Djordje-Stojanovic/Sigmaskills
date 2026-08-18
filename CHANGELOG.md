# Changelog

All notable changes to [Sigmaskills](https://github.com/Djordje-Stojanovic/Sigmaskills) are documented here.

## [Unreleased]

### Added

- The Sigma Installer `update` command classifies outside-customization edits, shows local-only and concurrent effects, and lets a user skip, export, or approve a whole-skill replace with an integrity-checked private backup. Skip leaves that skill unchanged; export uses a planned path, refuses collisions, and removes partial output; a prior backup is kept until the new tree and metadata commit, and cleanup failure may retain two backups with recorded debt.
- The Sigma Installer `update` command replaces selected whole skills with the Release bundled in the running CLI: it groups changed and unchanged skills, shows changelog and whole-skill diffs, preserves Skill Customization bytes exactly, updates the canonical copy and its links or matching copies together, and stops without mutation on unknown state schemas, missing bundled revisions, or unsafe drift.
- The Sigma Installer `status` command reports managed Project and Global Installation state and drift without writing files or contacting the network: live hashes and link checks classify clean copies, valid Skill Customization, outside edits, missing or extra resources, malformed markers, missing destinations, stale state, broken or wrong-target links, and copy disagreement.
- The Sigma Installer hardens Emberforge for real terminals: the accepted warm LAPI palette stays, layouts reflow below 76 columns, `?` opens keyboard help, reduced-motion/`NO_COLOR`/CI/JSON/non-TTY modes drop animation, truecolor through ASCII fallbacks keep safety copy, and the cursor restores after success, failure, interrupt, EOF, and exceptions.
- The Sigma Installer protects Global Installation with two confirmations, sandboxed user-home paths, schema-versioned global state, and the same adoption rules as Project Installation: `--global` plus `--yes` are required to write; CI, TTY, JSON, and Agent Host detection never imply that authority.
- The Sigma Installer migrates changed, duplicate, older, pre-marker, and unverified Sigma-looking trees with explicit replace, skip, or export choices: known legacy provenance requires a bundled baseline, a complete private backup is committed before replace, valid customization is preserved, and malformed markers are not guessed.
- The Sigma Installer adopts exact current official copies and valid links in place: valid Sigma state, then exact bundled Skill Revision, then resolved link target. Generic `skills-lock.json` entries never imply Sigma ownership.
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
