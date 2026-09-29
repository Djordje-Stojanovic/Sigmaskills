# Changelog

All notable changes to [Sigmaskills](https://github.com/Djordje-Stojanovic/Sigmaskills) are documented here.

## [Unreleased]

### Changed

- The six skills now agree with each other. SigmaShip and SigmaBrief both merge the base branch into a pushed branch (no rebase), use `<base>` (default `main`), delete a squash-merged branch with `git branch -D` only after the PR shows merged, define P1 as SigmaReview does, and use the shell native to the executing machine. In a SigmaShip review round, the `CLEAN | FIXED | BLOCKED` report wins over SigmaBrief's format. The grilling skill is called `/grilling` everywhere. SigmaShip says to write the acceptance criteria by hand when `/to-spec`, `/to-tickets`, or `/grilling` are missing. The README lists these optional companion skills from `mattpocock/skills`. (#65)
- SigmaBrief examples now use its own dispatch format and generic content. (#65)
- SigmaRefactor and the README no longer name a private repository, and they say `laloc` is optional. (#65)
- Tests check that `openai.yaml` lists only Codex products (`chatgpt`, `codex`, `atlas`), that every skill name and description follows the Agent Skills limits, and that every relative link and `#anchor` in the skill folders resolves. (#65)
- Package metadata: `package.json` now has `license` (`MIT`), `bugs`, and `keywords`, so npm shows the license. (#64)
- Docs and changelog match 0.4.0. The CHANGELOG compare links and the 0.4.0 package-size note are fixed, 0.2.1 is marked as a GitHub Release only, and the 0.2.0 sections follow Keep a Changelog order. The installer guide now covers the Link/Copy page, the `a` key, plain mode with `TERM=dumb` and `--json`, Escape in the destination search, and the hidden aliases (`-g`, `--cwd`, `--list`, `check`). The maintainer guide covers `registry:sync`, `registry:validate`, and the role of `.agents/skills` and `skills-lock.json`. ADRs 0005 and 0006 and the wayfinder label note are corrected. (#64)

### Fixed

- `agents/openai.yaml` no longer lists the invalid product `api` in any skill. Codex could ignore a metadata file with an unknown product. (#65)
- SigmaBrief now sets `allow_implicit_invocation: false`, so the host no longer starts it on its own. (#65)
- Two broken `measure.md` links in `sigmareview/references/method.md` now resolve. (#65)
- The migration error message, its comments, and the installer guide now name 0.3.0 as the last version with the old state layout. 0.4.0 already uses the new layout, so the old advice to run `@0.4.0` failed in the same place. (#64)
- The README host list names only hosts that exist in the registry.
- A project `skills-lock.json` from another tool is never rewritten. When the file is a generic (non-Sigma) lock, `install`, `uninstall`, and `restore` leave it byte-identical, print a notice, and still finish the install, uninstall, or restore. The Sigma lock is only written when the file is missing or already a Sigma lock. (#66)
- State and purge-journal paths that escape the project, home, or state folder are rejected when they load, with an error that says the path "escapes" its folder. A crafted `../victim` destination in `state.json` can no longer make `uninstall` or `purge` delete a folder outside the project. (#66)
- `restore` now stops with `occupied-unowned` when a recorded host destination (for example `.claude/skills/<skill>`) holds files Sigma does not own. Before, it deleted those files and put the skill there. (#66)

### Removed

- A private homelab plan that did not belong to this project (`.cursor/plans/`). `.cursor/` is now ignored. (#64)

## [0.4.0] — 2026-09-27

### Added

- SigmaImprove (`sigmaimprove`) finds what would make a product, game, codebase, or system clearly better. It scans a full list of improvement categories (value, speed, control, look and feel, reach, intelligence, trust, engineering, and games) and compares the product with the world's top one to three products and with published bars such as Core Web Vitals and WCAG 2.2. It keeps at least ten entries: ideas with 3–5 weighed options and text sketches, and signals that flag a gap for a person to think about. It files one living issue per category (1–20 per run) and updates those issues on later runs instead of duplicating them. It never edits the system. It grew out of the SigmaCheck draft, which was never released.
- The first SigmaCheck audit of this repository is kept in `docs/audits/SIGMACHECK-2026-09-26.md` as a baseline.
- SigmaShip (`sigmaship`) ships one planned GitHub issue end to end: a feature worktree and branch, a draft PR linked to the ticket, spec, and map, test-first commits pushed as it goes, review rounds by fresh agents until one finds nothing at P0–P2, then merge, ticket closed, branches and worktree deleted, and local `main` verified equal to `origin/main`. It refuses tickets without checkable acceptance criteria and names the skill to run first. It builds on Matt Pocock's `implement` skill.
- `install` takes several skill ids (`install sigmawrite sigmareview`) or `--all`. Every skill is planned first, then all of them install in one transaction: if one fails, none stay installed, and `skills-lock.json` is written once. `--json` prints `{ schemaVersion, plans }` when there is more than one skill; one skill prints the same plan as before. (#38)
- Skill evals. `npm test` now checks the output contract of every skill against good and bad sample outputs, and checks that near-miss prompts route to the right skill. `node scripts/eval-skills.js [skill...]` runs the real skills on a small fixture game with Claude Code, on demand only. See `docs/evals.md`. (#43)

### Changed

- SigmaReview (`sigmareview`) now covers correctness, security (source review plus safe tests on a local instance), and measured performance in one run. It reports every finding with no cap, each written as a self-contained fix brief that an LLM can act on, grouped into waves that can be fixed in parallel. It still never changes code: it publishes one feature-branch pull request with the review file. The report file is now `SIGMAREVIEW-YYYY-MM-DD.md`.
- SigmaBrief (`sigmabrief`) accepts SigmaReview reports and SigmaImprove issues as input and groups briefs into waves, so only independent items run in parallel. Every brief now asks for green baseline checks before changes and ends with a fixed report (`DONE`, `DONE_WITH_CONCERNS`, or `BLOCKED`, plus PR, checks, and open questions). `approval: auto` lets agents record their decisions as rulings instead of waiting. A host's native worktree tool is preferred over manual `git worktree`. A new `session` brief hands the current conversation to a fresh agent.
- The skill picker and `list` now show each skill's short description for people (`short_description` in `agents/openai.yaml`) instead of the agent-facing description cut off mid-word. The picker wraps it onto at most two lines, so narrow terminals show it whole. A skill without that line shows the first sentence of its description. `list --json` still gives the full description. (#39)
- The installer's private files (state, lock, backups, journals, staging) now live in `.agents/.sigmaskills/` (global: `~/.agents/.sigmaskills/`). The folder ignores itself in Git, so `git add -A` no longer stages `.agents/state.json` or backups. Older projects move there on the next write command; `status` and `--dry-run` still read the old layout and write nothing. `--state-dir` and `SIGMA_STATE_DIR` are unchanged. (#34)
- The npm package now ships only the user CLI: about 88 KB smaller unpacked (500,482 B instead of 588,522 B) and 3 fewer files (53 instead of 56). Release and registry automation moved to `scripts/` in the repository, and `sigmaskills release` is gone from the published CLI. Maintainers run `npm run release -- <flags>` from a checkout; the checks it makes are unchanged. (#40)
- Every pull request now rehearses the Release path. A CI job commits the Release identities in a throwaway worktree, then runs the preview, the dispatch checks, and the trusted `validate` and publish steps with a real `npm pack` (`node scripts/release-rehearsal.js`). npm and GitHub lookups, dispatch, and publish are stubbed, so the job needs no secrets. A pull request that breaks packing, such as the `npm pack` JSON bug fixed in 0.2.1, now fails before merge. (#41)
- CI now runs with a read-only token (`permissions: contents: read`) and pins every action to a full commit SHA, like the Release workflows. (#41)
- CI now tests Node.js 22 and 24 on Windows, macOS, and Linux. Node.js 20 reached end of life on 2026-04-30, but `engines` stays at `>=20` for this Release so current users on Node.js 20 can still install; one Linux job on Node.js 20 keeps that promise tested. A later Release may raise it. (#41)
- The README is short again. It keeps the quick start, the skills, one install table, and run examples. Command details moved to [`docs/installer.md`](docs/installer.md); releases, registry automation, tests, and CI moved to [`docs/maintainers.md`](docs/maintainers.md). A test keeps it under 1,500 words, with no paragraph over 80 words. (#42)
- The Agent Host registry follows `vercel-labs/skills` at `7407f38`: Droid and Kilo read project skills from `.agents/skills` (Kilo global: `~/.kilo/skills`), fx and sarvam-code are new hosts, and Antigravity, antigravity-cli, and deepagents leave the universal-prompt list. Existing installs keep their recorded paths.

### Removed

- SigmaPerformance (`sigmaperformance`). Its measurement method and evidence classes are now part of SigmaReview.

### Fixed

- The release tool now treats a breaking change before 1.0.0 as a minor version step, as SemVer allows for 0.y.z versions, instead of jumping to 1.0.0.
- The README no longer points to the v0.2.1 zip as the latest Release.
- The finished 0.3.0 `plan.md` is removed from the repository root; its content lives in issue #3 and PR #29.
- `update` no longer stops when a skill that left the Skill Pack is still installed. The manifest lists retired skills (`sigmaperformance`); `update` leaves them unchanged, lists them under *Retired skills*, and names the `uninstall` command that removes them.
- An unknown skill id now fails with `unknown skill '<id>'` before any planning, for `install`, `update`, `restore`, and `uninstall`. `uninstall --skill nope` said `stale-state` before. (#38)
- A value flag with a missing, empty, or dash-prefixed value now fails with the flag name. Before, `--skill --yes` read `--yes` as a skill id, and a value flag at the end of the command was ignored. One flag table now parses and checks every flag; all current flags and aliases still work. (#38)
- The registry sync test writes into a temporary folder instead of `registry/agent-hosts.json`, so parallel test files no longer read a half-written file and fail at random.
- Update previews show the relevant release notes and correct running-version relation, omit empty sections, and ask for outside-edit choices only when needed. JSON field names and the installed-side relation remain compatible. (#36)
- Lock recovery serializes competing takeovers, preserves fresh incomplete records, and checks unique ownership when releasing. Locks expire after 24 hours; a crash-leftover takeover guard stops safely with recovery instructions. Legacy migration uses the same lock. (#37)
- Untouched copies of earlier Releases are recognized again. `registry/skill-baselines.json` now holds the file hashes of 0.1.0, 0.2.0, 0.2.1, and 0.3.0, rebuilt from their git tags (`node scripts/backfill-baselines.js <tag>...`), and `npm run release -- --write-identities` adds the outgoing Release each time. Such a copy shows as `legacy` with high provenance and upgrades with no `--adopt-*` flag; a changed copy still needs a choice. (#35)
- Install plans now label files from the installer's point of view: *Additions* are files the new Release brings, *Deletions* are files the install removes. They were swapped before. (#35)

## [0.3.0] — 2026-09-08

### Added

- SigmaRefactor (`sigmarefactor`) scans and reconciles the five largest maintained files, reads them fully, discusses behavior-preserving refactoring choices with the user, and verifies approved changes.

### Fixed

- The interactive installer stops repeating unchanged static pages and pauses standard input during cleanup, so confirmed installs return to the shell reliably.
- The installer opens directly to skill selection, keeps destination pages within eight rows, and offers line-based commands in plain terminals. Help preserves cancellation, and short terminals keep focus and controls visible.
- Package tests compare complete trees and bytes for all five skills, including customized reinstall protection and updates.

## [0.2.1] — 2026-08-27 (GitHub Release only)

### Changed

- The Agent Host registry now includes Posit Assistant from the pinned `vercel-labs/skills` revision `dd3ca3c85581`.

### Fixed

- The destination picker paints one compact row per path, windows a live TTY list, groups search hits that share a path, and leaves the alternate screen before cancel or error copy so Windows does not stack or swallow that text.
- Registry Sync no longer fails when a leftover `registry/sync-*` branch still exists: it replaces that generated branch, or reuses a matching open pull request, and still refuses human branches.
- Release packing reads `npm pack --json` after prepack logs, so publication can rebuild the tarball digest.

## [0.2.0] — 2026-08-20

### Added

- Safe Agent Host registry additions and description-only changes may auto-merge after required checks and publish a patch Release through the trusted idempotent publication primitive. Destination, ID, alias, detection, platform, membership, removal, and unknown changes still need owner review. Version calculation serializes concurrent runs against live npm and GitHub state. The generated branch is deleted only after verified merge and matching publication. Automation cannot change skills, CLI behavior, unrelated work, human branches, or major/minor Releases, and it never overwrites an existing npm version.
- Release-candidate qualification packs the published tarball and proves install, adoption, status, update, unsafe resolution, restore, uninstall, uninstall-all, and purge on that artifact. Unknown newer state schemas fail without mutation; supported migrations keep ownership and backup references. The package allowlist, Skill Revisions, and publication preflight agree. Bundled install, status, uninstall, and restore stay offline. CI runs the suite on Windows, macOS, and Linux for Node.js 20+.
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
- The first npm package is `@djordje-stojanovic/sigmaskills` because the unscoped name is too close to an existing package. The installed command remains `sigmaskills`.
- The Sigma Installer's interactive Project Installation through plain `npx @djordje-stojanovic/sigmaskills`, with manifest-driven multi-skill selection, exact destination confirmation, cancellation-safe prompts, and no-color, static, and narrow-terminal modes.
- Structural regression tests (`npm test`) and GitHub Actions CI so skill registry, README wiring, templates, and SigmaWrite soft-steer invariants cannot silently drift.
- Root [`AGENTS.md`](AGENTS.md): mandatory work rules and clear-writing rules, project map, and the `KNOWN_SKILLS` + README + CHANGELOG update rule.

### Fixed

- `npm test` lists `test/*.test.js` files in a runner script so Node.js 20 CI runs the suite without glob expansion. Registry pin hashing ignores CRLF from Windows checkout so the fixture still matches `contentSha256`.

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

[Unreleased]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.2.1
[0.2.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.2.0
[0.1.0]: https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.1.0
