---
name: sigmatour
description: 'Use when asked for sigmatour or sigmafork, to walk through a codebase, or to copy it first, isolated, then learn it. Visual tour in one HTML page. Do not use to review it or plain git clone.'
---

# SigmaTour

Give the reader a guided tour of one repository in a single HTML page. Two starts, one page: tour the repo where it is, or copy it first — isolated from the original — and tour the copy. The bar: after the tour, the reader can say what the repo does, draw its parts, follow a request through it, run it, and knows what the README leaves out. In copy mode he can also change the copy. The original is read, never changed.

## Operating contract

- **The original stays untouched.** Read the source; never write to it. In copy mode, record its state before the copy (`git status --porcelain` and the HEAD commit, or the newest file time for a folder without git), check it again at the end and report both. A tour in place writes nothing into the toured repo: the page and its pictures go where the user says; by default `./<repo name>-tour.html` in the current folder and pictures in `./<repo name>-tour/`. A GitHub repo is cloned to a temporary folder first (`git clone --depth 200 <url> <tmp>`).
- **Isolation is a gate (copy mode).** The copy is done only when `scripts/sigmatour.py verify` prints `ISOLATED`: no absolute path, link (symlink or junction) or git remote in the copy reaches the original. Paths to other places (shared caches, output folders, sibling repos) are listed for review and remapped when the grill says so.
- **Owner-only inputs.** Logins, passwords, API keys and tokens: the owner types them himself, in his browser, a terminal prompt (`gh auth login`, `npm login`) or the file the copy reads (`.env`). You say exactly where each one goes and why. You never type, print, copy or commit a secret value; name a key by its variable name, and you may point the copy at an existing keys file by path.
- **No overwrite.** The helper refuses a destination folder that is not empty. Pick a new folder, or ask.
- **Real runs only.** Every command and output in the tour ran during this session, on this machine — in copy mode, in the copy. When one cannot run here (a GPU, a paid key, a service), say why and show the repo's own committed output instead. Never hello world.
- **Numbers from the helper.** Sizes, history, entry points and the README check come from `scripts/sigmatour.py`, never typed by hand.
- **Shell native to the machine:** PowerShell on Windows, POSIX shell elsewhere. Close any server you start.

The helper is one standard-library Python file. `python scripts/sigmatour.py selftest` checks it on this machine.

## 1. Measure, then ask once

Run `python scripts/sigmatour.py scan <repo>`. It prints the size, the history, the entry points, the README check and a suggested length from the code size (15, 30, 45 or 60 minutes).

The user's words pick the mode. **Tour in place** (explain, walk through, learn): ask one short round, each question with a recommended answer the user accepts by saying yes. Skip any the user already answered; log each one you took for him as `Ruling:`.

1. **Length:** the suggested minutes; the user's wish wins.
2. **Reader:** a new contributor, a user of the tool, or a decision maker. This sets how deep the trace and the deep dives go.
3. **Focus:** the whole repo, or one part or flow (name the candidates from the scan).
4. **Runs:** may the tour install dependencies and run the examples here? Recommend yes when the repo runs on this machine without paid keys.

**Copy mode** (copy, fork, duplicate, a destination folder): ask the 8 grill questions in **one** numbered round instead — [questions.md](references/questions.md), each with a recommended answer based on what the scan and a few minutes in the source showed (the README, the top-level folders, the package or build files, config that names keys, agent instructions, its size, hardcoded absolute paths from `python scripts/sigmatour.py paths <source> --source <source>`, which reads without writing). Use `/grilling`'s round format when it is installed. If the owner says "use the recommended answers", do not ask; log each answer you took for him as `Ruling:`. Write the answers to `grill.md` in your scratch folder; it moves into the copy in step 2.

## 2. Copy it first (copy mode only)

Follow [copy.md](references/copy.md) for the source kind (GitHub fork, GitHub clone, local git repo, local folder). In short:

