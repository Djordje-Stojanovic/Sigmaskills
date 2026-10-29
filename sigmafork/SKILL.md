---
name: sigmafork
description: Use when asked for sigmafork or to fork or copy a project and learn it. Copy a repo or folder, isolated from the original, then onboard the owner with an HTML course. Do not use for a plain git clone.
---

# SigmaFork

Take any repository, from GitHub or from a folder on this machine, and give the owner his own working copy plus a short course that teaches it. Five steps: grill, study, copy, onboarding guide, questions. The bar: after 15 minutes with the guide, the owner can run the copy, change it, and knows where everything is. The original is never touched.

## Operating contract

- **The original stays untouched.** Read the source; never write to it. Before the copy, record its state (`git status --porcelain` and the HEAD commit, or the newest file time for a folder without git). Check it again at the end and report both.
- **Isolation is a gate.** The copy is done only when `scripts/sigmafork.py verify` prints `ISOLATED`: no absolute path, link (symlink or junction) or git remote in the copy reaches the original. Paths to other places (shared caches, output folders, sibling repos) are listed for review and remapped when the grill says so.
- **Owner-only inputs.** Logins, passwords, API keys and tokens: the owner types them himself, in his browser, a terminal prompt (`gh auth login`, `npm login`) or the file the copy reads (`.env`). You say exactly where each one goes and why. You never type, print, copy or commit a secret value; you may point the copy at an existing keys file by path.
- **No overwrite.** The helper refuses a destination folder that is not empty. Pick a new folder, or ask.
- **Real examples only.** The course uses projects, commands and output from this repo, never hello world. Every command in it ran in the copy, and the course shows its real result.
- **Shell native to the machine:** PowerShell on Windows, POSIX shell elsewhere. Close any server you start before you stop.

The helper is one standard-library Python file. Run `python scripts/sigmafork.py selftest` once if you doubt it works on this machine.

## 1. Look, then grill

Spend a few minutes on the source first, so every recommendation is real: the README, the top-level folders, the package or build files, `.env.example` or other config that names keys, any agent instructions (`AGENTS.md`, `CLAUDE.md`), its size, and absolute paths it hardcodes (`python scripts/sigmafork.py scan <source> --source <source>` reads without writing and shows them).

Then ask the 8 questions in **one** numbered round, each with a recommended answer the owner accepts by saying yes. Use `/grilling`'s round format when it is installed; otherwise the same numbered layout by hand. The questions, their options and how to pick each recommendation: [questions.md](references/questions.md). If the owner already answered some, or says "use the recommended answers", do not ask those again; log each answer you took for him as `Ruling:`. Ask a second round only when an answer opens a new decision.

Write the answers to `grill.md` (in your scratch folder now; it moves into the copy's `.sigmafork/` folder in step 3).

## 2. Study

Know the source well enough to teach it. Read in this order and keep notes in `study.md`: what it is for and who uses it; how to install and run it; the main flows (what calls what, from the entry point to the output); the folders that matter; the real example projects inside it (demos, examples, fixtures, its own past work); its tests and checks; what it reads from outside (keys, services, shared folders); known pitfalls (issues, changelog, FAQ).

Then run `/sigmaresearch` at the depth from the grill (for example 100 sources): how real people use this project, the best tutorials and talks, the common problems and their fixes, and the top 3 resources for learning it fast. Without `/sigmaresearch`, read the same kinds of sources with your own web tools and say so. The research feeds the course and the "top 3 resources" of part 2.

## 3. Fork or copy, end to end

Follow [copy.md](references/copy.md) for the source kind (GitHub fork, GitHub clone, local git repo, local folder). In short:

1. **Make the copy** at the destination from the grill. GitHub: `gh repo fork` or `git clone`. Local: `python scripts/sigmafork.py copy <source> <dest> --exclude <pattern>...`, which skips installed dependencies and caches, remakes links that point inside the source so they point inside the copy, and copies links that point outside as real files.
2. **Cut every path back to the original:** `scan`, then `fix` (rewrites every spelling of the source path to the same spelling of the copy), then `--map OLD=NEW` for each outside folder the grill said the copy must own (its output folder, its cache, its database), then fix git remotes, then `verify` until it prints `ISOLATED`.
3. **Owner-only inputs:** list each login and key the copy needs (from the study), with the exact place it goes. Wait while the owner types them. Then check that the copy sees them without printing the values (a status command, a dry run, a "key found" line).
4. **Install and run:** install the copy's dependencies with its own lock file, then run its own check or one real example. A copy that does not run is not done; fix it or report the exact blocker.
5. **Install the skill bundle** from the grill: [bundles.md](references/bundles.md). Project scope, inside the copy.
6. **Move** `grill.md` and `study.md` into `<dest>/.sigmafork/`, next to the helper's `copy.json` and `paths.json` logs.

## 4. Onboarding guide

Write `ONBOARDING.html` at the root of the copy: a 10-15 minute mini course in one self-contained page, mostly pictures he can tap. `python scripts/sigmafork.py guide <dest> --source <source>` makes it from [assets/guide-template.html](assets/guide-template.html) and writes the repo numbers into it (files, folders, code lines without blanks, comments and scaffolding, languages, the folder tree, the copy facts); the page draws the numbers band, the folder explorer and the copy-and-original figure from them. Then fill it by [guide.md](references/guide.md): the clickable transit map, the use case as a story of real frames, the map line by line, the real example projects, the change flow, the first three tasks, the cheat sheet, and the empty part 2. Words in the `/sigmawrite` voice: one lead line per stop, three sentences a paragraph at most, a tap-to-explain meaning for every term. When the copy has its own `DESIGN.md` or brand tokens, the guide wears them.

Then run `python scripts/sigmafork.py guide <dest> --check` and fix its list, open the page in a browser at desktop and phone width, look at it (a screenshot), click the map, the explorer and a quiz, check the console for errors, and fix what is broken. Every `FILL` marker from the template must be gone.

## 5. Questions, then part 2

Show the owner the guide path and invite his questions. Answer each one in chat, short, with the real file or command. Then add them to the guide as **Part 2**: one block per question, the answer, and the file, command or diagram that makes it stick. Also fill **Top 3 resources**: the three videos, courses or articles from the research that teach the most per minute, each with its length and why it is in the top 3.

Finish with one question: "Is there anything else you need?" Repeat this step while he has questions.

## Final response

1. The copy path, how it was made (fork, clone or copy), and the `verify` result.
2. The original's state before and after (unchanged, with the evidence).
3. The skill bundle installed, and where.
4. Owner steps still open (keys not typed yet, logins), each with where it goes.
5. The guide path, and that it rendered with no console errors.
6. "Is there anything else you need?"

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
