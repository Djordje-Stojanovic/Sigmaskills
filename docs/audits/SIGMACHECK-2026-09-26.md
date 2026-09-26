# SigmaCheck audit — Sigmaskills (2026-09-26)

Setup (unattended defaults, stated as the skill requires): output C (one parent issue with sub-issues) plus this report; all 10 topics; authority "may run tests and the CLI in an isolated temp directory"; context inferred and labeled. Audited commit: `2bd5158` (v0.3.0) plus the SigmaCheck integration on `claude/nice-fermi-453rnk`.

## 1. Verdict

Sigmaskills is a pack of six Markdown skills plus the Sigma Installer, a zero-dependency Node.js CLI that copies or links the skills into Agent Host folders. The engineering floor is high: writes are transactional, the package has no runtime dependencies, and 316 tests run in about 11 seconds on three operating systems. The weak spots are not crashes. They are the places where the installer tells the user something false, stores private data where Git will pick it up, or makes the owner fix the release path by hand every time.

Overall score: **7.1 / 10**. No P0 or P1 findings. Four P2 findings, fourteen P3.

The three decisions that matter most:

1. **Move private installer state out of the committed `.agents/` tree** (SC-001). Today backups, the lock file, and `state.json` sit next to the skills that teams commit.
2. **Make `update` tell the truth** (SC-003, SC-004, SC-005) and **record every earlier Release as a known baseline** (SC-006). Together these decide whether upgrading from 0.3.0 to 0.4.0 is one command or a flag hunt.
3. **Stop adding installer surface** (SC-017) and rehearse the release path in CI (SC-007). 11,162 lines of installer code now serve about 100 KB of Markdown, and every one of the four Releases needed follow-up fixes to the release code.

## 2. Scorecard

| Topic | Avg | Notes |
|---|---|---|
| T1 Purpose & Requirements | 6.8 | Skill overlap and installer surface outgrow the job |
| T2 Correctness & Bugs | 6.8 | Lock race, private state in project, false update labels |
| T3 Security & Privacy | 7.8 | Global writes well gated; CI token and backups leak paths |
| T4 Performance & Latency | 8.5 | Fast enough; nothing worth optimizing now |
| T5 Simplicity & Size | 7.0 | Zero deps; maintainer code ships to users |
| T6 Architecture & Maintainability | 7.2 | Clean modules, repetitive CLI parser |
| T7 Reliability & Operations | 7.3 | Strong recovery; release path breaks every time |
| T8 UX & Design | 6.6 | Update preview misleads; one skill per command |
| T9 Intelligence & Automation | 6.5 | No skill evals; baselines never populated |
| T10 Verification, Cost & Evolution | 6.8 | Fast tests; stale docs; EOL Node in CI |

