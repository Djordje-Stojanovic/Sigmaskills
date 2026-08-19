# Changelog

All notable changes to [Sigmaskills](https://github.com/Djordje-Stojanovic/Sigmaskills) are documented here.

## [Unreleased]

### Added

- Guarded Agent Host registry automation fetches a pinned upstream revision as data, runs converter code only from an exact trusted default-branch SHA, and opens a tightly scoped pull request limited to `registry/agent-hosts.json`, `registry/source.json`, and the pinned upstream fixture. Semantic classification allows only validated new hosts and description-only changes; path, ID, alias, detection, platform, membership, removal, and unknown changes stay blocked. Generated pull requests record the upstream commit, full semantic diff, validation evidence, and blocked reasons. Forks, human branches, stale heads, moved default branches, failed checks, and concurrent runs cannot be auto-authorized. This automation does not auto-merge, publish npm, close unrelated issues or pull requests, or delete unrelated branches.
- The Sigma Installer `release` command prepares one immutable publication preview from the accepted source commit and, after `--expected-commit`, `--expected-version`, and `--expected-digest`, dispatches the trusted GitHub workflow that rebuilds that commit, verifies the artifact, and publishes matching git tag, GitHub Release, and npm provenance under `latest`. `--yes` is not authority. Missing npm reservation, trusted publisher, protected `release` environment, or a conflicting version/tag/Release fails closed. Partial success is retried without overwriting versions or duplicating Releases. Ordinary merges never publish.
- The Sigma Installer `purge` command removes all Sigma-owned active content, customizations, locks, state, journals, and backups in one explicit Project or Global scope: it prints an exact ownership plan, requires the typed phrase `purge SigmaSkills` (or `--confirm-purge` with that phrase), and does not treat `--yes`, CI, non-TTY, or JSON as authority. Purge never infers ownership from folder names. Unowned occupants stop the command. Durable journaling and reversible quarantine keep the ownership manifest until owned trees are moved; interrupted cleanup leaves recoverable quarantined state.
- The Sigma Installer `uninstall --all` command composes Uninstall Review across every recorded Sigma skill in one explicit Project or Global scope: there is no review-skipping fast path; the aggregate plan lists every skill, owned destination, canonical dependency, state change, and retained backup; keep choices leave shared state intact; changed skills default to backup so snapshots stay restorable; project and global scopes stay isolated; cancellation or failure writes a durable recovery journal and restores the failed skill; human, dry-run, and JSON results report removed, retained, skipped, and failed skills.
- The Sigma Installer `uninstall` command runs Uninstall Review per selected skill: clean skills offer remove or keep; changed, customized, or malformed skills offer backup-and-remove, keep, export, or permanent-delete-current. The preview lists every path, method, scope, and remaining canonical dependency. Execution revalidates leaves, deletes a link itself never its target, keeps canonical content while dependents remain, leaves older backups on permanent delete, and writes state only after filesystem commit. Missing, stale, unowned, divergent, and wrong-target cases stop without partial ownership.
- The Sigma Installer `restore` command returns the latest retained backup for a skill: the preview names Release, Skill Revision, creation date, verified size, scope, canonical target, and affected links or copies; content and metadata are integrity-checked and staged before any live write; a successful restore makes the displaced tree the new one-step backup; identical content is a no-op; missing, truncated, tampered, schema-incompatible, insufficient-space, stale-ownership, occupied-unowned, and failed Windows fallback cases write nothing.
- The Sigma Installer `update` command diagnoses missing, duplicate, reversed, nested, and malformed customization markers, blocks automatic update for that skill, shows exact proposed repair bytes when a unique mechanical repair exists, and requires `--malformed-markers skip|repair|replace`. Repair never infers marker boundaries; skip leaves the skill while others continue; replace backs up then clean-installs. Combined outside drift keeps all content until both resolutions are explicit, and failure paths write nothing partial.
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
