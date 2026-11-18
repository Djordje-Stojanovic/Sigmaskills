# SigmaSkills

## On a new machine: one line

Claude Code is all you need: no Node. The Git Bash line needs Git for Windows; the PowerShell line does not. One line copies every Sigma skill into `~/.claude/skills`. Run it again later to update. Inside Claude Code, type `!` first to run it in the session's shell.

macOS, Linux, Git Bash:

```bash
d=$(mktemp -d) && curl -fsSL https://github.com/Djordje-Stojanovic/Sigmaskills/archive/refs/heads/main.tar.gz | tar -xz -C "$d" --strip-components=1 && mkdir -p ~/.claude/skills && for s in "$d"/sigma*; do [ -f "$s/SKILL.md" ] && cp -R "$s" ~/.claude/skills/; done; rm -rf "$d"
```

Windows PowerShell:

```powershell
$t = "$env:TEMP\sigmaskills-src"; Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory $t | Out-Null; curl.exe -fsSL -o "$t.tgz" https://github.com/Djordje-Stojanovic/Sigmaskills/archive/refs/heads/main.tar.gz; if ($LASTEXITCODE -eq 0) { tar -xzf "$t.tgz" -C $t --strip-components=1 }; if ($LASTEXITCODE -eq 0) { New-Item -ItemType Directory "$HOME\.claude\skills" -Force | Out-Null; Get-ChildItem $t -Directory -Filter sigma* | Where-Object { Test-Path "$($_.FullName)\SKILL.md" } | Copy-Item -Destination "$HOME\.claude\skills" -Recurse -Force }; Remove-Item $t, "$t.tgz" -Recurse -Force
```

