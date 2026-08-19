# SigmaSkills

**High-rigor Agent Skills for every serious coding agent.**

Portable [Agent Skills](https://agentskills.io/) that install once and run on **Codex**, **Claude Code**, **Cursor**, **Pi**, **OpenCode**, **LAPI**, Reasonix-class TUIs, Kimi/Muse-style hosts, and any tool that reads a `SKILL.md`.

| | |
|---|---|
| **Release** | [**v0.1.0**](https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.1.0) |
| **Changelog** | [CHANGELOG.md](CHANGELOG.md) |
| **License** | [MIT](LICENSE) |
| **Spec** | [agentskills.io](https://agentskills.io/) |

```text
  Σ  review     →  one findings report, one PR, no runtime edits
  Σ  performance→  calibrated bottlenecks, one report PR
  Σ  brief      →  paste-ready agent briefs, chat only
  Σ  write      →  clear STE-inspired technical English
```

---

## Quick start

Start the first-party Sigma Installer in a project:

```bash
npx sigmaskills
```

Select any set of skills. By default the installer writes only to `.agents/skills/<id>` and lists every Agent Host that reads that universal destination. Host-specific directories such as `.claude/skills` or `.pi/skills` stay unselected until you choose them. Selected host destinations use Windows directory junctions or macOS/Linux symbolic links to the canonical copy; `--copy` writes an independent managed copy instead. Link failure reports the exact cause and offers copy — the installer never changes method silently. Exact current official copies and valid links are adopted in place without rewriting skill bytes. Changed, older, pre-marker, and unverified Sigma-looking trees are classified with a file diff and provenance confidence; replace commits a private backup first, skip leaves the tree, and export writes a collision-safe copy. Pre-marker extra content is never guessed into the customization block; malformed markers stop unless you pass an explicit `--adopt-malformed` choice. The confirmation plan shows every full destination path and method. Press `g` in the skill picker for Global Installation: an immediate scope warning appears, then a second confirmation repeats every Agent Host, resolved path, method, overwrite effect, and backup action. Non-interactive Global writes need both `--global` and `--yes`; CI, TTY, JSON, and Agent Host detection never imply that authority. To install one skill without the interactive interface:

```bash
npx sigmaskills install sigmawrite --project .
npx sigmaskills install sigmawrite --project . --destination .claude/skills
npx sigmaskills install sigmawrite --project . --destination .claude/skills --copy
npx sigmaskills install sigmawrite --global --dry-run
npx sigmaskills install sigmawrite --global --yes
```

Then invoke with your host’s normal skill syntax (`$sigmawrite`, `/skill:sigmawrite`, skill picker, …).

---

## The skills

| Skill | Id | Job | Output |
|-------|-----|-----|--------|
| **SigmaReview** | `sigmareview` | One-shot full-repo engineering audit | One findings MD + report-only PR |
| **SigmaPerformance** | `sigmaperformance` | Calibrated performance investigation | One report MD + report-only PR |
| **SigmaBrief** | `sigmabrief` | Prompt factory for parallel / single agents | Chat briefs only |
| **SigmaWrite** | `sigmawrite` | Clear STE-inspired technical English | Chat writing voice |

### SigmaReview

A single agent walks an entire repository — correctness, completeness, architecture, data and concurrency, reliability, security, performance, tests, dependencies, delivery, operations, and domain-specific engineering. Speculative findings are rejected. Exactly **one** evidence-rich Markdown report is published as a **report-only** pull request. Runtime code is never changed.

### SigmaPerformance

Maps real user journeys, then separates **measured** and **mechanically proven** bottlenecks from measurement-required opportunities. Publishes one structured report PR. Runtime sources stay untouched unless calibration explicitly says otherwise.

### SigmaBrief

Turns GitHub issues, features, upgrades, bugs, or plain work statements into short, copy-pastable briefs for other agents. Light research → dispatch list → fenced briefs → **stop**. Does not implement work or open product fix PRs. Default brief arc: plan → optional grill-me (including Windows worktree) → approve → execute → validate → PR for review (**do not merge**).

**User-triggered only.** Do not treat Brief as ambient chat decoration.

### SigmaWrite

Writing voice inspired by **ASD-STE100 Simplified Technical English** — soft steers, not hard numbered rules. High-quality, still-technical explanations a sharp outsider can follow. Hard bans on gibberish and invented words. Includes a pasteable system-prompt block inside `SKILL.md`. Not certified STE; no dictionary ship.

---

## Install

### Sigma Installer: Project Installation (recommended)

Run `npx sigmaskills` with no command. The Sigma Installer's Emberforge interface reads the Skill Pack catalog from `manifest.json` and the bundled Agent Host registry. Project Installation selects only the universal `.agents/skills/` destination by default, expands every Agent Host that reads it, and leaves host-specific destinations unselected until you choose them. Search remains available for every supported Agent Host, including hosts that are not detected. Exact current official copies and valid links are recorded as managed without rewriting skill bytes. Escape, EOF, Ctrl+C, or a rejected confirmation exits without writing.

The Emberforge screens keep the accepted warm LAPI palette and do not mix in Prismgrid or Monolith. Layouts reflow below 76 columns and wrap long paths. Keyboard-only controls cover focus, search, selection, confirmation, cancellation, and `?` help. `--no-color`, `--static`, `--narrow`, `--json`, `NO_COLOR`, `CI`, `REDUCED_MOTION=1`, `PREFERS_REDUCED_MOTION=reduce`, redirected output, and non-TTY sessions disable animation and decorative color. Truecolor, 256-color, 16-color, and ASCII fallbacks stay readable and still show safety copy. The cursor and raw mode restore after success, failure, interrupt, EOF, and exceptions.

Use `--no-color`, `--static`, or `--narrow` when the terminal needs those modes. Use `--project <path>` to select another project root.

### Sigma Installer: Global Installation

Project Installation stays the default. In the interactive installer, `g` selects Global Installation and shows a scope warning immediately. The final confirmation repeats every selected Agent Host, exact resolved path, method, overwrite or delete effect, and backup action. Cancel at either prompt leaves prior user-level state unchanged.

Non-interactive mutation requires both `--global` and `--yes`. `--dry-run` shows those confirmation requirements and the full impact without writing. Unknown newer global state schemas fail closed; supported migrations keep ownership, hashes, methods, and backup references. Exact and changed existing copies use the same adoption path as Project Installation.

### Sigma Installer: status

`npx sigmaskills status` is read-only. It reports Project Installation state by default, or Global Installation with `--global`. Human and `--json` output name the scope, installed and running Release, Skill Revisions, Agent Hosts, methods, exact paths, and ownership. Classification uses live per-file hashes and `lstat`/link checks. Valid Skill Customization is drift, not corruption. Drift discovery still exits `0`; command failures exit `1`. Status does not migrate, repair, write state or destinations, rewrite `skills-lock.json`, or contact the network.

### Sigma Installer: update

`npx sigmaskills update --dry-run` groups changed and unchanged skills, shows the bundled changelog and whole-skill file diffs, and writes nothing. `--yes` updates every changed skill when none are blocked; `--skill <id>` (repeatable) selects complete skills only. Valid Skill Customization bytes between the markers are copied onto the new official `SKILL.md` exactly. Edits outside that block are classified as local-only or concurrent with upstream; `--dry-run` names those cases and the overwrite or delete effects. `--outside-edit replace|skip|export` is required before mutation: replace takes a complete integrity-checked private backup first, skip leaves that skill and its state untouched while other skills continue, and export copies the prior tree to a planned path and refuses collisions. Missing, duplicate, reversed, nested, or otherwise malformed customization markers block automatic update for that skill and are never guessed into a customization boundary. `--dry-run` shows the marker shape, exact proposed repair bytes when a unique mechanical repair exists, and the resulting replacements or deletions. `--malformed-markers skip|repair|replace` is required before mutation: skip leaves that skill unchanged while others continue, repair writes only an approved exact repair, and replace takes a complete private backup then installs a clean official copy. Malformed markers plus outside drift keep all content until both `--malformed-markers` and `--outside-edit` are explicit. Cancellation, invalid repair, editor failure, backup failure, or transaction failure writes nothing partial. The latest valid backup stays until the new tree and backup metadata commit; cleanup failure may keep two backups and record cleanup debt. The canonical `.agents/skills/<id>` copy owns customization; links and matching managed copies follow it. Unknown newer state schemas, missing bundled Skill Revisions, broken links, and copy disagreement stop without mutation. Updates use the same transactional install path and refresh state only after commit. Project Installation is the default; Global Installation needs `--global` and `--yes`.

### Sigma Installer: restore

`npx sigmaskills restore --skill <id> --dry-run` shows the latest retained backup: Release and Skill Revision when known, creation date, verified size, scope, canonical target, and affected links or copies. `--yes` stages and integrity-checks the backup before any live write. On success the displaced current tree becomes the new one-step backup. Restoring identical content is a no-op and does not rotate backups. A removed skill can return from portable ownership metadata without claiming unrelated paths. Missing, truncated, tampered, schema-incompatible, insufficient-space, stale-ownership, occupied-unowned, and failed Windows fallback cases stop with the prior live tree and retained backup intact. Project Installation is the default; Global Installation needs `--global` and `--yes`.

### Sigma Installer: uninstall

`npx sigmaskills uninstall --skill <id> --dry-run` runs Uninstall Review for each selected skill. `npx sigmaskills uninstall --all --dry-run` composes that same Uninstall Review across every recorded Sigma skill in one explicit Project or Global scope. There is no review-skipping fast path. The aggregate plan lists every skill, owned destination, canonical dependency, planned state change, and retained backup. Clean skills offer `--clean remove|keep`. Changed, customized, or malformed skills offer `--changed backup|keep|export|delete`. Uninstall-all defaults to `--changed backup` so backups remain restorable. `--yes` applies those choices: remove deletes only revalidated Sigma-owned paths; backup snapshots the current tree then removes it; export copies the current tree to `--export-dir` then removes managed paths; delete removes current content and leaves any older retained backup; keep writes nothing. Keep choices leave shared state and canonical dependency graphs intact. Execution rechecks each leaf with `lstat` and deletes a link itself, never its resolved target. Canonical content stays until recorded dependents are gone. Project uninstall-all never writes Global Installation; global uninstall-all never scans projects. For selected uninstall, missing paths, stale state, unowned replacements, divergent managed copies, and wrong-target links stop without a partial ownership change. For uninstall-all, those cases skip that skill, continue the rest, and report it as skipped. Interruption or failure leaves a durable recovery journal in installer state (`uninstall-journal.json`) and restores the failed skill so no active partial links remain. Human, dry-run, and JSON results report removed, retained, skipped, and failed skills. State and lock update only after filesystem operations commit. Project Installation is the default; Global Installation needs `--global` and `--yes`.

### Cross-host alternative

The cross-agent [skills](https://github.com/vercel-labs/skills) CLI detects Codex, Claude Code, Cursor, OpenCode, Pi, and dozens more:

```bash
# Everything, all detected agents, global
npx skills add Djordje-Stojanovic/Sigmaskills --all -g -y

# One skill at a time
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmareview -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmaperformance -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmabrief -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmawrite -g

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
$skill-installer install sigmaperformance from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmabrief from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmawrite from https://github.com/Djordje-Stojanovic/Sigmaskills
```

### Manual / universal copy

When a host only watches a skills folder (Pi, LAPI mirrors, custom TUIs, air-gapped boxes):

**POSIX**

```bash
git clone https://github.com/Djordje-Stojanovic/Sigmaskills.git
mkdir -p ~/.agents/skills
cp -R Sigmaskills/sigmareview ~/.agents/skills/sigmareview
cp -R Sigmaskills/sigmaperformance ~/.agents/skills/sigmaperformance
cp -R Sigmaskills/sigmabrief ~/.agents/skills/sigmabrief
cp -R Sigmaskills/sigmawrite ~/.agents/skills/sigmawrite
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/Djordje-Stojanovic/Sigmaskills.git
New-Item -ItemType Directory -Force -Path "$HOME\.agents\skills" | Out-Null
Copy-Item -Recurse Sigmaskills\sigmareview   "$HOME\.agents\skills\sigmareview"
Copy-Item -Recurse Sigmaskills\sigmaperformance "$HOME\.agents\skills\sigmaperformance"
Copy-Item -Recurse Sigmaskills\sigmabrief    "$HOME\.agents\skills\sigmabrief"
Copy-Item -Recurse Sigmaskills\sigmawrite    "$HOME\.agents\skills\sigmawrite"
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

Release zip: download [**Sigmaskills-v0.1.0**](https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.1.0) and copy the four skill folders into the path your agent reads.

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
$sigmaperformance https://github.com/owner/repo
$sigmabrief https://github.com/owner/repo/issues/12
$sigmabrief all open
$sigmawrite
```

</td>
<td width="50%">

**Pi / skill-slash hosts**

```text
/skill:sigmareview https://github.com/owner/repo
/skill:sigmaperformance https://github.com/owner/repo
/skill:sigmabrief https://github.com/owner/repo/issues/12
/skill:sigmabrief all open
/skill:sigmawrite
```

</td>
</tr>
</table>

**Claude Code · Cursor · OpenCode · ChatGPT/Codex UI · Reasonix-class · Kimi/Muse · others**  
Use the skill picker, `@` / `$` skill mention, or whatever that product documents for Agent Skills. Folder name = skill id = invocation token.

| Skill | Typical invoke | Notes |
|-------|----------------|-------|
| `sigmareview` | repo URL | Needs push/fork rights for the report PR |
| `sigmaperformance` | repo URL | Starts with two short calibration batches, then runs |
| `sigmabrief` | issue URL · `#N` · `all open` · plain work | Explicit only — not ambient |
| `sigmawrite` | (no args) | Session writing voice until you turn it off |

---

## Output contracts

### SigmaReview

- File: `SIGMAREVIEW-FINDINGS-YYYY-MM-DD.md`
- One dedicated branch + **report-only** PR
- Prioritized, confidence-gated findings with exact evidence
- Implementation-ready remediation and verification steps
- Full repository coverage ledger
- **No** source fixes, dependency installs, app execution, subagents, or auxiliary repo artifacts

### SigmaPerformance

- File: `SIGMAPERFORMANCE-REPORT-YYYY-MM-DD.md`
- One dedicated **report-only** PR
- **M1** measured · **M2** mechanically proven bottlenecks
- **M3** measurement-required opportunities, failed experiments, unverified boundaries (accounted separately)
- Structured future SigmaOptimize handoff
- Default single-agent; bounded subagents only via explicit calibration opt-in
- **No** runtime-source changes or temp measurement junk in the repo diff

### SigmaBrief

- Chat-only dispatch list + paste-ready fenced `text` briefs  
  (**no** `SIGMABRIEF-*.md` in the product repo)
- Types: greenfield · finish-PR · skip · blocked
- Executing briefs: plan first · optional grill-me · **do not merge** · self-review before PR
- Isolation on → agent-created Windows `git worktree`; cleanup only after human merge or abandon
- Never implements the work or opens product fix PRs

### SigmaWrite

- Chat writing style only (no report file, no PR)
- Soft STE-inspired steers + hard bans (gibberish / invented words / talking down / renaming code)
- Optional pasteable system-prompt block in `SKILL.md`
- Does not override another skill’s rigid output contract

---

## Requirements

| Skill | Needs |
|-------|--------|
| All | Agent that can load Agent Skills (`SKILL.md`) |
| SigmaReview · SigmaPerformance | Read access to the target repo · authenticated GitHub tooling to push a branch or fork + open a PR |
| SigmaPerformance | Authority / safety boundary chosen in calibration |
| SigmaBrief | `gh` read when briefing from issues/PRs · **no** push to the product repo |
| SigmaWrite | Nothing beyond chat — optional paste into system instructions |

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
├── sigmaperformance/         SKILL.md · agents/ · references/
├── sigmabrief/               SKILL.md · agents/ · references/
└── sigmawrite/               SKILL.md · agents/
```

Each top-level folder is one installable skill. `name` in frontmatter = folder name = `--skill` id.

Agents working in this repo should read [`AGENTS.md`](AGENTS.md).

---

## Testing

Zero-dependency Node tests guard the beauty: skill registry, `SKILL.md` frontmatter, `agents/openai.yaml`, README install/run wiring, CHANGELOG, issue templates, agent docs, and SigmaWrite’s soft-steer contract.

```bash
npm test
```

CI runs the same suite on every push and pull request to `main`.

When you **add or rename a skill**, update `KNOWN_SKILLS` in [`test/repo-invariants.test.js`](test/repo-invariants.test.js) in the same change as README and CHANGELOG — otherwise CI fails on purpose. That rule also lives in [`AGENTS.md`](AGENTS.md).

---

## Contributing & issues

Use the issue chooser: [New issue](https://github.com/Djordje-Stojanovic/Sigmaskills/issues/new/choose)  
Bug · Feature · Improvement · Docs — written for skills, prompts, and templates (not unrelated product apps).

---

## License

[MIT](LICENSE) © Djordje Stojanovic