| # | Check | Score | Reason |
|---|---|---|---|
| 1 | Requirement validity | 8 | Each skill has a clear job; installer need is real |
| 2 | Scope discipline | 6 | SC-014 overlapping audit skills; SC-017 installer surface |
| 3 | Spec vs. reality | 6 | SC-003 README promises a changelog the tool never shows |
| 4 | Journey completeness | 7 | SC-006 upgrade of an untouched copy needs a flag |
| 5 | Success metrics | 6 | SC-017 no usage data behind purge/restore/uninstall-all |
| 6 | Logic and boundaries | 7 | SC-004 inverted release relation label |
| 7 | Error handling | 8 | Errors surface; SC-011 one misleading message |
| 8 | Concurrency and state | 6 | SC-002 two processes can both hold the lock |
| 9 | Data integrity | 6 | SC-001 private state and backups inside committed tree |
| 10 | Contracts | 7 | SC-006 baseline contract exists but is empty |
| 11 | AuthN / AuthZ | 9 | Global writes need `--global --yes`; purge needs typed phrase |
| 12 | Untrusted input | 8 | Registry sync validates paths, traversal, control chars |
| 13 | Secrets and supply chain | 7 | SC-012 CI has no `permissions:` and tag-pinned actions |
| 14 | Privacy | 7 | SC-001 backups of personal customizations can be pushed |
| 15 | Abuse resistance | N/A | Local CLI, no service surface |
| 16 | End-to-end latency | 8 | Measured 75–90 ms per command vs 34 ms bare Node |
| 17 | Throughput and scale | 9 | Six skills; linear and tiny |
| 18 | Startup and load | 8 | Every command imports all modules and hashes every skill; bounded |
| 19 | Resource efficiency | 9 | Measured: 143 KB tarball, no deps |
| 20 | Algorithmic and I/O waste | 8 | Catalog re-hash per run is cheap at this size |
| 21 | Dead weight | 6 | SC-008 maintainer code shipped; SC-013 stale `plan.md` |
| 22 | Duplication | 6 | SC-016 parser branches; README repeats install lists four ways |
| 23 | Over-abstraction | 6 | SC-017 four adopt flags, two update flags, three removal commands |
| 24 | Dependency weight | 10 | Zero runtime dependencies |
| 25 | Footprint | 7 | SC-008 about 80 KB of 588 KB unpacked is maintainer-only |
| 26 | Boundaries and coupling | 7 | SC-008 user CLI imports release module |
| 27 | Data model | 7 | SC-001 private and shared state share one folder |
| 28 | Readability | 7 | SC-016 110-line if/else parser |
| 29 | Configuration | 8 | Sensible defaults; `SIGMA_STATE_DIR` override |
| 30 | Technical debt | 7 | SC-006 empty baselines since PR #12 |
| 31 | Failure modes | 8 | Journals and rollback on every mutating command |
| 32 | Observability | 8 | Readable errors, `--json` everywhere |
| 33 | Recovery | 8 | Backups integrity-checked before restore |
| 34 | Build and deploy | 5 | SC-007 release code fixed after every cut |
| 35 | Capacity and cost of operation | N/A | No hosted service |
| 36 | Time to value | 7 | One `npx` command; SC-013 README is 3,668 words |
| 37 | Flow friction | 6 | SC-009 one skill per non-interactive install |
| 38 | Feedback and states | 5 | SC-003, SC-004, SC-005, SC-011 |
| 39 | Visual quality | 7 | SC-010 picker shows truncated model-facing description |
| 40 | Accessibility and reach | 8 | `NO_COLOR`, plain, static, narrow, reduced motion |
| 41 | Smart defaults | 7 | SC-006 official copies treated as unknown |
| 42 | AI/ML quality | 5 | SC-015 no behavioral evals for any skill |
| 43 | LLM efficiency | 8 | Skill bodies are compact; references load on demand |
| 44 | Automation of toil | 6 | SC-007 manual release repair; SC-006 manual baselines |
| 45 | Search and heuristics | N/A | Destination search is substring only and adequate |
| 46 | Test value | 7 | Strong installer tests missed SC-003/004/005/006 |
| 47 | Test speed and determinism | 9 | Measured: 316 tests, about 11 s, no flakes seen |
| 48 | Documentation truth | 5 | SC-013 stale zip line (fixed here), stale `plan.md`, walls of text |
| 49 | Unit economics | N/A | Free package, no infrastructure |
| 50 | Currency and upgrade path | 6 | SC-018 CI tests EOL Node 20, not Node 24 LTS |

## 3. Action plan