No install at all: skills you turn on in your claude.ai account load in Claude Code when you sign in with that account. That needs Claude Code 2.1.273 or later. It does not work with an API key or on Amazon Bedrock ([how](https://code.claude.com/docs/en/skills#how-synced-skills-behave)). To add your own skills in claude.ai, go to Customize, then Skills, click +, choose Create skill, then Upload a skill, and upload one ZIP per skill folder.

**High-rigor Agent Skills for every serious coding agent.**

Portable [Agent Skills](https://agentskills.io/) that install once and run on **Codex**, **Claude Code**, **Cursor**, **Pi**, **OpenCode**, **Reasonix**, **Kimi Code CLI**, and any tool that reads a `SKILL.md`.

| | |
|---|---|
| **Release** | [**v0.25.0**](https://github.com/Djordje-Stojanovic/Sigmaskills/releases/tag/v0.25.0) |
| **Changelog** | [CHANGELOG.md](CHANGELOG.md) |
| **License** | [MIT](LICENSE) |
| **Spec** | [agentskills.io](https://agentskills.io/) |

## What it is

SigmaSkills is a set of skills for coding agents. A skill is a folder with one `SKILL.md` that tells an agent how to do one job well. It can review a repo, ship a ticket, write a plan or read a video. You install the skills once. Then you call them by name in Codex, Claude Code, Cursor, Pi and any other host that reads `SKILL.md`.

## Install in one line

```bash
npx @djordje-stojanovic/sigmaskills
```

The wizard has three steps: **What**, **Where**, **Review**. It writes nothing until you confirm. The first screen names the scope it works in, Project or Global, and `s` switches it. There, `u` updates every skill installed in that scope and `x` uninstalls them all. For a script, one line does it all: `npx @djordje-stojanovic/sigmaskills install --preset core --global --yes`. `core` is every Sigma skill plus the whole Matt Pocock pack and Theo Browne's whole tstack pack, and a bare `install --global --yes` means `--preset core`. Every other pack goes into one repo at a time: `install --pack threejs --project .` (`--pack` is the same flag as `--preset`).

## Stay current

Updates start with a release on npm. A merge to `main` never publishes. To move every skill on a machine to the newest release, run one line there:

```bash
npx @djordje-stojanovic/sigmaskills@latest update --global --yes
```

Use `--project .` in place of `--global` for a repo. Add `--dry-run` to preview. `update --check` lists each skill that is out of date and writes nothing; it exits 1 when one exists. A skill you edited is never replaced without your say: `update` keeps your Skill Customization block and asks about other edits. `status` shows drift. To keep many machines current, run the same line on each one, from a scheduled task or a login script.

---

## After the install


![The What step: packs with counts, one pack opened to pick single skills](https://raw.githubusercontent.com/Djordje-Stojanovic/Sigmaskills/main/docs/images/installer-what.svg)

![The summary after an install](https://raw.githubusercontent.com/Djordje-Stojanovic/Sigmaskills/main/docs/images/installer-done.svg)

### Presets

`--preset <pack>` installs a whole pack, and the wizard lists every pack. `npx @djordje-stojanovic/sigmaskills packs` prints every pack with its skill count and source. The 18 packs, with their skills, source, licence and needs: [Packs](#packs).

### Without the wizard

Every choice has a flag, so scripts and CI skip the wizard. Name skills, presets, and Agent Hosts (`claude`, `codex`, `gemini`, `agy`, `pi`, `cursor`, or any registry id).

```bash
npx @djordje-stojanovic/sigmaskills install sigmawrite --project .
npx @djordje-stojanovic/sigmaskills install --preset sigma --agent claude --project .
npx @djordje-stojanovic/sigmaskills install --preset all --global --yes
npx @djordje-stojanovic/sigmaskills update --global --yes
```

The [installer guide](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/docs/installer.md) explains presets, host folders, Global Installation, `status`, `update`, `restore`, `uninstall`, and `purge`.

---

## The skills

Each skill has one job. Say its name to start it.

| Skill | Id | What it does |
|-------|-----|--------------|
| **SigmaReview** | `sigmareview` | Finds and proves what is wrong in a repo, in one PR |
| **SigmaImprove** | `sigmaimprove` | Lists what would make a product better than the best in its field |
| **SigmaBrief** | `sigmabrief` | Writes paste-ready briefs for other agents |
| **SigmaShip** | `sigmaship` | Ships one planned ticket: build, review, merge, clean up |
| **SigmaFreedom** | `sigmafreedom` | Removes model-written refusals from a repo's agent docs |
| **SigmaWrite** | `sigmawrite` | Plain technical English, and status boards on request |
| **SigmaDebug** | `sigmadebug` | Settles open topics one at a time and ships each fix |
| **SigmaCorrect** | `sigmacorrect` | Turns a correction you gave twice into a check that fails |
| **SigmaCreate** | `sigmacreate` | Makes a new skill, public or local, and proves an agent picks it up |
| **SigmaCourse** | `sigmacourse` | Plans and builds teaching of any size; the course decides its own process |
| **SigmaFinanceMan** | `sigmafinanceman` | Values any investment from free data: stocks, startups, GPUs, homes, gold, cards |
| **SigmaSetup** | `sigmasetup` | Sets up a repo for the installed packs and syncs your house rule files |
| **SigmaCreateArena** | `sigmacreatearena` | Ranks any options blind, by Elo |
| **SigmaResearch** | `sigmaresearch` | Reads public sources and counts those read in full |
| **SigmaDeepLook** | `sigmadeeplook` | Reads what agents cannot: video, speech, scans, binaries |
| **SigmaLoop** | `sigmaloop` | Writes the prompt and file for an unattended run |
| **SigmaTaste** | `sigmataste` | Writes one ranked plan of big visible changes |
| **SigmaHuman** | `sigmahuman` | Makes text read like a person wrote it |
| **SigmaTour** | `sigmatour` | Shows how a repo works in one visual page; copies it first, isolated, when you ask |
| **SigmaClimb** | `sigmaclimb` | Improves anything measurable, one judged change at a time (was SigmaSpeedLoop) |
| **SigmaMusk** | `sigmamusk` | Runs Musk's Algorithm on one thing, one codebase or a whole setup: measure, delete first |
| **SigmaBoat** | `sigmaboat` | Works tasks on boat.dev boxes copied from one base; watches, deletes and updates them |
| **SigmaVast** | `sigmavast` | Rents a GPU for one job through `lacompute`, inside the cap, and proves the teardown |

### Which one do I need?

SigmaReview and SigmaImprove split on one question: **is it wrong, or could it be better?**

- If a test, a doc, a stated goal, or a budget can prove it wrong, it is a SigmaReview finding. Examples: a crash, a security hole, a page that breaks its latency budget.
- If good people could disagree about the answer, it is a SigmaImprove idea. Examples: weak animation, a missing level, an onboarding flow with too many steps.
- If the code is only too large and behavior must not change, use SigmaMusk (`cut`).
- If the question is how one target looks, reads or feels, and you want one plan of visible changes now, use SigmaTaste.
- If the text itself must sound like a person wrote it, use SigmaHuman. SigmaWrite is for plain technical English.

The skills chain into two loops. **Fix:** SigmaReview → review PR → SigmaBrief or SigmaShip fixes each finding → merge. **Grow:** SigmaImprove → category issues → specs and tickets → SigmaShip.

### SigmaReview

Finds what breaks the system's own promises: bugs, security holes, slow paths, broken pages and weak tests. Each finding has a location, the cause, the impact, evidence, a fix and a proof test, so an LLM can fix it from that finding alone. All findings land in one review file on one PR. It never changes your code, and it measures or probes only a local instance you allow.

### SigmaImprove

Compares the product with the best one to three products in its field and with published bars such as WCAG 2.2. It writes ideas (three to five weighed options each) and signals (gaps a person must think about first) into one living issue per category. Later runs update those issues. It never edits the product.

### SigmaBrief

Turns issues, features, bugs or plain work into short, copy-pastable briefs for other agents, grouped into safe parallel waves. Each brief tells the agent to build in big steps, check once at the end and open a PR, and not to merge. It never does the work itself. It runs only when you ask for it by name.

### SigmaShip

Ships one issue that has checkable acceptance criteria: a worktree, a draft PR that tracks the criteria, test-first slices, and at most two review rounds by an agent one model up, until a round finds nothing serious. Then it merges, closes the ticket and cleans up. A ticket without criteria gets the name of the skill to run first.

### SigmaFreedom

Deletes model-written refusals and moral limits from a repo's agent docs and skill sources. A lint with a keep-list stops them coming back, and every deletion is in a was/now log for a clean revert. Mechanical rules, such as never printing secrets, stay.

### SigmaWrite

A writing voice inspired by ASD-STE100 Simplified Technical English: short sentences, common words, still technical. It stays on until you turn it off. To use it everywhere, paste the **Paste as system prompt** block from [`sigmawrite/SKILL.md`](sigmawrite/SKILL.md) into your host's instructions.

The GUI option keeps replies short and puts status reports or question batches on one interactive board. Say "easy talk" (or "sigmawrite gui") to start it. Your ticks and answers come back through **Copy my answers**. Say "easy talk off" to stop. This replaces the old SigmaWriteGUI skill.

### SigmaDebug

Turns open questions into merged fixes while you talk. It writes every topic to a text file and opens it. In chat it shows one topic per message, in 5 parts with 3 options, the likely pick first, and grills until the topic is clear. Each clear topic gets a short plan and a background SigmaShip worker that merges and deploys without asking you. Another model can answer for you.

### SigmaCorrect

Makes a correction you gave twice impossible to need a third time. It finds the repeat in your words and the git history, then fixes it at the highest level that works: delete the wrong way, a type, a check in the test command whose error names the fix, a test, and a line in `AGENTS.md` last. The check must fail on the real past mistake before it counts.

### SigmaCreate

Makes one new skill by one of two routes. A public skill is one you publish: it holds no names, paths, accounts, hosts or keys, and a search proves that before it ships. A local skill belongs to one project, repo or machine and may name its paths and commands; it lands where that agent loads skills. Either way it ends installed, with a fresh agent naming it.

### SigmaCourse

Plans and builds teaching of any size, subject, audience and medium. It first writes what the learner can do at the end, maps every ability that needs, and derives the parts, their order and their length from that map. The map also decides which steps of the process run, so a short piece gets almost none and a long program gets a spec, a checked done list, a course repo and a goal prompt. Delivery is part of the job: one design file, the learner's path on phone and desktop, a performance budget measured in the built course, and accessibility.

### SigmaFinanceMan

Values a public company from free data it fetches itself: SEC filings, the share price and the 10-year Treasury rate. It runs a DCF, comps, an LBO, a three-statement model, ratios, red flags, a value scorecard and an earnings review, or a household budget from your own file. The DCF gives a bear, base and bull value and what the share price implies (a reverse DCF: the growth the market is betting on). Each run writes an Excel workbook with live formulas, a deck, charts and one page that walks through the method in ten plain steps. Use the Financial Services pack instead when you have your own model template or a paid data feed.

### SigmaSetup

Run it once per repo after the installer, and again when your master rule files change. It brings the repo's copies of your house files (`ENGINEERING.md`, `DESIGN.md`, a shared `AGENTS.md` section) up to date from the folder or repo where you keep the masters. It also sets up what each installed pack needs here: tracker files, labels, tools, keys by name, Ponytail and a git guard. It reports first, asks once, and gives an undo for every change.

### SigmaCreateArena

Ranks many options by your taste: two at a time, names hidden, sides random, one pick per metric. The picks become an Elo board with 95 % ranges, so overlapping bars read as a tie. Local only, no install.

### SigmaResearch

Reads Reddit, X, Hacker News, GitHub, Stack Overflow, YouTube and pages in other languages, and counts only sources it read in full. When a site blocks, it takes the next route. The answer lists every source, every contradiction and every gap.

### SigmaDeepLook

Reads what an agent cannot: video frames, speech, scanned PDFs and images, binaries and odd containers. Plain text and data stay with the agent. It never runs the input, uses no network and lists every step it could not do.

### SigmaLoop

Reads a repo's open work, asks one round of questions, then writes a paste-ready prompt for your host's unattended mode (Claude Code, Codex, pi, T3 Code or a plain instruction) and a loop file the agent re-reads at every wake. The loop file sets big steps, checks once at the end, no idle agent slots and a model per difficulty. It never starts the loop.

### SigmaTaste

Looks at one page, app, deck, doc, image or film through 14 taste lenses, asks one round of questions, then writes one ranked plan of the changes that make a big visible difference, each with how to check it. It plans; it does not build.

### SigmaHuman

Rewrites any text so it reads like a person wrote it, or writes new text from a brief, in the right lane: a script, a book, a song, a chat, docs or a post. It keeps every fact and can match your writing sample. It builds on [blader/humanizer](https://github.com/blader/humanizer) (MIT).

### SigmaTour

A 15-60 minute tour of any repo in one page: a clickable map, one request traced, real runs, and the README held against the code. Ask it to copy the repo first and it copies any repository after 8 questions, cuts every path, link and git remote back to the original, installs your skills, and tours the copy. (Was two skills; SigmaFork is retired.)

### SigmaClimb

Improves anything you can measure: model serving speed, a render, a kernel, an algorithm. It asks what better and no loss mean to you, locks a scoring script the agent cannot edit, measures the noise, adds a quality gate and a held-out check on inputs the agent never sees, then tries one change per pass. It keeps only what the script confirms, and charts who found each champion. Serving a model on a rented GPU is the worked example. (Was SigmaSpeedLoop; `speed loop` still finds it.)

### SigmaMusk

Runs Elon Musk's five-step Algorithm on your work, at three sizes. **One thing** (a plan, a feature, a process): it measures the waste, files one issue with a ranked delete list and checkable acceptance criteria, shows the numbers on a report page, answers in Musk's voice and offers SigmaShip. Alone, it grills you with 3 to 5 questions first; `--fast "<problem>"` researches, decides and ships end to end; `--demon` turns the voice up. **One codebase** (`cut`, was SigmaRefactor): it counts lines, reads the five largest files and explains safe ways to shrink them; it edits only after your approval and keeps behavior, tests and public interfaces. **A whole setup** (`reset`, was SigmaReset): it opens every thing before it judges it, groups what it finds into 15 to 30 products with their cost and proven use, asks you keep or kill, deletes the rest in every place it lives and keeps one map file as the handoff.

### SigmaBoat

Gives work you already authorized more machines: boat.dev cloud sandboxes (full Ubuntu VMs, no GPU). It builds one stopped base per repo, forks one sandbox per worker, runs each worker's gate there, lands the result by the work's own rules, and deletes every sandbox it started. It starts nothing unless you name boat.

---

## Packs

A pack is a named group of skills from one source. `--preset <id>` installs a whole pack, a skill id installs one skill, and `--preset all` installs every pack. A pack skill is downloaded from its source, at the pinned point, when you install it. In the wizard, `p` shows the full `SKILL.md` of the highlighted skill before you pick it. `list --packs` prints the same list in a terminal. Every pack has one category: Engineering, Design, Media, Research, Marketing, Finance or Productivity. The wizard shows the packs first, then the one-skill sources under their category, and `/design` (or any category name) filters to every skill in that category.

### Sigma (`sigma`)

Review, improve, ship, research and write. The first-party Sigma skills.

- **Category:** Engineering.
- **Skills:** every skill under [The skills](#the-skills).
- **Source:** this package. Licence: MIT. Also answers to: `sigmaskills`.
- **Needs:** Python 3 for the skills that ship a script; see [Requirements](#requirements).

### Matt Pocock (`mattpocock`)

Skills for real engineers: grill, spec, TDD, triage, deep modules.

- **Category:** Engineering.
- **Skills (39):** `ask-matt`, `chief-of-staff`, `claude-handoff`, `code-review`, `codebase-design`, `diagnosing-bugs`, `domain-modeling`, `git-guardrails-claude-code`, `grill-me`, `grill-with-docs`, `grilling`, `handoff`, `implement`, `implement-spec`, `improve-codebase-architecture`, `loop-me`, `migrate-to-shoehorn`, `pr`, `prototype`, `research`, `retro`, `scaffold-exercises`, `setup-matt-pocock-skills`, `setup-pre-commit`, `setup-ts-deep-modules`, `software-factory`, `tdd`, `teach`, `to-questionnaire`, `to-spec`, `to-tickets`, `triage`, `wait-what`, `wayfinder`, `wizard`, `writing-beats`, `writing-for-agents`, `writing-fragments`, `writing-shape`.
- **Source:** [mattpocock/skills](https://github.com/mattpocock/skills). Licence: MIT. Also answers to: `matt`, `pocock`.
- **Needs:** run `/setup-matt-pocock-skills` once per repo (it asks where issues live and writes `docs/agents/`); the issue skills use `gh` or `glab`.

### Three.js (`threejs`)

Geometry, materials, lighting, shaders, loaders, post-processing, R3F.

- **Category:** Media.
- **Skills (13):** `threejs-animation`, `threejs-asset-pipeline`, `threejs-fundamentals`, `threejs-geometry`, `threejs-interaction`, `threejs-lighting`, `threejs-loaders`, `threejs-materials`, `threejs-performance`, `threejs-postprocessing`, `threejs-react-three-fiber`, `threejs-shaders`, `threejs-textures`.
- **Source:** [CloudAI-X/threejs-skills](https://github.com/CloudAI-X/threejs-skills). Licence: MIT. Also answers to: `three`.
- **Needs:** the skills target `three@0.186`, React Three Fiber 9.8 and drei 10.7; `threejs-asset-pipeline` runs `npx @gltf-transform/cli`, so it needs Node.

### HyperFrames (`hyperframes`)

HTML to video: the HyperFrames skill, CLI, registry, media and slideshows, plus the student kit.

- **Category:** Media.
- **Skills (20):** `figma`, `hyperframes`, `hyperframes-cli`, `hyperframes-registry`, `media-use`, `remotion-to-hyperframes`, `reverse-any-video`, `slideshow`, `style-sampling`, `cut-mistakes`, `cut-silences`, `edit-video`, `gsap`, `hyperframes-video-beats`, `make-a-video`, `motion-showreel`, `short-form-edit`, `style-library`, `video-storytelling`, `website-to-hyperframes`.
- **Source:** [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes), pinned to tag `v0.9.65` and [nateherkai/hyperframes-student-kit](https://github.com/nateherkai/hyperframes-student-kit), pinned to commit `10511e5`. Licence: Apache-2.0 (HyperFrames); the student kit has its own licence file. Also answers to: `hf`.
- **Needs:** Node.js 22+, FFmpeg and Chrome. Optional keys: `GEMINI_API_KEY`, `HEYGEN_API_KEY`, `FIGMA_TOKEN`.

### MiniMax H3 (`minimax-h3`)

Prompt writing and eight video recipes for the MiniMax H3 model.

- **Category:** Media.
- **Skills (9):** `3d-animation-short-generator`, `brand-promo-video-generator`, `co-op-game-intro-generator`, `h3-prompt-writing`, `handdrawn-live-video-generator`, `minimalist-product-ad-generator`, `music-video-subtitle-generator`, `paper-collage-explainer-generator`, `papercraft-stop-motion-explainer`.
- **Source:** [MiniMax-AI/MiniMax-H3](https://github.com/MiniMax-AI/MiniMax-H3). Licence: no licence that GitHub reports. Also answers to: `minimax`, `h3`.
- **Needs:** `h3-prompt-writing` works in any agent; the other 8 skills need the MiniMax Hub agent and its image and video tools.

### Anthropic (`anthropic`)

Anthropic's skills: document skills (docx, pdf, pptx, xlsx), Claude API reference, MCP builder, skill creator and more.

- **Category:** Productivity.
- **Skills (19):** `academy-guide`, `algorithmic-art`, `brand-guidelines`, `canvas-design`, `claude-api`, `discernment-nudge`, `doc-coauthoring`, `docx`, `frontend-design`, `internal-comms`, `mcp-builder`, `pdf`, `pptx`, `skill-creator`, `slack-gif-creator`, `theme-factory`, `web-artifacts-builder`, `webapp-testing`, `xlsx`.
- **Source:** [anthropics/skills](https://github.com/anthropics/skills), pinned to commit `e4bb5d9`. Licence: no repo-wide licence that GitHub reports; check each skill folder. Also answers to: `anthropics`.
- **Needs:** `docx`, `pdf`, `pptx` and `xlsx` need Python or Node libraries and LibreOffice; `webapp-testing` needs Playwright; `mcp-builder` needs `ANTHROPIC_API_KEY` for evaluations. The rest need nothing.

### Design.md (`design-md`)

84 brand DESIGN.md files, each one a skill. Pick up to 3 at a time.

- **Category:** Design.
- **Skills (84):** `design-1win`, `design-airbnb`, `design-airtable`, `design-aljazeera`, `design-apple`, `design-binance` and 78 more; `list --packs --json` prints all of them.
- **Source:** [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md), pinned to commit `fcc7028`. Licence: MIT. Also answers to: `design`, `awesome-design-md`.
- **Needs:** nothing to install. Put the chosen look in the project root as `DESIGN.md`. **At most 3 installed at a time**; the wizard asks which one to drop for a fourth.

### Last 30 Days (`last30days`)

Research what people say about any topic in the last 30 days, across Reddit, X, YouTube, Hacker News and more.

- **Category:** Research.
- **Skills (1):** `last30days`.
- **Source:** [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill), pinned to tag `v4.3.2`. Licence: MIT. Also answers to: `last30`.
- **Needs:** Python 3.12+ and Node 22+. One-time `scripts/last30days.py setup`, run by you. Every key is optional.

### Financial Services (`financial-services`)

Anthropic finance plugins as skills: DCF, LBO, comps, pitch decks, earnings, fund admin, KYC.

- **Category:** Finance.
- **Skills (99):** `3-statement-model`, `accrual-schedule`, `ai-readiness`, `analyze-bond-basis`, `analyze-bond-rv`, `analyze-fx-carry` and 93 more; `list --packs --json` prints all of them.
- **Source:** [anthropics/financial-services](https://github.com/anthropics/financial-services), pinned to commit `3e32c22`. Licence: Apache-2.0. Also answers to: `fsi`, `finance`.
- **Needs:** the data comes through MCP servers (Daloopa, Morningstar, S&P Global, FactSet and more); each may need a subscription. Without one, the skills work on numbers you give.

### tstack (`tstack`)

Theo Browne's agent skills for shipping PRs: full-send, council, babysit-pr, file-pr and more.

- **Category:** Engineering.
- **Skills (9):** `babysit-pr`, `council`, `file-pr`, `full-send`, `full-stop`, `leaving-pr-comments`, `modernize`, `sol-loop`, `takeover`.
- **Source:** [t3dotgg/tstack](https://github.com/t3dotgg/tstack), pinned to commit `11e37a7`. Licence: MIT. Also answers to: `theo`.
- **Needs:** `gh`, signed in. `babysit-pr` needs `python3`. `council` and `sol-loop` ask reviewers on other providers' models, so they need a host that can run those.

### Superpowers (`superpowers`)

Jesse Vincent's workflow skills: brainstorm, write a plan, execute it, TDD, debug, review, finish the branch.

- **Category:** Engineering.
- **Skills (15):** `brainstorming`, `diagnosing-superpowers`, `dispatching-parallel-agents`, `executing-plans`, `finishing-a-development-branch`, `receiving-code-review`, `requesting-code-review`, `subagent-driven-development`, `systematic-debugging`, `test-driven-development`, `using-git-worktrees`, `using-superpowers`, `verification-before-completion`, `writing-plans`, `writing-skills`.
- **Source:** [obra/superpowers](https://github.com/obra/superpowers), pinned to commit `22f0b46`. Licence: MIT. Also answers to: `obra`.
- **Needs:** nothing to install. Upstream loads `using-superpowers` at session start through its plugin hook; a plain skill install has no hook, so call the skills by name.

### Impeccable (`impeccable`)

Paul Bakaus's design vocabulary for agents: one skill with commands to audit, polish, critique and restyle a frontend.

- **Category:** Design.
- **Skills (1):** `impeccable`.
- **Source:** [pbakaus/impeccable](https://github.com/pbakaus/impeccable), pinned to commit `d41d986`. Licence: Apache-2.0. Also answers to: `pbakaus`.
- **Needs:** Node, for its `npx impeccable` detector. Run `/impeccable init` once per project; it writes `PRODUCT.md`. Scanning a rendered page uses your installed Chrome or Edge.

### Security Audit (`security-audit`)

Cloudflare's security audit skill: find vulnerabilities and verify each finding before it is reported.

- **Category:** Engineering.
- **Skills (1):** `security-audit`.
- **Source:** [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill), pinned to commit `c1c8a8c`. Licence: MIT. Also answers to: `cloudflare`, `audit`.
- **Needs:** an agent with tool use and parallel sub-agents, and Node.js for the two validators (no dependencies).

### Anatomy (`anatomy`)

Detailed, interactive isometric illustrations of real machines and how they work.

- **Category:** Design.
- **Skills (1):** `anatomy`.
- **Source:** [wheresryan22/anatomy](https://github.com/wheresryan22/anatomy), pinned to commit `1482e84`. Licence: MIT. Also answers to: `isometric`.
- **Needs:** Node 20.10 or later. No API keys and nothing to `npm install`.

### Diagram Design (`diagram-design`)

Cathryn Lavery's editorial diagrams: architecture, flow, sequence and more as clean HTML and SVG.

- **Category:** Design.
- **Skills (1):** `diagram-design`.
- **Source:** [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design), pinned to commit `f6db0de`. Licence: MIT. Also answers to: `diagram`, `diagrams`.
- **Needs:** nothing to install: a diagram is plain HTML and SVG, with no build step.

### Taste (`taste-skill`)

Art direction for coding agents: reference images, a visual brief and a browser check, so a page does not look generated.

- **Category:** Design.
- **Skills (1):** `taste-skill`.
- **Source:** [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill), pinned to commit `f6b7657`. Licence: MIT. Also answers to: `taste`, `leonxlnx`.
- **Needs:** Node 22+ and an installed Chrome, Edge or Chromium (`CHROME_PATH` for an unusual place). ffmpeg is optional. No API keys.

### Hallmark (`hallmark`)

A design skill that refuses the AI look: new pages, audits, redesigns and design extraction.

- **Category:** Design.
- **Skills (1):** `hallmark`.
- **Source:** [Nutlope/hallmark](https://github.com/Nutlope/hallmark), pinned to commit `04977e1`. Licence: MIT. Also answers to: `nutlope`.
- **Needs:** Node 18 or later. The browser checks also need `npm i -g puppeteer-core` and Chrome; without them the static checks still run.

### Ponytail (`ponytail`)

The lazy senior developer: the smallest change that fully works, plus audit, review, debt and gain reports.

- **Category:** Engineering.
- **Skills (6):** `ponytail`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`, `ponytail-help`, `ponytail-review`.
- **Source:** [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail), pinned to tag `v5.3.3`. Licence: MIT. Also answers to: `lazy`.
- **Needs:** nothing. The [per-project plugin command](#ponytail-per-project) stays as an extra for agents that load plugins.

### Anthropic Engineering (`anthropic-engineering`)

Anthropic's engineering plugin as skills: architecture, code review, debugging, incidents, standups, system design, tech debt, testing.

- **Category:** Engineering.
- **Skills (9):** `architecture`, `debug`, `deploy-checklist`, `documentation`, `incident-response`, `standup`, `system-design`, `tech-debt`, `testing-strategy`.
- **Source:** [anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins), pinned to commit `e91a134`. Licence: Apache-2.0. Also answers to: `anthropic-eng`.
- **Needs:** nothing to install. Some skills ask for a connector (source control, issue tracker, monitoring); without one they work on what you paste. `code-review` is left out: Matt Pocock's pack has that name.

### Agent Skills (`agent-skills`)

Addy Osmani's engineering workflow: spec, plan, build in small steps, test, review, harden and ship.

- **Category:** Engineering.
- **Skills (24):** `api-and-interface-design`, `browser-testing-with-devtools`, `ci-cd-and-automation`, `code-review-and-quality`, `code-simplification`, `constraint-driven-development`, `context-engineering`, `debugging-and-error-recovery`, `deprecation-and-migration`, `documentation-and-adrs`, `doubt-driven-development`, `frontend-ui-engineering`, `git-workflow-and-versioning`, `idea-refine`, `incremental-implementation`, `interview-me`, `observability-and-instrumentation`, `performance-optimization`, `planning-and-task-breakdown`, `security-and-hardening`, `shipping-and-launch`, `source-driven-development`, `spec-driven-development`, `using-agent-skills`.
- **Source:** [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills), pinned to commit `39b723c`. Licence: MIT. Also answers to: `addy`, `addyosmani`.
- **Needs:** nothing to install. `browser-testing-with-devtools` needs the Chrome DevTools MCP server. Some skills link to checklists in the repo's `references/` folder, which a skill install does not copy. `test-driven-development` is left out: Superpowers has that name.

### Caveman (`caveman`)

Terse answers that keep every fact, plus lean build, patch, refactor and verify skills.

- **Category:** Engineering.
- **Skills (14):** `caveman`, `caveman-commit`, `caveman-compress`, `caveman-explore`, `caveman-help`, `caveman-review`, `investigate-first`, `lean-build`, `megacave`, `migration`, `safe-refactor`, `surgical-patch`, `ultracave`, `verify-and-stop`.
- **Source:** [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman), pinned to commit `a192894`. Licence: Apache-2.0. Also answers to: `cave`.
- **Needs:** nothing. The pack is plain skill files: no hooks, no settings changes, no edits to `CLAUDE.md`. `caveman-compress` needs Python 3 and sends the file you name to your model provider. Left out because they need more than a skill folder: `cavecrew` (its plugin's sub-agents), `caveman-stats` (its hook), `caveman-learn` (its CLI) and the five Caveman Cloud skills.

### Claude Red (`claude-red`)

Offensive security for authorized tests: web, API, cloud, Active Directory, wireless, exploit development and reports.

- **Category:** Engineering.
- **Skills (79):** `offensive-active-directory`, `offensive-advanced-redteam`, `offensive-ai-security`, `offensive-anti-forensics`, `offensive-api-abuse`, `offensive-api-security` and 73 more; `list --packs --json` prints all of them.
- **Source:** [SnailSploit/Claude-Red](https://github.com/SnailSploit/Claude-Red), pinned to commit `6196ba7`. Licence: MIT. Also answers to: `red`, `snailsploit`.
- **Needs:** the tools each skill names (for example `nmap` or Burp Suite), installed by you. Use it only on systems you are authorized to test.

### Dev Browser (`dev-browser`)

The agent drives a real Chrome through short scripts, with named pages that persist between runs.

- **Category:** Engineering.
- **Skills (1):** `dev-browser`.
- **Source:** [SawyerHood/dev-browser](https://github.com/SawyerHood/dev-browser), pinned to commit `520ba5c`. Licence: MIT. Also answers to: `sawyerhood`.
- **Needs:** `npm install -g dev-browser`, and Chrome (`dev-browser install` fetches one if none is found).

### Emil Kowalski (`emil-kowalski`)

Design engineering from the maker of Sonner: animation, gestures, Apple-style design, taste and UI reviews.

- **Category:** Design.
- **Skills (19):** `animate`, `animate-expo`, `animation-performance`, `animation-vocabulary`, `apple-design`, `ask-emil`, `ask-sonner`, `break-ui`, `choreograph`, `emil-design-eng`, `find-animation-opportunities`, `gestures`, `improve-animations`, `learn-taste`, `mobile-native`, `pick-ui-library`, `remove-animations`, `review-animations`, `write-swift`.
- **Source:** [emilkowalski/skills](https://github.com/emilkowalski/skills), pinned to commit `64eb3de`. Licence: MIT. Also answers to: `emil`.
- **Needs:** nothing to install. `prototype` is left out: Matt Pocock's pack has that name.

### Marketing Skills (`marketingskills`)

Corey Haines's marketing skills: copy, SEO, CRO, ads, email, pricing, launches, analytics and more.

- **Category:** Marketing.
- **Skills (53):** `ab-testing`, `ad-creative`, `ads`, `ai-seo`, `analytics`, `aso` and 47 more; `list --packs --json` prints all of them.
- **Source:** [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills), pinned to commit `73573e9`. Licence: MIT. Also answers to: `corey`, `coreyhaines`.
- **Needs:** nothing to install. Run `product-marketing` first: the other skills read the context file it writes (`.agents/product-marketing.md`). Some skills mention optional tools (Ahrefs, PostHog and others) that need their own accounts.

### LinkedIn (`linkedin`)

LinkedIn posts, comments, replies, hooks, profiles and analytics, each drafted for your approval.

- **Category:** Marketing.
- **Skills (12):** `linkedin-comment-drafter`, `linkedin-content-planner`, `linkedin-employee-advocacy`, `linkedin-engager-analytics`, `linkedin-hook-extractor`, `linkedin-humanizer`, `linkedin-interviewer`, `linkedin-post-writer`, `linkedin-profile-optimizer`, `linkedin-reply-handler`, `linkedin-repurposer`, `linkedin-thread-monitor`.
- **Source:** [sergebulaev/linkedin-skills](https://github.com/sergebulaev/linkedin-skills), pinned to commit `8f8bc4b`. Licence: MIT. Also answers to: `linkedin-skills`.
- **Needs:** nothing to draft. Publishing goes through a Publora account; without one, you post the approved text yourself.

### I Have ADHD (`i-have-adhd`)

Answers shaped for a reader with ADHD: next action first, numbered steps, no tangents, visible wins.

- **Category:** Productivity.
- **Skills (1):** `i-have-adhd`.
- **Source:** [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd), pinned to commit `1ecea19`. Licence: MIT. Also answers to: `adhd`.
- **Needs:** nothing. Turn it on with `/i-have-adhd`; it stays on until you say "stop adhd mode".

### Baoyu (`baoyu`)

Baoyu's content skills: cover images, infographics, comics, slides, diagrams, translation and posting to X, WeChat and Weibo.

- **Category:** Media.
- **Skills (21):** `baoyu-article-illustrator`, `baoyu-comic`, `baoyu-compress-image`, `baoyu-cover-image`, `baoyu-danger-gemini-web`, `baoyu-danger-x-to-markdown`, `baoyu-diagram`, `baoyu-electron-extract`, `baoyu-format-markdown`, `baoyu-image-gen`, `baoyu-infographic`, `baoyu-markdown-to-html`, `baoyu-post-to-wechat`, `baoyu-post-to-weibo`, `baoyu-post-to-x`, `baoyu-slide-deck`, `baoyu-translate`, `baoyu-url-to-markdown`, `baoyu-wechat-summary`, `baoyu-xhs-images`, `baoyu-youtube-transcript`.
- **Source:** [Djordje-Stojanovic/baoyu-skills](https://github.com/Djordje-Stojanovic/baoyu-skills), pinned to commit `1b7fb3f`. This is an English fork of [JimLiu/baoyu-skills](https://github.com/JimLiu/baoyu-skills), which is written in Chinese; Chinese stays only for trigger phrases, labels on Chinese sites and text that goes into an image. Licence: MIT. Also answers to: `baoyu-skills`, `jimliu`.
- **Needs:** Node.js (the scripts run with `npx bun`). The image skills need a key for an image API (OpenAI, Google and others). The posting skills drive your own Chrome and ask you to log in once.

**`local`** is a folder of your own skills (`SIGMA_LOCAL_SKILLS_DIR` or `~/.sigmaskills/packs.json`). **`all`** is every pack that is available on this machine.

**Graphify is not a pack:** its repo ships no `SKILL.md`. Its skill comes from its own tool: `uv tool install graphifyy && graphify install`.

Three more sources were checked and are not packs, because their skills break when copied out of their repo:

- **[gstack](https://github.com/garrytan/gstack):** almost every skill runs tools from its own install folder, built by `./setup` with Bun. Install it the way its README says.
- **[Agent Reach](https://github.com/Panniantong/Agent-Reach):** one templated skill that drives the `agent-reach` Python CLI. SigmaResearch already reads Reddit, X, YouTube and GitHub.
- **[Academic Research Skills](https://github.com/Imbad0202/academic-research-skills):** its five skills read shared folders at the repo root (`shared/`, `scripts/`, `agents/`). Install it as the Claude Code plugin it ships as.

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
$sigmadebug
$sigmacorrect Stop hardcoding: make it a check
$sigmacreate Turn what we just did into a skill for this repo
$sigmacourse A one-page guide to reading a balance sheet
$sigmafinanceman DCF and comps for MSFT against AAPL, GOOGL and META
$sigmasetup
$sigmacreatearena Rank these 8 thumbnail ideas blind
$sigmaresearch Research recent discussions about local language models
$sigmadeeplook What happens at 2:10 in D:\clips\demo.mp4?
$sigmaloop Write an overnight loop prompt for Claude Code until 07:00
$sigmataste Taste pass on the landing page
$sigmahuman Rewrite this announcement so it sounds like me
$sigmatour Copy this repo to D:\work\my-copy, isolated, and tour the copy
$sigmatour Give me a 30 minute tour of this repo
$sigmaclimb Set up a speed loop for my vLLM model on a rented H100
$sigmamusk Why does our test suite take 20 minutes?
$sigmamusk cut this repo: the five largest files
$sigmamusk reset: my setup is bloated, list every product, I say keep or kill
$sigmaboat Run .scratch/loops/2026-11-05-x.md on boat, two workers
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
/skill:sigmadebug
/skill:sigmacorrect
/skill:sigmacreate Turn what we just did into a skill for this repo
/skill:sigmacourse Plan a 10-hour course that makes me fluent in SQL
/skill:sigmafinanceman What does the price of KO assume?
/skill:sigmasetup Sync the house files
/skill:sigmacreatearena Rank these 8 thumbnail ideas blind
/skill:sigmaresearch Research recent discussions about local language models
/skill:sigmadeeplook What happens at 2:10 in ~/clips/demo.mp4?
/skill:sigmaloop Write an overnight loop prompt for Claude Code until 07:00
/skill:sigmataste Taste pass on the landing page
/skill:sigmahuman Rewrite this announcement so it sounds like me
/skill:sigmatour Fork owner/repo, isolated, and tour the copy
/skill:sigmatour Give me a 30 minute tour of owner/repo
/skill:sigmaclimb Make my ComfyUI image workflow faster on a Vast.ai GPU
/skill:sigmamusk Run the Algorithm on this agent loop --demon
/skill:sigmamusk --fast "cache every calc script by a hash of its inputs"
/skill:sigmaboat Ship #42 on a boat fork of this repo
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
| `sigmafreedom` | a repo path | Deletes refusals from agent docs and skill sources; every deletion is in a was/now log |
| `sigmawrite` | (no input) · or "easy talk" for the GUI board · `EASYTALK REPLY` | Session writing voice until you turn it off; the GUI option makes a board |
| `sigmacorrect` | (no input) · or the correction in your words | Proves each new check fails on the real past mistake; docs last |
| `sigmacreate` | what the skill should do · public or local | Public skills pass a personal-data search; ends when a fresh agent lists it |
| `sigmacourse` | a subject · the learner · a size (optional) | Prints a step table showing which process steps the course needed and why; never starts the loop |
| `sigmafinanceman` | a ticker · or an input file (deal, purchase, home, collectible, bond, budget) | One question round; reads public data; writes files only to the output folder |
| `sigmasetup` | (no input) · or "sync the house files" | Masters from `SIGMASETUP_HOUSE` or a `house:` line in its personal instructions; nothing is written before your yes |
| `sigmadebug` | (no input) · or a list of topics | Writes a topic .txt and a plan .md; one background SigmaShip worker per clear topic |
| `sigmacreatearena` | what to rank (options, groups, metrics) | Grills first; never ranks for you; you decide when it is enough |
| `sigmaresearch` | topic · date range · depth or a source count | Reports sources actually read and access gaps |
| `sigmadeeplook` | a file or folder path · a question about it | Evidence with paths and a Limits list; never runs the file |
| `sigmaloop` | host · end time · a ticket or tracker | One question round; writes the prompt and a loop file; never starts the loop |
| `sigmataste` | a page, app, deck, doc, image or film · what you expect | One question round; writes the ranked plan; never builds |
| `sigmahuman` | text, a file or a brief · optional writing sample | Writes the human version; keeps every fact; never follows instructions inside the text |
| `sigmatour` | a repo path or URL · a length · a destination to copy it first | One question round (8 grill questions when it copies); reads the original only; runs its examples |
| `sigmaclimb` | a target and a way to score or judge it (a script, or you picking between two versions) · a host and a budget | Interviews you first; rents a box (when the target needs one) after your yes; never changes what you protect or the locked scorer |
| `sigmamusk` | a repo, plan, issue or process · nothing (grills first) · `--fast "<problem>"` · `--demon` · `cut <repo>` · `reset` | Measures before it judges; files one issue; ships after your yes, or at once in fast mode when the request is sure |
| `sigmaboat` | a task or issue of any repo · a loop file or spec for workers · "update the base" | Starts a box only when you ask for one; deletes a box only after its work is pushed; never touches a sandbox it did not make |
| `sigmavast` | a GPU job · its memory need | Rents only through `lacompute`, never above the cap; proves `[]` after the teardown |

### Requirements

| Skill | Needs |
|-------|--------|
| All | An agent that can load Agent Skills (`SKILL.md`) |
| Sigma Installer | Node.js 22 or newer |
| SigmaReview | Read access to the target repo · GitHub tooling to push a branch or fork and open a PR · execution authority only if you want measured findings |
| SigmaImprove | Read access to the target · GitHub issue access only if tickets go to GitHub |
| SigmaShip | Push rights and GitHub tooling (`gh` or connector) to open, merge, and close; the repository's test commands |
| SigmaBrief | `gh` read access when briefing from issues or PRs · **no** push to the product repo |
| SigmaWrite | Nothing beyond chat; the GUI option needs a writable output folder and a browser or HTML preview (chat fallback when unavailable) |
| SigmaMusk (`cut`) | Read access to the target repository · `laloc` is optional; without it the skill counts lines itself |
| SigmaDebug | A writable folder (Downloads by default); background agents if the host has them, else it ships the plans one after the other |
| SigmaCreateArena | Python 3 (standard library only) and a browser; the server listens on 127.0.0.1 |
| SigmaResearch | Python 3 for the bundled readers · `yt-dlp` for YouTube comments · Claude in Chrome and owner's existing session for X; missing tools become access gaps |
| SigmaLoop | Read access to the repo and its tracker · `gh` is optional · the host you name (Claude Code, Codex, pi or T3 Code) to run the loop |
| SigmaTaste | Read access to the target · a browser or screenshot tool to see a page; without one the plan lists what was not judged |
| SigmaHuman | Nothing beyond chat · Python 3 (standard library) for the optional fact check |
| SigmaTour | Python 3 (standard library) · `git` · a browser for the page · `gh` and Node.js only when it copies first |
| SigmaClimb | Python 3 · a scoring script for your target · for the serving example: SSH, a GPU host account (`vastai`) and a long-run agent host |
| SigmaFreedom | Python 3 (standard library) for `guardrail_lint.py` |
| SigmaFinanceMan | Python 3.10 or newer with `openpyxl` and `python-pptx` · LibreOffice is optional (`audit`, `render`) · network access to SEC, Yahoo and FRED |
| SigmaDeepLook | Python 3.10 or newer; optional ffmpeg, LibreOffice, poppler, tesseract and Python packages · `look.py doctor` lists them; missing tools become Not-looked-at rows |

Skills use the shell native to the machine that runs the agent (PowerShell on Windows, POSIX shell elsewhere). They do not assume WSL.

SigmaShip and SigmaBrief work best with optional companion skills from [mattpocock/skills](https://github.com/mattpocock/skills): `/to-spec` and `/to-tickets` turn an idea into a ticket with acceptance criteria, `/grilling` settles open decisions, and `/tdd` guides test-first work. Without them, the skills fall back to plain steps.

---

## Ponytail per project

[Ponytail](https://github.com/DietrichGebert/ponytail) (MIT) tells coding agents to write the smallest code that works. Turn it on for one project only; other projects on the machine stay as they are:

```bash
npx @djordje-stojanovic/sigmaskills ponytail --project .           # on
npx @djordje-stojanovic/sigmaskills ponytail --check --project .   # on or off per agent
npx @djordje-stojanovic/sigmaskills ponytail --remove --project .  # off
```

It writes three project files, pinned to Ponytail v5.3.3: `.claude/settings.json` (Claude Code), `.codex/config.toml` (Codex) and `.pi/settings.json` (Pi), and adds `.pi/git/` to `.gitignore`. Each agent loads them only in a folder you trust. T3 Code threads read the same files. Codex also needs `codex plugin marketplace add DietrichGebert/ponytail` once per machine.

---

## Links

- [Installer guide](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/docs/installer.md): every command, flag, and install method
- [Maintainer guide](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/docs/maintainers.md): tests, releases, and registry automation
- [Skill evals](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/docs/evals.md): how each skill's output is checked, and the latest results
- [CHANGELOG.md](CHANGELOG.md): what changed in each Release
- [AGENTS.md](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/AGENTS.md): the working rules for agents in this repository
- [CONTEXT.md](https://github.com/Djordje-Stojanovic/Sigmaskills/blob/main/CONTEXT.md): the words this project uses, such as Skill Pack and Agent Host
- [Decision records](https://github.com/Djordje-Stojanovic/Sigmaskills/tree/main/docs/adr): why the installer works the way it does
- [New issue](https://github.com/Djordje-Stojanovic/Sigmaskills/issues/new/choose): bug, feature, improvement, or docs

## License

[MIT](LICENSE) © Djordje Stojanovic
