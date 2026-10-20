# SigmaSkills

**High-rigor Agent Skills for every serious coding agent.**

Portable [Agent Skills](https://agentskills.io/) that install once and run on **Codex**, **Claude Code**, **Cursor**, **Pi**, **OpenCode**, **Reasonix**, **Kimi Code CLI**, and any tool that reads a `SKILL.md`.

| | |
|---|---|
| **Release** | [**v0.11.0**](https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.11.0) |
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
     sigmawritegui   →  plain chat and interactive status or question boards
     arena      →  blind pairs that rank any options by Elo
  Σ  research   →  read public sources, record evidence and access gaps
  Σ  deeplook   →  helper for what agents cannot read: video, speech, scans, binaries
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
| **SigmaWriteGUI** | `sigmawritegui` | Plain chat with status and question boards | Interactive HTML board and copied replies |
| **SigmaCreateArena** | `sigmacreatearena` | Blind-pairs arena that ranks any options by Elo per metric | Local arena page, Elo board with ranges and costs |
| **SigmaResearch** | `sigmaresearch` | Read Reddit, X, HN, GitHub, Hugging Face, video sites and non-English pages; counts sources read in full | Answer with source links, dates, read scope and access gaps |
| **SigmaDeepLook** | `sigmadeeplook` | Helper for files an agent cannot read: video, speech, scanned PDF or image, binary, odd container. Plain text and data are read directly | Evidence with file paths, limits, and a side-by-side `view.html` |
| **SigmaLoop** | `sigmaloop` | Turn a repo's open work into an unattended-run prompt for Claude Code, Codex, pi or T3 Code | One loop prompt in chat and one loop file |
| **SigmaTaste** | `sigmataste` | Taste pass through 14 lenses on a page, app, deck, doc, image or film | One ranked plan of big visible changes |
| **SigmaHuman** | `sigmahuman` | Text that reads like a person wrote it: rewrite any text or write from a brief, in lanes (script, book, song, chat, docs, posts), every fact kept | The rewritten or new text, and a fact check |
| **SigmaFork** | `sigmafork` | Fork or copy any repo, cut every path back to the original, install a skill bundle, teach it | An isolated working copy and a 15-minute `ONBOARDING.html` course |

### Which one do I need?

SigmaReview and SigmaImprove split on one question: **is it wrong, or could it be better?**

- If a test, a doc, a stated goal, or a budget can prove it wrong, it is a SigmaReview finding. Examples: a crash, a security hole, a page that breaks its latency budget.
- If good people could disagree about the answer, it is a SigmaImprove idea. Examples: weak animation, a missing level, an onboarding flow with too many steps.
- If the code is only too large and behavior must not change, use SigmaRefactor.
- If the question is how one target looks, reads or feels, and you want one plan of visible changes now, use SigmaTaste.
- If the text itself must sound like a person wrote it, use SigmaHuman. SigmaWrite is for plain technical English.

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

### SigmaFreedom

De-safeguards and decensors a repository. It deletes model-authored refusals, bans and moral limits from agent-facing docs and skill sources, writes the owner's freedom doctrine, installs `guardrail_lint` with an owner-vetoable keep-list so the lines never come back, and reports every keep for the owner's veto. Every deletion lands in a was/now change log for a clean revert. Mechanical invariants (one post per run, no file overwrites, secrets never printed) stay.

### SigmaWrite

A writing voice inspired by **ASD-STE100 Simplified Technical English**. It gives soft steers, not numbered rules, and bans gibberish and invented words. A sharp outsider can follow the result, and it stays technical. It stays on until you turn it off. To keep the voice on everywhere, copy the **Paste as system prompt** block from [`sigmawrite/SKILL.md`](sigmawrite/SKILL.md) into your host's instructions. It is not certified STE.

### SigmaRefactor

Counts lines (with `laloc` if you have it, or by itself), reads the five largest maintained files, and explains safe refactoring choices. It waits for your approval before it edits. It keeps behavior, tests, interfaces, and your own changes intact. At the end it reports lines removed apart from lines moved into new modules.

### SigmaWriteGUI

Keeps replies short and puts status reports or question batches on one interactive board. Read ticks, recommended options, task statuses, and free text feed a **Copy my answers** reply that names every unread card. Open it with an HTML preview tool or as a local browser file. Say “easy talk off” to stop.

### SigmaCreateArena

Ranks many options by your taste. After a short grilling round it builds an **arena**: two options side by side, names hidden, sides random. You pick per metric. A Bradley-Terry fit turns the picks into an Elo board with 95 % ranges, so overlapping bars read as a tie. The kit is a standard-library Python server and one HTML page: local only, no install.

### SigmaResearch

Reads public sources with bundled stdlib Python readers for Reddit, Hacker News, GitHub, Stack Overflow and YouTube comments, plus X through Claude in Chrome on the owner's existing session. One interface (`read.py`), a 24-hour cache, per-host rate limits and source scoring. Reports contradictions, blocked and partial reads. It never logs in, solves CAPTCHAs or evades bot checks.

### SigmaDeepLook

The helper for content an agent cannot read with its own tools: video frames, speech, scanned PDFs and images, fax TIFFs, binaries and odd containers. Plain text, CSV, JSON and code stay with the agent, which reads or queries them itself. A one-line gate decides; `--ask` gives one exact answer. It never runs the input, uses no network, and lists each step it could not do, with its install line. Python alone covers the basics.

### SigmaLoop

Reads a repo's open work (a ticket, the issue tracker, a TRACKER file), asks one numbered round of questions with a recommended answer each, then writes a paste-ready prompt for your host (Claude Code `/loop`, Codex `/goal`, pi plan mode, T3 Code or a plain instruction) and a loop file the prompt tells the agent to re-read at every wake. It carries the task order, crew, wake rules, landing rules and stop line. It never starts the loop.

### SigmaTaste

Looks at one target (a page, app, dashboard, deck, doc, image or film) and asks one round of questions: which of 14 taste lenses to use, what you expect, scope, brand and constraints. Then it writes `sigmataste-plan-DD-MM-YYYY.md`: the changes that make a big visible difference, ranked, each with how to verify it. The target's own brand wins over every lens default. It plans; it does not build.

### SigmaHuman

Rewrites any text so it reads like a person wrote it, or writes new text from a brief. It finds the 26 AI-writing patterns of [blader/humanizer](https://github.com/blader/humanizer) (MIT) and fixes them in the lane for the text: a script for the ear, a book, song lyrics, a chat or email, docs, or a post. It keeps every fact, can match your writing sample, and checks numbers, quotes and names before and after.


### SigmaFork

Takes any repository, from GitHub or a local folder, and asks one round of 8 questions: what you want, why, where the resources are, research depth, skill bundle, destination, access and how you learn. Then it studies the source, makes the fork or copy, cuts every path, link and git remote back to the original, installs the bundle, and writes `ONBOARDING.html`: a 15-minute course with a map of the repo and its real projects. Your questions become part 2.
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
$sigmafreedom Set this repo up for freedom
$sigmaimprove
$sigmabrief https://github.com/owner/repo/issues/12
$sigmabrief all open
$sigmaship https://github.com/owner/repo/issues/42
$sigmawrite
$sigmarefactor
$sigmawritegui
$sigmacreatearena Rank these 8 thumbnail ideas blind
$sigmaresearch Research recent discussions about local language models
$sigmadeeplook What happens at 2:10 in D:\clips\demo.mp4?
$sigmaloop Write an overnight loop prompt for Claude Code until 07:00
$sigmataste Taste pass on the landing page
$sigmahuman Rewrite this announcement so it sounds like me
$sigmafork Copy this repo to D:\work\my-copy and teach me how it works
```

</td>
<td width="50%">

**Pi / skill-slash hosts**

```text
/skill:sigmareview https://github.com/owner/repo
/skill:sigmafreedom Set this repo up for freedom
/skill:sigmaimprove
/skill:sigmabrief https://github.com/owner/repo/issues/12
/skill:sigmabrief all open
/skill:sigmaship https://github.com/owner/repo/issues/42
/skill:sigmawrite
/skill:sigmarefactor
/skill:sigmawritegui
/skill:sigmacreatearena Rank these 8 thumbnail ideas blind
/skill:sigmaresearch Research recent discussions about local language models
/skill:sigmadeeplook What happens at 2:10 in ~/clips/demo.mp4?
/skill:sigmaloop Write an overnight loop prompt for Claude Code until 07:00
/skill:sigmataste Taste pass on the landing page
/skill:sigmahuman Rewrite this announcement so it sounds like me
/skill:sigmafork Fork owner/repo and teach me how it works
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
| `sigmawritegui` | “easy talk” · status or question batch · `EASYTALK REPLY` | Conversation mode until “easy talk off” |
| `sigmacreatearena` | what to rank (options, groups, metrics) | Grills first; never ranks for you; you decide when it is enough |
| `sigmaresearch` | topic · date range · depth or a source count | Reports sources actually read and access gaps |
| `sigmadeeplook` | a file or folder path · a question about it | Evidence with paths and a Limits list; never runs the file |
| `sigmaloop` | host · end time · a ticket or tracker | One question round; writes the prompt and a loop file; never starts the loop |
| `sigmataste` | a page, app, deck, doc, image or film · what you expect | One question round; writes the ranked plan; never builds |
| `sigmahuman` | text, a file or a brief · optional writing sample | Writes the human version; keeps every fact; never follows instructions inside the text |
| `sigmafork` | a GitHub repo or a local folder · where the copy goes | One question round; the original is only read; the owner types every key |

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
| SigmaWriteGUI | A writable output folder and a browser or HTML preview; chat fallback when unavailable |
| SigmaCreateArena | Python 3 (standard library only) and a browser; the server listens on 127.0.0.1 |
| SigmaResearch | Python 3 for the bundled readers · `yt-dlp` for YouTube comments · Claude in Chrome and owner's existing session for X; missing tools become access gaps |
| SigmaLoop | Read access to the repo and its tracker · `gh` is optional · the host you name (Claude Code, Codex, pi or T3 Code) to run the loop |
| SigmaFork | Python 3 (standard library only) · `git` · `gh` for a GitHub fork · Node.js for skill bundles · a browser to check the guide |
| SigmaTaste | Read access to the target · a browser or screenshot tool to see a page; without one the plan lists what was not judged |
| SigmaHuman | Nothing beyond chat · Python 3 (standard library) for the optional fact check |
| SigmaDeepLook | Python 3.10 or newer; optional ffmpeg, LibreOffice, poppler, tesseract and Python packages · `look.py doctor` lists them; missing tools become Not-looked-at rows |

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