Tracking: parent issue [#31](https://github.com/Djordje-Stojanovic/Sigmaskills/issues/31).

| Order | Findings | Work | Issue | Depends on | Done when |
|---|---|---|---|---|---|
| 1 | SC-014 | Integrate SigmaCheck (this PR) | #32 | — | `npm test` green with six skills |
| 2 | — | Cut and publish Release 0.4.0 | #33 | 1 | npm, tag, and GitHub Release show 0.4.0 |
| 3 | SC-001 | Keep private state out of commits | #34 | — | Fresh install leaves `git status` showing only skills and lock |
| 4 | SC-006 | Record baselines for every Release | #35 | — | Untouched 0.3.0 copy adopts under 0.4.x without flags |
| 5 | SC-003, SC-004, SC-005 | Truthful update preview | #36 | 4 | Dry-run shows correct relation and the changelog between versions |
| 6 | SC-002 | Safe lock takeover | #37 | — | Two-process test never has two holders |
| 7 | SC-009, SC-011, SC-016 | Multi-skill install and strict flags | #38 | — | `install a b` and `install --all` work; missing values error |
| 8 | SC-010 | Human text in the picker | #39 | — | Picker shows `short_description` |
| 9 | SC-008 | Ship only user code | #40 | — | Tarball has no release or registry automation files |
| 10 | SC-007, SC-012, SC-018 | Release rehearsal and CI hardening | #41 | 9 | PR CI packs and validates a release candidate |
| 11 | SC-013 | Short, true docs | #42 | 1 | README under 1,500 words; `plan.md` gone |
| 12 | SC-015 | Behavior evals for skills | #43 | — | One eval per skill runs on demand |
| 13 | SC-017 | Decide the installer's feature freeze | #44 | — | Written decision (ADR) |

## 4. Findings

### SC-001 — Private installer state, backups, and lock land inside the committed `.agents/` tree

- Topic/check: T2 #9, T3 #14, T6 #27 · **P2** · Measured · confidence 0.95 · effort M
- Location: `src/state.js` `getProjectStateDir` returns `<project>/.agents`; `src/backup.js` `getBackupRoot` returns `<stateDir>/backups`; `src/transaction.js` lock at `<stateDir>/.sigma.lock`.
- Mechanism: Project Installation writes `state.json`, `backups/<skill>/<stamp>/`, `.sigma.lock`, and uninstall journals into `.agents/`, the same folder that holds `.agents/skills/`, which teams commit so agents can load the skills. The installer adds no ignore rule. The CLI help calls this "private machine state".
- Trigger: install, then `update --outside-edit replace` or `uninstall --changed backup`, then `git add -A`.
- Impact: full copies of personal Skill Customizations and machine state go into shared history. A crashed run can commit a stale lock.
- Measured: a fresh six-skill install followed by `git init && git add -A` stages `.agents/state.json`.
- Counterevidence: `skills-lock.json` is the intended shared lock and lives at the project root, which confirms `state.json` is meant to be private. No `.gitignore` handling exists anywhere in `src/`.
- Fix: move private state to one folder that ignores itself, for example `.agents/.sigmaskills/` with a generated `.gitignore` containing `*`. Migrate existing `state.json` and backups on first run. This is a one-way door for the state location, so decide it once.
- Verification: a test installs, forces a backup, runs `git init && git add -A`, and asserts only `.agents/skills/**` and `skills-lock.json` are staged.

### SC-003 — `update` never shows the changes between the installed and running Release

- Topic/check: T1 #3, T8 #38 · **P2** · Measured · confidence 0.95 · effort S
- Location: `src/update.js` `readChangelog` matches only `## [Unreleased]`.
- Mechanism: published packages have an empty `[Unreleased]` section, so the preview prints only that heading. The README says update "shows the bundled changelog".
- Trigger: install with 0.3.0, run `update --dry-run` with a newer package. Observed output: `Changelog: ## [Unreleased]` and nothing else.
- Impact: the user approves an update blind.
- Fix: print every `## [x.y.z]` section newer than the installed Release and not newer than the running one.
- Verification: fixture changelog with three versions; installed 0.3.0, running 0.4.1 prints exactly 0.4.0 and 0.4.1.

### SC-006 — Official copies from earlier Releases are classified "unverified"

- Topic/check: T2 #10, T9 #41, T6 #30 · **P2** · Measured · confidence 0.9 · effort M
- Location: `registry/skill-baselines.json` has `"skills": {}` since PR #12; `src/release.js` never writes baselines.
- Mechanism: adoption recognizes legacy trees only through that file. The README promotes `npx skills add` and manual copy for every skill, so most users hold unmanaged official copies.
- Trigger: copy `sigmawrite` from 0.3.0 into `.agents/skills`, then run `install sigmawrite` from a newer package. Observed: `unverified, provenance low` and an error that requires `--adopt-*`. The same plan labels a file that upstream adds as a "Deletion".
- Impact: every Release makes every non-installer user pass an expert flag, which defeats adoption.
- Fix: `release --write-identities` appends the outgoing Release's per-file hashes to the baselines file. Backfill 0.1.0–0.3.0 from the git tags. Label the diff from the installer's point of view (adds, replaces, deletes).
- Verification: test adopts an untouched copy of every earlier Release as `legacy` with high provenance and no flag.

### SC-007 — The release path fails on every real run and is fixed by hand afterwards

- Topic/check: T7 #34, T9 #44 · **P2** · Proven (git history) · confidence 0.9 · effort M
- Location: `src/release.js`, `src/release-ci.js`, `.github/workflows/release.yml`.
- Mechanism: the release code runs for real only at publish time. History shows a follow-up fix after each cut: `958866e` (npm on Windows), `2f1d056` (name collision), `dd35041` (npm pack JSON after prepack logs), `36a362b` (GH_TOKEN for validate), and `2bd5158` changed `release.js` inside the 0.3.0 cut.
- Impact: every Release costs the owner extra commits and risks a half-published state.
- Fix: a CI job on pull requests runs `release --dry-run` and the `validate` step against the PR head with real `npm pack` and stubbed network and publish.
- Verification: reintroduce the `dd35041` bug on a branch; the new job fails.

### SC-002 — Two processes can both hold the concurrency lock

- Topic/check: T2 #8 · P3 · Proven · confidence 0.85 · effort S
- Location: `src/transaction.js` `acquireConcurrencyLock`.
- Mechanism: stale and unreadable locks are handled by "unlink, then create". Interleaving: A and B both read a lock from a dead PID; A unlinks and creates its lock; B unlinks A's lock and creates its own; both proceed. An empty lock file (A has opened but not written) also gets deleted by B. PID reuse makes a stale lock look alive forever, with no age limit.
- Impact: two installers in one project can interleave state writes. Rare, but it is exactly the case the lock exists for.
- Fix: take over a stale lock by renaming it to a unique name first (atomic), then create; treat an empty lock younger than a few seconds as held; add an age limit.
- Verification: a test that races two takeovers with an injected pause asserts one winner.

### SC-004 — `update` labels a newer running Release as "older"

- Topic/check: T2 #6 · P3 · Measured · confidence 0.95 · effort S
- Location: `src/update.js` `releaseRelation` returns the relation of installed to running; the formatter prints it after the running version.
- Observed: `Running Release: 0.4.0 (older)` with 0.3.0 installed.
- Fix: print `(newer)` from the running side, or rename the field and label it `installed is older`.
- Verification: formatter test for older, same, and newer.

### SC-005 — The update preview asks for a flag that apply does not need, and pads output

- Topic/check: T8 #37, #38 · P3 · Measured · confidence 0.9 · effort S
- Mechanism: for a clean skill with only upstream changes, dry-run prints `Prompt: Resolve upstream-only outside-edit cases with skip, export, or replace.`, yet `update --yes` applies without `--outside-edit`. With nothing to do, the output still prints about 25 lines of empty `(none)` sections.
- Fix: prompt only for local-only and concurrent cases; omit empty sections in human output (keep them in `--json`).
- Verification: snapshot tests for a clean upstream-only update and a no-op update.

### SC-008 — Maintainer-only code ships to every user

- Topic/check: T5 #21, #25, T6 #26 · P3 · Measured · confidence 0.9 · effort M
- Location: `package.json` `files` includes all of `src/`; tarball contains `src/release.js`, `src/release-ci.js`, and `src/registry/automation*.js` and `sync.js` (about 80 KB of 588 KB unpacked). `release` appears in the user `--help`, and `src/cli.js` imports the release module on every run.
- Fix: move release and registry automation into a maintainer folder outside `files` and run it from the checkout (workflows already do). Remove `release` from the user CLI.
- Verification: tarball test forbids those paths; `--help` has no `release`.

### SC-009 — Non-interactive install takes one skill per command

- Topic/check: T8 #37 · P3 · Measured · confidence 0.95 · effort S
- Observed: `sigmaskills install sigmawrite sigmareview` fails with `unknown option or command: sigmareview`. There is no `--all`.
- Fix: accept several ids and `--all` in one transaction and one lock write.
- Verification: CLI test installs three skills in one call and writes the lock once.

### SC-010 — The skill picker shows a truncated model-facing description

- Topic/check: T8 #39 · P3 · Measured · confidence 0.9 · effort S
- Observed: `Perform a one-shot, single-agent, full-repository engineering audit and publis…`. Each skill already has a human `short_description` in `agents/openai.yaml`.
- Fix: show `short_description` in the focus area; fall back to the first sentence of the description.
- Verification: interactive test asserts the short description for every skill.

### SC-011 — Misleading errors for unknown skills and swallowed flags

- Topic/check: T2 #7, T8 #38 · P3 · Measured · confidence 0.9 · effort S
- Observed: `uninstall --skill nope --yes` prints `stale-state stopped uninstall of 'nope'`. `--skill --yes` treats `--yes` as a skill id. A value flag at the end (`--adopt-changed`) is silently ignored.
- Fix: validate skill ids against the catalog first; reject a missing or dash-prefixed value.
- Verification: CLI tests for each case.

### SC-012 — CI workflow runs with default token permissions and tag-pinned actions

- Topic/check: T3 #13 · P3 · Proven · confidence 0.85 · effort S
- Location: `.github/workflows/ci.yml` has no `permissions:` and uses `actions/checkout@v4`, while the release workflows pin SHAs and set `permissions: {}`.
- Fix: `permissions: contents: read` and SHA pins that match the other workflows.

### SC-013 — Documentation is long and partly stale

- Topic/check: T10 #48, T8 #36 · P3 · Measured · confidence 0.9 · effort M
- Evidence: README is 3,668 words; single paragraphs reach 294 words (update section). The README pointed to the v0.2.1 zip as current after v0.3.0 shipped (fixed in this PR). `plan.md` at the root is the finished 0.3.0 spec for issue #3.
- Fix: README keeps quick start, skills, and one install table; command details move to `docs/installer.md`. Remove `plan.md` (its content lives in the closed issue and PR #29).

### SC-014 — SigmaCheck and SigmaReview overlap

- Topic/check: T1 #2 · P3 · Proven · confidence 0.8 · effort S
- Mechanism: both are full-repository audits with report PRs. Without a stated boundary, users pick at random and both skills drift.
- Fix: this PR states the boundary in the README. The trigger descriptions should also name the other skill.

### SC-015 — No behavioral evaluation for any skill

- Topic/check: T9 #42, T10 #46 · P3 · Needs measurement · confidence 0.8 · effort L
- Mechanism: tests check frontmatter, headings, and packaging. A skill edit that breaks its output contract passes CI.
- Measurement: run each skill on a fixed fixture repo and check the output contract (file name, sections, score table). Decide from that whether to gate CI.

### SC-016 — The CLI parser repeats one pattern for every flag

- Topic/check: T5 #22, T6 #28 · P3 · Proven · confidence 0.9 · effort S
- Location: `src/cli.js` `parseCliArgs` (about 110 lines of `--x` / `--x=` pairs) and five hand-written enum checks.
- Fix: one table of flags with type and allowed values; one loop; one validator. This also fixes the swallowed-value cases in SC-011.

### SC-017 — The installer grows faster than the job it does

- Topic/check: T1 #2, #5, T5 #23 · P3 · Needs measurement · confidence 0.8 · effort decision
- Evidence: 11,162 lines of installer code for about 100 KB of Markdown; ten commands, twelve resolution flags (`--adopt-*` ×4, `--outside-edit`, `--malformed-markers`, `--clean`, `--changed`, …). No usage data exists for purge, restore, or uninstall-all.
- Fix: freeze new installer commands; record the decision as an ADR; merge the four `--adopt-*` flags into one when SC-006 removes most of their triggers.

### SC-018 — CI tests an end-of-life Node.js and skips the current LTS

- Topic/check: T10 #50 · P3 · Proven · confidence 0.85 · effort S
- Evidence: CI matrix is Node 20 and 22; Node 20 reached end of life on 2026-04-30 and Node 24 is the active LTS.
- Fix: test 22 and 24; decide whether `engines` stays at `>=20`.

## 5. Strengths worth keeping

- Zero runtime dependencies and a 143 KB tarball. Keep it that way while fixing SC-016.
- Atomic temp-and-rename writes, journals, and integrity-checked backups. SC-001 should move them, not weaken them.
- 316 tests in about 11 seconds on Windows, macOS, and Linux. New tests for these findings should use the same temp-directory style.
- Owner-gated release with an approved commit, version, and digest. SC-007 should rehearse it, not bypass it.

## 6. Coverage

- Deep-read: `src/cli.js`, the lock in `src/transaction.js`, state and backup location code, `src/update.js` release relation and changelog, adoption baselines, CI workflows, README, CHANGELOG, AGENTS.md, CONTEXT.md, `plan.md`, all `SKILL.md` files.
- Run in temp directories: install, status, update across a simulated 0.4.0, restore, uninstall, plain-mode interactive start, `release --dry-run`, full test suite, per-file test timing.
- Sampled: `src/interactive.js`, `src/restore.js`, `src/uninstall.js`, `src/purge.js`, registry automation.
- Not verified: real Windows junction behavior, real TTY rendering, the release and registry workflows on GitHub. The open registry pull request (#30) did not auto-merge; the cause was not investigated, so it is not a finding.
