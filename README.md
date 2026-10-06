# SigmaSkills

**High-rigor Agent Skills for every serious coding agent.**

Portable [Agent Skills](https://agentskills.io/) that install once and run on **Codex**, **Claude Code**, **Cursor**, **Pi**, **OpenCode**, **Reasonix**, **Kimi Code CLI**, and any tool that reads a `SKILL.md`.

| | |
|---|---|
| **Release** | [**v0.6.1**](https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.6.1) |
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
     easytalk   →  plain chat and interactive status or question boards
  Σ  research   →  read public sources, record evidence and access gaps
```

---

## Quick start

Run the Sigma Installer in your project:

```bash
npx @djordje-stojanovic/sigmaskills
```

Pick the skills you want and confirm. By default the installer writes only to `.agents/skills/<id>`, the folder that many Agent Hosts read. It writes nothing until you confirm.

To install without the picker, name one or more skills, or pass `--all`. Several skills install together: if one fails, none stay installed.

```bash
npx @djordje-stojanovic/sigmaskills install sigmawrite --project .
npx @djordje-stojanovic/sigmaskills install sigmawrite sigmareview sigmaship --project .
npx @djordje-stojanovic/sigmaskills install --all --project .
```

Then call a skill with your host's normal skill syntax (`$sigmawrite`, `/skill:sigmawrite`, the skill picker, …).

The [installer guide](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/docs/installer.md) explains host folders, Global Installation, `status`, `update`, `restore`, `uninstall`, and `purge`.

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
| **EasyTalk** | `easytalk` | Plain chat with status and question boards | Interactive HTML board and copied replies |
| **SigmaResearch** | `sigmaresearch` | Read Reddit, X, HN, GitHub and Hugging Face for research | Answer with source links, dates, read scope and access gaps |

### Which one do I need?

SigmaReview and SigmaImprove split on one question: **is it wrong, or could it be better?**

- If a test, a doc, a stated goal, or a budget can prove it wrong, it is a SigmaReview finding. Examples: a crash, a security hole, a page that breaks its latency budget.
- If good people could disagree about the answer, it is a SigmaImprove idea. Examples: weak animation, a missing level, an onboarding flow with too many steps.
- If the code is only too large and behavior must not change, use SigmaRefactor.

The skills chain into two loops. **Fix:** SigmaReview → review PR → SigmaBrief or SigmaShip fixes each finding → merge. **Grow:** SigmaImprove → category issues → specs and tickets → SigmaShip.

### SigmaReview

Finds everything that breaks the system's own promises: bugs, security holes, slow paths, broken rendering, and weak tests. It measures performance and runs security probes only when you allow it, and only on a local instance. Each finding has a location, a mechanism, an impact, evidence, a fix, and a proof test, so an LLM can fix it from that finding alone. All findings go into `SIGMAREVIEW-YYYY-MM-DD.md` on one pull request. It never changes your code.

SigmaPerformance is retired. Its measurement method now lives in SigmaReview.

### SigmaImprove

Compares the product with the world's top one to three products and with published bars such as WCAG 2.2. It uses the product like a new user and keeps at least ten entries. An *idea* has three to five weighed options with sketches. A *signal* flags a gap that a person must think about first. Each category gets one living issue, so a run makes 1–20 issues, and later runs update them. It never edits the system.

### SigmaBrief

Turns GitHub issues, features, bugs, or plain work statements into short, copy-pastable briefs for other agents. It does light research, writes a dispatch list and fenced briefs, and then stops. It never implements the work. Each brief tells the agent to plan, build, check, and open a PR for review, and not to merge. Run it only when you ask for it by name.

### SigmaShip

Ships one GitHub issue that has acceptance criteria. It opens a worktree, a branch, and a draft PR that tracks the criteria and review rounds. It builds test-first and pushes each slice. Fresh agents then review the branch in rounds until one round finds nothing at P0–P2. Then it merges, closes the ticket, removes the branches and worktree, and checks that local `main` equals `origin/main`. It refuses a ticket without checkable criteria and names the skill to run first.

### SigmaWrite

A writing voice inspired by **ASD-STE100 Simplified Technical English**. It gives soft steers, not numbered rules, and bans gibberish and invented words. A sharp outsider can follow the result, and it stays technical. It stays on until you turn it off. To keep the voice on everywhere, copy the **Paste as system prompt** block from [`sigmawrite/SKILL.md`](sigmawrite/SKILL.md) into your host's instructions. It is not certified STE.

### SigmaRefactor

Counts lines (with `laloc` if you have it, or by itself), reads the five largest maintained files, and explains safe refactoring choices. It waits for your approval before it edits. It keeps behavior, tests, interfaces, and your own changes intact. At the end it reports lines removed apart from lines moved into new modules.

### EasyTalk

Keeps replies short and puts status reports or question batches on one interactive board. Read ticks, recommended options, task statuses, and free text feed a **Copy my answers** reply that names every unread card. Open it with an HTML preview tool or as a local browser file. Say “easy talk off” to stop.

### SigmaResearch

Reads public sources with platform-specific routes: Reddit RSS, X through Claude in Chrome on the owner's existing session, and public HN, GitHub and Hugging Face pages. It reports blocked or partial reads and stops on 403/429. It never logs in or evades bot checks.

---

## Install

Pick one method. The [installer guide](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/docs/installer.md#other-install-methods) has the full per-skill commands and host folders.

| Method | Command | Best for |
|--------|---------|----------|
| **Sigma Installer** (recommended) | `npx @djordje-stojanovic/sigmaskills install --all --project .` | Project or Global Installation with status, update, restore, and uninstall |
| **`npx skills`** | `npx skills add Djordje-Stojanovic/Sigmaskills --all -g -y` | Every agent that the [skills](https://github.com/vercel-labs/skills) CLI detects |
| **Codex** | `$skill-installer install <id> from https://github.com/Djordje-Stojanovic/Sigmaskills` | Codex only |
| **Manual copy** | `git clone` this repository, then copy `<id>/` into `~/.agents/skills/` | Air-gapped machines and hosts that only watch a folder |

Every [GitHub Release](https://github.com/Djordje-Stojanovic/Sigmaskills/releases) from 0.2.0 on is also on npm, except 0.2.1.

---

## Run

Use your host's skill syntax. Examples:

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
$easytalk
$sigmaresearch Research recent discussions about local language models
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
/skill:easytalk
/skill:sigmaresearch Research recent discussions about local language models
```

</td>
</tr>
</table>

**Claude Code · Cursor · OpenCode · ChatGPT/Codex UI · Reasonix · Kimi Code CLI · others:** use the skill picker, an `@` or `$` mention, or whatever the product documents for Agent Skills. The folder name is the skill id and the call token.

| Skill | Typical input | Notes |
|-------|---------------|-------|
| `sigmareview` | repo URL · path | One setup message (authority, goals), then runs alone |
| `sigmaimprove` | repo · path · running product | One setup message (vision, focus, constraints, ticket place), then discusses ideas |
| `sigmabrief` | issue URL · `#N` · `all open` · plain work | Only when you ask for it |
| `sigmaship` | issue URL · `#N` | Refuses tickets without checkable acceptance criteria |
| `sigmawrite` | (no input) | Session writing voice until you turn it off |
| `sigmarefactor` | repository path or current repository | Scans and discusses large files before any edit |
| `easytalk` | “easy talk” · status or question batch · `EASYTALK REPLY` | Conversation mode until “easy talk off” |
| `sigmaresearch` | topic · date range · depth | Reports sources actually read and access gaps |

### Requirements

| Skill | Needs |
|-------|--------|
| All | An agent that can load Agent Skills (`SKILL.md`) |
| Sigma Installer | Node.js 22 or newer |
| SigmaReview | Read access to the target repo · GitHub tooling to push a branch or fork and open a PR · execution authority only if you want measured findings |
| SigmaImprove | Read access to the target · GitHub issue access only if tickets go to GitHub |
| SigmaShip | Push rights and GitHub tooling (`gh` or connector) to open, merge, and close; the repository's test commands |
| SigmaBrief | `gh` read access when briefing from issues or PRs · **no** push to the product repo |
| SigmaWrite | Nothing beyond chat |
| SigmaRefactor | Read access to the target repository · `laloc` is optional; without it the skill counts lines itself |
| EasyTalk | A writable output folder and a browser or HTML preview; chat fallback when unavailable |
| SigmaResearch | Public fetch/search tools · curl for Reddit · Claude in Chrome and owner's existing session for X; missing tools become access gaps |

Skills use the shell native to the machine that runs the agent (PowerShell on Windows, POSIX shell elsewhere). They do not assume WSL.

SigmaShip and SigmaBrief work best with optional companion skills from [mattpocock/skills](https://github.com/mattpocock/skills): `/to-spec` and `/to-tickets` turn an idea into a ticket with acceptance criteria, `/grilling` settles open decisions, and `/tdd` guides test-first work. Without them, the skills fall back to plain steps.

---

## Links

- [Installer guide](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/docs/installer.md): every command, flag, and install method
- [Maintainer guide](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/docs/maintainers.md): tests, CI, releases, and registry automation
- [Skill evals](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/docs/evals.md): how each skill's output is checked, and the latest results
- [CHANGELOG.md](CHANGELOG.md): what changed in each Release
- [AGENTS.md](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/AGENTS.md): the working rules for agents in this repository
- [CONTEXT.md](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/CONTEXT.md): the words this project uses, such as Skill Pack and Agent Host
- [Decision records](https://github.com/Djordje-Stojanovic/Sigmaskills/tree/main/docs/adr): why the installer works the way it does
- [New issue](https://github.com/Djordje-Stojanovic/Sigmaskills/issues/new/choose): bug, feature, improvement, or docs

## License

[MIT](LICENSE) © Djordje Stojanovic