1. **Make the copy** at the destination from the grill. GitHub: `gh repo fork` or `git clone`. Local: `python scripts/sigmatour.py copy <source> <dest> --exclude <pattern>...`, which skips installed dependencies and caches, remakes links that point inside the source so they point inside the copy, and copies links that point outside as real files.
2. **Cut every path back to the original:** `paths`, then `fix` (rewrites every spelling of the source path to the same spelling of the copy), then `--map OLD=NEW` for each outside folder the grill said the copy must own (its output folder, its cache, its database), then fix git remotes, then `verify` until it prints `ISOLATED`.
3. **Owner-only inputs:** list each login and key the copy needs, with the exact place it goes. Wait while the owner types them. Then check that the copy sees them without printing the values (a status command, a dry run, a "key found" line).
4. **Install and run:** install the copy's dependencies with its own lock file, then run its own check or one real example. A copy that does not run is not done; fix it or report the exact blocker.
5. **Install the skill bundle** from the grill: [bundles.md](references/bundles.md). Project scope, inside the copy.
6. **Move** `grill.md` and `study.md` (step 3) into `<dest>/.sigmatour/`, next to the helper's `copy.json` and `paths.json` logs.

From here the tour target is the copy, and the page goes inside it: `<dest>/<repo name>-tour.html`, unless the owner says otherwise — the name ends in `-tour.html`, so the scan never counts the page itself.

## 3. Study

Read in this order and keep notes (in copy mode, `study.md`): the README and docs; the entry points from the scan; the main flows from each entry point to its output (what calls what); the folders that matter; the examples, demos, tests and fixtures (in copy mode, the real example projects inside it); what the repo reads from outside (keys, services, files); the issues and changelog for known problems.

When `/sigmaresearch` is installed and the repo is public, read how people use it and what they trip over: 5-10 sources for a tour in place, the grill's depth in copy mode (for example 100). Without `/sigmaresearch`, read the same kinds of sources with your own web tools and say so. In copy mode the research also feeds the "Top 3 resources" of step 6.

Then run the repo: install with its own lock file, run its own check or test, and run 2-3 real examples end to end. Save screenshots or output files for the page.

Read the README against the repo. The scan finds the mechanical part: README commands with no script or file behind them, paths that do not exist, environment variables the code reads that no doc names, package scripts and top folders the README never mentions, TODO and FIXME notes. Add what only reading finds: features and flags the README never mentions, promises the code does not keep, parts that look dead, limits the README hides. Each with its proof (a file, a line, a command and its output).

## 4. Build the page

`python scripts/sigmatour.py build <repo> --out <page> --minutes <N>` makes the page from [the template](assets/tour-template.html) and writes the scan into its data block. The page draws the numbers band, the folder explorer, the history band, the README check and the entry points from it. Fill every `FILL` by [tour.md](references/tour.md): the transit map, how it works, the trace of one request, the examples with their real output, the hidden and missing list, the deep dives (their count sets the length), where things are, and three hands-on tasks. In copy mode, [tour.md](references/tour.md) also says where the copy facts go: why the copy exists, the keys by name, the bundle, the `verify` result.

Write in the `/sigmawrite` voice: clear technical English a sharp outsider follows on the first read (the ASD-STE100 spirit). One lead line per stop, three sentences a paragraph at most, a tap-to-explain meaning for every term a newcomer would stop at. When `/sigmahuman` is installed, give the text one pass with it.

## 5. Check

Run `python scripts/sigmatour.py check <page>` and fix its list. Open the page in a browser at desktop and phone width (390 px), look at screenshots, click the map, the explorer, the trace (Back, Next, a file in the trail), a quiz and a term, and read the console: no errors. Fix and look again. In copy mode, run `verify` once more with the page in place.

## 6. Questions

Give the user the page path and invite questions. Answer each one short, with the real file or command, and add it to the page's "Your questions" section, with the diagram or snippet that makes it stick. In copy mode, fill **Top 3 resources** there too: the three videos, courses or articles from the research that teach the most per minute, each with its length and why it is in the top 3. Finish with: "Is there anything else you want to see?" Repeat while he has questions.

## Final response

1. The page path, its length in minutes and its stops.
2. What ran for real, and what could not run here and why.
3. The three most surprising things the README does not say.
4. That the page rendered with no console errors at both widths.
5. "Is there anything else you want to see?"

Copy mode also reports, before item 5: the copy path, how it was made (fork, clone or copy), and the `verify` result; the original's state before and after (unchanged, with the evidence); the skill bundle installed, and where; owner steps still open (keys not typed yet, logins), each with where it goes.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
