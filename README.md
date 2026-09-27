# SigmaSkills

**High-rigor Agent Skills for every serious coding agent.**

Portable [Agent Skills](https://agentskills.io/) that install once and run on **Codex**, **Claude Code**, **Cursor**, **Pi**, **OpenCode**, **LAPI**, Reasonix-class TUIs, Kimi/Muse-style hosts, and any tool that reads a `SKILL.md`.

| | |
|---|---|
| **Release** | [**v0.4.0**](https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.4.0) |
| **Changelog** | [CHANGELOG.md](CHANGELOG.md) |
| **License** | [MIT](LICENSE) |
| **Spec** | [agentskills.io](https://agentskills.io/) |

```text
  Σ  review     →  find and prove what is wrong, one PR an LLM can fix from
  Σ  improve    →  ideas versus the world's best, one living issue per category
  Σ  refactor   →  user-guided, behavior-preserving code reduction
  Σ  brief      →  paste-ready agent briefs, chat only
  Σ  ship       →  one planned ticket to a merged, cleaned-up PR
  Σ  write      →  clear STE-inspired technical English
```

---

## Quick start

Start the first-party Sigma Installer in a project:

```bash
npx @djordje-stojanovic/sigmaskills
```

Select any set of skills. By default the installer writes only to `.agents/skills/<id>` and lists every Agent Host that reads that universal destination. Host-specific directories such as `.claude/skills` or `.pi/skills` stay unselected until you choose them. Selected host destinations use Windows directory junctions or macOS/Linux symbolic links to the canonical copy; `--copy` writes an independent managed copy instead. Link failure reports the exact cause and offers copy — the installer never changes method silently. Exact current official copies and valid links are adopted in place without rewriting skill bytes. An untouched copy of an earlier Release (from `npx skills add`, the Codex installer, or a manual copy) matches a bundled baseline in `registry/skill-baselines.json`, shows as `legacy` with high provenance, and upgrades with no flag after a private backup; `--adopt-legacy skip|export` still overrides. Changed, older, pre-marker, and unverified Sigma-looking trees are classified with a file diff and provenance confidence; replace commits a private backup first, skip leaves the tree, and export writes a collision-safe copy. Pre-marker extra content is never guessed into the customization block; malformed markers stop unless you pass an explicit `--adopt-malformed` choice. The confirmation plan shows every full destination path and method. Press `g` in the skill picker for Global Installation: an immediate scope warning appears, then a second confirmation repeats every Agent Host, resolved path, method, overwrite effect, and backup action. Non-interactive Global writes need both `--global` and `--yes`; CI, TTY, JSON, and Agent Host detection never imply that authority. To install skills without the interactive interface, name one or more skill ids, or pass `--all`. Several skills install in one transaction: every skill is planned first, and if one fails, none stay installed. `skills-lock.json` is written once. With `--json`, several skills print `{ "schemaVersion": 1, "plans": [...] }`; one skill prints one plan, as before. An unknown skill id stops with `unknown skill '<id>'` before anything is planned. A flag that needs a value stops with the flag name when the value is missing or starts with `-`; write `--flag=value` for a value that really starts with `-`.

```bash
npx @djordje-stojanovic/sigmaskills install sigmawrite --project .
npx @djordje-stojanovic/sigmaskills install sigmawrite sigmareview sigmaship --project .
npx @djordje-stojanovic/sigmaskills install --all --project .
npx @djordje-stojanovic/sigmaskills install sigmawrite --project . --destination .claude/skills
npx @djordje-stojanovic/sigmaskills install sigmawrite --project . --destination .claude/skills --copy
npx @djordje-stojanovic/sigmaskills install sigmawrite --global --dry-run
npx @djordje-stojanovic/sigmaskills install sigmawrite --global --yes
```

Then invoke with your host’s normal skill syntax (`$sigmawrite`, `/skill:sigmawrite`, skill picker, …).

---

## The skills

| Skill | Id | Job | Output |
|-------|-----|-----|--------|
| **SigmaReview** | `sigmareview` | Find and prove what is wrong: bugs, security, performance, tests | One feature-branch PR with one review file |
| **SigmaImprove** | `sigmaimprove` | Find what would make it clearly better, measured against the world's best | One living issue per category (1–20), updated on every run |
| **SigmaBrief** | `sigmabrief` | Prompt factory for parallel / single agents | Chat briefs only |
| **SigmaShip** | `sigmaship` | Ship one planned ticket: build, review rounds, merge, clean up | One merged PR, closed ticket, main in sync |
| **SigmaWrite** | `sigmawrite` | Clear STE-inspired technical English | Chat writing voice |
| **SigmaRefactor** | `sigmarefactor` | Safe, user-approved large-file refactoring | Discussion, changes, and verification |

### Which one do I need?

SigmaReview and SigmaImprove split on one question: **is it wrong, or could it be better?**

- If a test, a doc, a stated goal, or a budget can prove it wrong, it is a SigmaReview finding. Examples: a crash, a security hole, a page that breaks its latency budget, a level that renders the wrong texture.
- If good people could disagree about the answer, it is a SigmaImprove idea. Examples: weak character animation, a missing boss level, an onboarding flow with too many steps.
- If the code is only too large and behavior must not change, it is SigmaRefactor.

The skills chain into two loops: **fix** (SigmaReview → review PR → SigmaBrief or SigmaShip fix each finding → merge) and **grow** (SigmaImprove → category issues → specs and tickets → SigmaShip).

### SigmaReview

Finds everything that breaks the system's own promises: bugs, security holes (source review plus safe tests on a local instance), slow and wasteful paths (measured when you allow execution), broken rendering, and weak tests. Every finding carries a location, a mechanism, an impact, an evidence class (measured or proven), a fix, and a proof test, written so an LLM can fix it from that finding alone. There is no cap: 1 finding or 1,000 go in one review file on one feature-branch pull request. It never changes your code.

### SigmaImprove

Names the world's top one to three products in the field, then uses the product like a new user, then looks through product, simplicity, ambition, and craft lenses across a full list of improvement categories — new features, speed and latency, control, layout, color, motion, native feel, accessibility, backend, engineering quality, and game design — and keeps at least ten entries spread across those categories. An *idea* gets three to five options with impact, effort, risk, and a text sketch. A *signal* flags a gap that needs a person to think first: the UI looks dated next to the leaders, startup is four times slower, or every leader has a feature this product lacks. Each category gets one issue that holds all its entries, so a run produces 1–20 issues, not hundreds. Later runs update those same issues instead of adding duplicates. It never edits the system.

### SigmaBrief

Turns GitHub issues, features, upgrades, bugs, or plain work statements into short, copy-pastable briefs for other agents. Light research → dispatch list → fenced briefs → **stop**. Does not implement work or open product fix PRs. Default brief arc: plan → optional grill-me (including Windows worktree) → approve → execute → validate → PR for review (**do not merge**).

**User-triggered only.** Do not treat Brief as ambient chat decoration.

### SigmaShip

Takes one GitHub issue that has acceptance criteria and ships it. It creates a feature worktree and branch, opens a draft PR linked to the ticket, spec, and map, and builds test-first, committing and pushing each slice. When every criterion has evidence and CI is green, fresh agents review the branch in rounds until one round finds nothing at P0–P2. Then it merges, closes the ticket, deletes the branches and worktree, and proves that local `main` equals `origin/main`. A ticket without checkable criteria is refused, with the skill to run first (`/to-spec`, `/to-tickets`, `/grilling`, SigmaReview, SigmaImprove, or SigmaBrief).

### SigmaWrite

Writing voice inspired by **ASD-STE100 Simplified Technical English** — soft steers, not hard numbered rules. High-quality, still-technical explanations a sharp outsider can follow. Hard bans on gibberish and invented words. Includes a pasteable system-prompt block inside `SKILL.md`. Not certified STE; no dictionary ship.

### SigmaRefactor

Runs a reproducible `laloc` scan, reads the five largest maintained files, explains safe refactoring choices, and waits for user agreement before editing. It checks directories that `laloc` skips, preserves behavior and user changes, and reports lines removed separately from lines moved into new modules.

---

## Install

### Sigma Installer: Project Installation (recommended)

Run `npx @djordje-stojanovic/sigmaskills` with no command. The Sigma Installer's Emberforge interface reads the Skill Pack catalog from `manifest.json` and the bundled Agent Host registry. Project Installation selects only the universal `.agents/skills/` destination by default, shows a compact host-path list, and leaves host-specific destinations unselected until you choose them. Search remains available for every supported Agent Host, including hosts that are not detected. Exact current official copies and valid links are recorded as managed without rewriting skill bytes. Escape, EOF, Ctrl+C, or a rejected confirmation exits without writing.

The installer opens directly to a small Sigma heading in the warm LAPI palette. Each skill's short description (`short_description` in `agents/openai.yaml`) stays in a focus area of at most two lines. Destination pages show at most eight rows and adapt to terminal height. Long confirmation paths wrap onto pages; use `next`/`prev` in plain mode or left/right arrows in interactive mode. Reduced motion keeps the same picker: there is no opening animation. The cursor, raw mode, input flow, and listeners are restored when the installer finishes or stops.

With `--static`, `--no-color`, `NO_COLOR`, `CI`, redirected output, or a non-TTY session, enter one command per line. Type a row number to toggle it, `/claude` to search destinations, `/` to clear search, `next` or `prev` to change page, and press Enter to continue. Use `a` to select all skills, `g` for the global warning, `?` for help, or `esc` to cancel. Confirm installation with `y` followed by Enter. Only `.agents/skills` is selected by default; detected hosts stay unselected.

Use `--no-color`, `--static`, or `--narrow` when the terminal needs those modes. Use `--project <path>` to select another project root.

### Sigma Installer: Global Installation

Project Installation stays the default. In the interactive installer, `g` selects Global Installation and shows a scope warning immediately. The final confirmation repeats every selected Agent Host, exact resolved path, method, overwrite or delete effect, and backup action. Cancel at either prompt leaves prior user-level state unchanged.

Non-interactive mutation requires both `--global` and `--yes`. `--dry-run` shows those confirmation requirements and the full impact without writing. Unknown newer global state schemas fail closed; supported migrations keep ownership, hashes, methods, and backup references. Exact and changed existing copies use the same adoption path as Project Installation.

### Sigma Installer: status

`npx @djordje-stojanovic/sigmaskills status` is read-only. It reports Project Installation state by default, or Global Installation with `--global`. Human and `--json` output name the scope, installed and running Release, Skill Revisions, Agent Hosts, methods, exact paths, and ownership. Classification uses live per-file hashes and `lstat`/link checks. Valid Skill Customization is drift, not corruption. Drift discovery still exits `0`; command failures exit `1`. Status does not migrate, repair, write state or destinations, rewrite `skills-lock.json`, or contact the network.

The installer keeps its private files in `.agents/.sigmaskills/` (Global Installation: `~/.agents/.sigmaskills/`): `state.json`, the `.sigma.lock` file, backups, journals, and staging. That folder holds its own `.gitignore` with `*`, so `git add -A` stages only `.agents/skills/**` and `skills-lock.json`. Your root `.gitignore` is never edited. Locks expire after 24 hours; incomplete lock records get a five-second grace period. A short-lived `.sigma.lock.guard` serializes takeover and release. If a crash leaves that guard, stop all SigmaSkills processes before removing the guard directory and retrying. Projects from 0.4.0 and older keep these files straight in `.agents/`. `status` and every `--dry-run` read them there and write nothing. The next install, update, uninstall, restore, or purge moves them into `.agents/.sigmaskills/` in one step: a crash leaves either the old or the new layout. If an interrupted uninstall or purge journal is still in the old layout, the installer stops and asks you to finish that run with 0.4.0 first. `--state-dir` and `SIGMA_STATE_DIR` still choose an exact folder and are never migrated.

### Sigma Installer: update

`npx @djordje-stojanovic/sigmaskills update --dry-run` groups changed and unchanged skills and writes nothing. It shows the changelog sections newer than the installed Release, up to the running one, and labels the running Release as newer, same, or older than the installed one. Empty groups are left out, and a skill gets a resolution prompt only when it has local or concurrent edits. `--json` output keeps its fields. `--yes` updates every changed skill when none are blocked; `--skill <id>` (repeatable) selects complete skills only. Valid Skill Customization bytes between the markers are copied onto the new official `SKILL.md` exactly. Edits outside that block are classified as local-only or concurrent with upstream; `--dry-run` names those cases and the overwrite or delete effects. `--outside-edit replace|skip|export` is required before mutation: replace takes a complete integrity-checked private backup first, skip leaves that skill and its state untouched while other skills continue, and export copies the prior tree to a planned path and refuses collisions. Missing, duplicate, reversed, nested, or otherwise malformed customization markers block automatic update for that skill and are never guessed into a customization boundary. `--dry-run` shows the marker shape, exact proposed repair bytes when a unique mechanical repair exists, and the resulting replacements or deletions. `--malformed-markers skip|repair|replace` is required before mutation: skip leaves that skill unchanged while others continue, repair writes only an approved exact repair, and replace takes a complete private backup then installs a clean official copy. Malformed markers plus outside drift keep all content until both `--malformed-markers` and `--outside-edit` are explicit. Cancellation, invalid repair, editor failure, backup failure, or transaction failure writes nothing partial. The latest valid backup stays until the new tree and backup metadata commit; cleanup failure may keep two backups and record cleanup debt. The canonical `.agents/skills/<id>` copy owns customization; links and matching managed copies follow it. Unknown newer state schemas, missing bundled Skill Revisions, broken links, and copy disagreement stop without mutation. Updates use the same transactional install path and refresh state only after commit. Project Installation is the default; Global Installation needs `--global` and `--yes`.

### Sigma Installer: restore

`npx @djordje-stojanovic/sigmaskills restore --skill <id> --dry-run` shows the latest retained backup: Release and Skill Revision when known, creation date, verified size, scope, canonical target, and affected links or copies. `--yes` stages and integrity-checks the backup before any live write. On success the displaced current tree becomes the new one-step backup. Restoring identical content is a no-op and does not rotate backups. A removed skill can return from portable ownership metadata without claiming unrelated paths. Missing, truncated, tampered, schema-incompatible, insufficient-space, stale-ownership, occupied-unowned, and failed Windows fallback cases stop with the prior live tree and retained backup intact. Project Installation is the default; Global Installation needs `--global` and `--yes`.

### Sigma Installer: uninstall

`npx @djordje-stojanovic/sigmaskills uninstall --skill <id> --dry-run` runs Uninstall Review for each selected skill. `npx @djordje-stojanovic/sigmaskills uninstall --all --dry-run` composes that same Uninstall Review across every recorded Sigma skill in one explicit Project or Global scope. There is no review-skipping fast path. The aggregate plan lists every skill, owned destination, canonical dependency, planned state change, and retained backup. Clean skills offer `--clean remove|keep`. Changed, customized, or malformed skills offer `--changed backup|keep|export|delete`. Uninstall-all defaults to `--changed backup` so backups remain restorable. `--yes` applies those choices: remove deletes only revalidated Sigma-owned paths; backup snapshots the current tree then removes it; export copies the current tree to `--export-dir` then removes managed paths; delete removes current content and leaves any older retained backup; keep writes nothing. Keep choices leave shared state and canonical dependency graphs intact. Execution rechecks each leaf with `lstat` and deletes a link itself, never its resolved target. Canonical content stays until recorded dependents are gone. Project uninstall-all never writes Global Installation; global uninstall-all never scans projects. For selected uninstall, missing paths, stale state, unowned replacements, divergent managed copies, and wrong-target links stop without a partial ownership change. For uninstall-all, those cases skip that skill, continue the rest, and report it as skipped. Interruption or failure leaves a durable recovery journal in installer state (`uninstall-journal.json`) and restores the failed skill so no active partial links remain. Human, dry-run, and JSON results report removed, retained, skipped, and failed skills. State and lock update only after filesystem operations commit. Project Installation is the default; Global Installation needs `--global` and `--yes`.

### Sigma Installer: purge

`npx @djordje-stojanovic/sigmaskills purge --dry-run` lists the exact ownership plan for one Project or Global scope: revalidated Sigma-owned trees, links or junctions, copies, backups, staging, journals, and relevant locks. Purge never infers ownership from folder names. `--yes`, CI, non-TTY, and JSON are not authority. Apply with the typed phrase `purge SigmaSkills`, or non-interactively with `--confirm-purge "purge SigmaSkills"`. Unexpected unowned occupants stop the command and stay untouched. Cross-filesystem deletes journal first and quarantine owned trees before the ownership manifest is removed. An interrupted cleanup leaves recoverable quarantined state rather than active partial links. Retry with the same confirmation phrase finishes the purge. Project purge never writes Global Installation; global purge never scans projects.

### Sigma Installer: Agent Host registry automation

The `registry-sync.yml` workflow fetches one pinned `vercel-labs/skills` revision as data and runs converter code only from the exact default-branch SHA in `EXPECTED_HEAD`. Generated changes are limited to `registry/agent-hosts.json`, `registry/source.json`, and `test/fixtures/vercel-skills/src/agents.ts`. New hosts must pass safe-root, traversal, collision, overlap, control-character, and platform checks. Only a generated pull request from that trusted workflow, with an exact allowlisted diff, the validated head SHA, current protected `main`, and all required checks may auto-merge. Validated additions and description-only edits can then publish a patch Release through the same idempotent trusted publication primitive as owner Releases. Path, ID, alias, detection, platform, membership, removal, unknown fields, and validation failures stay blocked for owner review. Version calculation serializes concurrent runs and reconciles npm and GitHub before the patch. The generated branch is deleted only after verified merge and matching npm/GitHub completion. If that generated branch is leftover from an earlier run, Generate replaces it; if a matching generated pull request is already open, Generate reuses it instead of failing the push. Automation cannot change skills, CLI behavior, unrelated issues or pull requests, human branches, or major/minor Releases, and it never overwrites an existing npm version. Configure an npm trusted publisher for `registry-sync.yml` in addition to `release.yml`.

### Maintainers: release

Releases run from a repository checkout, never from the published package; the npm package ships only the user CLI. Release and registry automation live in `scripts/`.

1. `npm run release -- --dry-run` previews the next Release.
2. `npm run release -- --write-identities` writes the version identities; commit them and merge.
3. `npm run release -- --expected-commit <sha> --expected-version <version> --expected-digest <sha256>` dispatches `release.yml`.

`--dry-run` calculates the next semantic version and complete change set from the accepted source commit, then prints one publication preview: commit, version, required tests, tarball contents and SHA-256 digest, Skill Revisions, git tag, GitHub Release, npm package, and `latest` dist-tag. Ordinary merges never publish. `--yes`, CI, and informal text cannot dispatch. `--write-identities` writes matching `package.json`, `manifest.json`, and `CHANGELOG.md` identities, and adds the outgoing Release's skill hashes (read from its local `v<version>` tag) to `registry/skill-baselines.json`, so the owner can commit them. Dispatch requires `--expected-commit`, `--expected-version`, and `--expected-digest` that match that rebuilt preview. The trusted `release.yml` workflow independently checks out the approved commit, re-runs tests, rebuilds the tarball, and verifies those values before the publish job. Validation stays `contents: read`. Only the final job receives `id-token: write`, `contents: write`, and the protected `release` environment, with actions pinned by commit SHA. Missing npm reservation, trusted publisher, environment protection, or a conflicting version, tag, or GitHub Release fails closed with setup guidance. Matching npm provenance or an existing GitHub Release at the same commit is skipped rather than overwritten or duplicated.

### Cross-host alternative

The cross-agent [skills](https://github.com/vercel-labs/skills) CLI detects Codex, Claude Code, Cursor, OpenCode, Pi, and dozens more:

```bash
# Everything, all detected agents, global
npx skills add Djordje-Stojanovic/Sigmaskills --all -g -y

# One skill at a time
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmareview -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmaimprove -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmabrief -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmaship -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmawrite -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmarefactor -g

# Pin to specific hosts
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmawrite -g -a cursor -a claude-code -a codex -a opencode -a pi

# List what this repo ships (no install)
npx skills add Djordje-Stojanovic/Sigmaskills --list
```

Full GitHub URL also works:

```bash
npx skills add https://github.com/Djordje-Stojanovic/Sigmaskills --skill sigmabrief -g
```

### Codex

```text
$skill-installer install sigmareview from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmaimprove from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmabrief from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmaship from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmawrite from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmarefactor from https://github.com/Djordje-Stojanovic/Sigmaskills
```

### Manual / universal copy

When a host only watches a skills folder (Pi, LAPI mirrors, custom TUIs, air-gapped boxes):

**POSIX**

```bash
git clone https://github.com/Djordje-Stojanovic/Sigmaskills.git
mkdir -p ~/.agents/skills
cp -R Sigmaskills/sigmareview ~/.agents/skills/sigmareview
cp -R Sigmaskills/sigmaimprove ~/.agents/skills/sigmaimprove
cp -R Sigmaskills/sigmabrief ~/.agents/skills/sigmabrief
cp -R Sigmaskills/sigmaship ~/.agents/skills/sigmaship
cp -R Sigmaskills/sigmawrite ~/.agents/skills/sigmawrite
cp -R Sigmaskills/sigmarefactor ~/.agents/skills/sigmarefactor
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/Djordje-Stojanovic/Sigmaskills.git
New-Item -ItemType Directory -Force -Path "$HOME\.agents\skills" | Out-Null
Copy-Item -Recurse Sigmaskills\sigmareview   "$HOME\.agents\skills\sigmareview"
Copy-Item -Recurse Sigmaskills\sigmaimprove  "$HOME\.agents\skills\sigmaimprove"
Copy-Item -Recurse Sigmaskills\sigmabrief    "$HOME\.agents\skills\sigmabrief"
Copy-Item -Recurse Sigmaskills\sigmaship     "$HOME\.agents\skills\sigmaship"
Copy-Item -Recurse Sigmaskills\sigmawrite    "$HOME\.agents\skills\sigmawrite"
Copy-Item -Recurse Sigmaskills\sigmarefactor "$HOME\.agents\skills\sigmarefactor"
```

Point other hosts at the same folders (or copy again) as needed:

| Host family | Typical skills path |
|-------------|---------------------|
| Universal / Codex-style | `~/.agents/skills/<id>/` |
| Cursor | `~/.cursor/skills/<id>/` or project `.agents/skills/` |
| Claude Code | `~/.claude/skills/<id>/` |
| Pi / LAPI-style | `~/.pi/agent/skills/<id>/` |
| OpenCode | `~/.config/opencode/skills/<id>/` |
| Codex | `~/.codex/skills/<id>/` |

Every [GitHub Release](https://github.com/Djordje-Stojanovic/Sigmaskills/releases) matches the npm package of the same version. A skill that is in the repository but not yet in a Release is available from the repository source only.

### Optional: SigmaWrite as system prompt

Open [`sigmawrite/SKILL.md`](sigmawrite/SKILL.md), copy the **Paste as system prompt** block into host instructions when you want the voice always on — without editing this repo’s release contract.

---

## Run

Use your host’s skill syntax. Examples:

<table>
<tr>
<td width="50%">

**Codex**

```text
$sigmareview https://github.com/owner/repo
$sigmaimprove
$sigmabrief https://github.com/owner/repo/issues/12
$sigmabrief all open
$sigmaship https://github.com/owner/repo/issues/42
$sigmawrite
$sigmarefactor
```

</td>
<td width="50%">

**Pi / skill-slash hosts**

```text
/skill:sigmareview https://github.com/owner/repo
/skill:sigmaimprove
/skill:sigmabrief https://github.com/owner/repo/issues/12
/skill:sigmabrief all open
/skill:sigmaship https://github.com/owner/repo/issues/42
/skill:sigmawrite
/skill:sigmarefactor
```

</td>
</tr>
</table>

**Claude Code · Cursor · OpenCode · ChatGPT/Codex UI · Reasonix-class · Kimi/Muse · others**  
Use the skill picker, `@` / `$` skill mention, or whatever that product documents for Agent Skills. Folder name = skill id = invocation token.

| Skill | Typical invoke | Notes |
|-------|----------------|-------|
| `sigmareview` | repo URL · path | One setup message (authority, goals), then runs alone |
| `sigmaimprove` | repo · path · running product | One setup message (vision, focus, constraints, ticket place), then discusses ideas |
| `sigmabrief` | issue URL · `#N` · `all open` · plain work | Explicit only — not ambient |
| `sigmaship` | issue URL · `#N` | Refuses tickets without checkable acceptance criteria |
| `sigmawrite` | (no args) | Session writing voice until you turn it off |
| `sigmarefactor` | repository path or current repository | Scans and discusses large files before any edit |

---

## Output contracts

### SigmaReview

- File: `SIGMAREVIEW-YYYY-MM-DD.md` on branch `sigmareview/YYYY-MM-DD`, one pull request
- `SIG-###` findings: P0–P3, **M1** measured or **M2** proven, location, broken promise, fix, and proof test
- **M3** needs-measurement items listed apart and never counted as confirmed
- Every finding is a self-contained fix brief; findings are grouped into waves that can be fixed in parallel
- The PR adds only the review file; it never changes code
- Execution, installs, and security probes only with your authority, and only on a local instance

### SigmaImprove

- Compares with the world's top 1–3 products and with published bars (Core Web Vitals, RAIL, WCAG 2.2, platform guidelines, DORA)
- At least 10 entries across at least 5 category groups; ideas with 3–5 weighed options and sketches, signals with evidence and questions
- One issue per category, titled `SigmaImprove · <ID> <name>`, 1–20 issues per run; or `.scratch/sigmaimprove/<ID>-<slug>.md`
- Later runs update the same issues: new entries, done entries marked, rejected entries not re-proposed
- Never edits code, assets, or docs

### SigmaBrief

- Chat-only dispatch list + paste-ready fenced `text` briefs  
  (**no** `SIGMABRIEF-*.md` in the product repo)
- Types: greenfield · finish-PR · skip · blocked
- Executing briefs: plan first · optional grill-me · **do not merge** · self-review before PR
- Isolation on → agent-created Windows `git worktree`; cleanup only after human merge or abandon
- Never implements the work or opens product fix PRs

### SigmaShip

- Branch `ship/<issue>-<slug>` in its own worktree; draft PR opened before any code, with `Closes #N`, spec and map links, and one checkbox per criterion
- The PR body is the ledger: criteria with evidence, rulings, follow-ups, and review rounds; an interrupted run resumes from it
- Test-first slices, one conventional commit per slice, pushed as it goes; never force-pushes or merges red
- Review rounds by fresh agents until one finds zero P0–P2 problems (at most 3, then it asks you)
- Lands with the repository's merge style, closes the ticket, deletes branches and worktree, and verifies `main` equals `origin/main`

### SigmaWrite

- Chat writing style only (no report file, no PR)
- Soft STE-inspired steers + hard bans (gibberish / invented words / talking down / renaming code)
- Optional pasteable system-prompt block in `SKILL.md`
- Does not override another skill’s rigid output contract

### SigmaRefactor

- Five-stage scan → read → discussion → implementation → verification flow
- `laloc` reconciliation with a maintained-file inventory and explicit exclusions
- User approval before edits; behavior, tests, interfaces, and custom content stay protected
- Final line-count comparison with removed and moved lines reported separately


---

## Requirements

| Skill | Needs |
|-------|--------|
| All | Agent that can load Agent Skills (`SKILL.md`) |
| SigmaReview | Read access to the target repo · GitHub tooling to push a branch or fork and open a PR · execution authority only if you want measured findings |
| SigmaImprove | Read access to the target · GitHub issue access only if tickets go to GitHub |
| SigmaShip | Push rights and GitHub tooling (`gh` or connector) to open, merge, and close; the repository's test commands |
| SigmaBrief | `gh` read when briefing from issues/PRs · **no** push to the product repo |
| SigmaWrite | Nothing beyond chat — optional paste into system instructions |
| SigmaRefactor | Read access to the target repository and `laloc` when available; no required external skill |

Windows-native defaults where skills mention shells or worktrees (PowerShell-friendly; do not assume WSL).

---

## Repo layout

```text
Sigmaskills/
├── AGENTS.md                 Agent working contract
├── README.md · CHANGELOG.md · LICENSE · package.json
├── test/                     Structural regression tests (npm test)
├── .github/                  Issue forms · PR template · CI
├── sigmareview/              SKILL.md · agents/ · references/
├── sigmaimprove/             SKILL.md · agents/ · references/
├── sigmabrief/               SKILL.md · agents/ · references/
├── sigmaship/                SKILL.md · agents/ · references/
├── sigmawrite/               SKILL.md · agents/
└── sigmarefactor/            SKILL.md · agents/ · references/
```

Each top-level folder is one installable skill. `name` in frontmatter = folder name = `--skill` id.

Agents working in this repo should read [`AGENTS.md`](AGENTS.md).

---

## Testing

Zero-dependency Node tests guard the beauty: skill registry, `SKILL.md` frontmatter, `agents/openai.yaml`, README install/run wiring, CHANGELOG, issue templates, agent docs, and SigmaWrite’s soft-steer contract.

```bash
npm test
```

CI runs the same suite on Windows, macOS, and Linux for Node.js 20 and 22, on every pull request and every push to `main`. Those jobs cover real junctions or symbolic links, copy fallback, shell differences, and an isolated temp filesystem.

When you **add or rename a skill**, update `KNOWN_SKILLS` in [`test/repo-invariants.test.js`](test/repo-invariants.test.js) in the same change as README and CHANGELOG — otherwise CI fails on purpose. That rule also lives in [`AGENTS.md`](AGENTS.md).

---

## Contributing & issues

Use the issue chooser: [New issue](https://github.com/Djordje-Stojanovic/Sigmaskills/issues/new/choose)  
Bug · Feature · Improvement · Docs — written for skills, prompts, and templates (not unrelated product apps).

---

## License

[MIT](LICENSE) © Djordje Stojanovic
