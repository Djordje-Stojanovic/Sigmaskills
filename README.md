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

Install every skill to every Agent Skills host the CLI can see:

```bash
npx skills add Djordje-Stojanovic/Sigmaskills --all -g -y
```

Or pick one:

```bash
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmawrite -g
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

### One command (recommended)

Uses the cross-agent [skills](https://github.com/vercel-labs/skills) CLI — detects Codex, Claude Code, Cursor, OpenCode, Pi, and dozens more:

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
├── README.md · CHANGELOG.md · LICENSE · package.json
├── test/                     Structural regression tests (npm test)
├── .github/                  Issue forms · PR template · CI
├── sigmareview/              SKILL.md · agents/ · references/
├── sigmaperformance/         SKILL.md · agents/ · references/
├── sigmabrief/               SKILL.md · agents/ · references/
└── sigmawrite/               SKILL.md · agents/
```

Each top-level folder is one installable skill. `name` in frontmatter = folder name = `--skill` id.

---

## Testing

Zero-dependency Node tests guard the beauty: skill registry, `SKILL.md` frontmatter, `agents/openai.yaml`, README install/run wiring, CHANGELOG, issue templates, and SigmaWrite’s soft-steer contract.

```bash
npm test
```

CI runs the same suite on every push and pull request to `main`.

When you **add or rename a skill**, update `KNOWN_SKILLS` in [`test/repo-invariants.test.js`](test/repo-invariants.test.js) in the same change as README and CHANGELOG — otherwise CI fails on purpose.

---

## Contributing & issues

Use the issue chooser: [New issue](https://github.com/Djordje-Stojanovic/Sigmaskills/issues/new/choose)  
Bug · Feature · Improvement · Docs — written for skills, prompts, and templates (not unrelated product apps).

---

## License

[MIT](LICENSE) © Djordje Stojanovic
