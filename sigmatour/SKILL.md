---
name: sigmatour
description: 'A visual 15-60 minute tour of any repository, end to end, in one HTML page: its job, how it works, a clickable map and architecture diagram, one real request traced file by file, examples run for real, the repo in numbers, and the README held against the repo (hidden settings, missing files, dead commands). Length by the user''s wish and the repo''s size. Plain technical English. Use when the user wants to understand, learn, explore or get a walkthrough or tour of a repo or codebase. Do not use to copy or fork the repo (SigmaFork), to review it for bugs (SigmaReview), or to suggest improvements (SigmaImprove).'
---

# SigmaTour

Give the reader a guided tour of one repository in a single HTML page. The bar: after the tour, the reader can say what the repo does, draw its parts, follow a request through it, run it, and knows what the README leaves out. The repo is read, never changed.

## Operating contract

- **Read only.** Never write into the toured repo. The page and its pictures go where the user says; by default `./<repo name>-tour.html` in the current folder and pictures in `./<repo name>-tour/`. A GitHub repo is cloned to a temporary folder first (`git clone --depth 200 <url> <tmp>`).
- **Real runs only.** Every command and output in the tour ran during this session, on this machine. When one cannot run here (a GPU, a paid key, a service), say why and show the repo's own committed output instead. Never hello world.
- **Numbers from the helper.** Sizes, history, entry points and the README check come from `scripts/sigmatour.py`, never typed by hand.
- **Secrets stay out.** Name a key or login by its variable name; never print, copy or quote a value.
- **Shell native to the machine:** PowerShell on Windows, POSIX shell elsewhere. Close any server you start.

The helper is one standard-library Python file. `python scripts/sigmatour.py selftest` checks it on this machine.

## 1. Measure, then ask once

Run `python scripts/sigmatour.py scan <repo>`. It prints the size, the history, the entry points, the README check and a suggested length from the code size (15, 30, 45 or 60 minutes).

Then ask one short round, each question with a recommended answer the user accepts by saying yes. Skip any the user already answered; log each one you took for him as `Ruling:`.

1. **Length:** the suggested minutes; the user's wish wins.
2. **Reader:** a new contributor, a user of the tool, or a decision maker. This sets how deep the trace and the deep dives go.
3. **Focus:** the whole repo, or one part or flow (name the candidates from the scan).
4. **Runs:** may the tour install dependencies and run the examples here? Recommend yes when the repo runs on this machine without paid keys.

## 2. Study

Read in this order and keep notes: the README and docs; the entry points from the scan; the main flows from each entry point to its output (what calls what); the folders that matter; the examples, demos, tests and fixtures; what the repo reads from outside (keys, services, files); the issues and changelog for known problems. When `/sigmaresearch` is installed and the repo is public, read how people use it and what they trip over (5-10 sources unless the user asks for more).

Then run the repo: install with its own lock file, run its own check or test, and run 2-3 real examples end to end. Save screenshots or output files for the page.

Read the README against the repo. The scan finds the mechanical part: README commands with no script or file behind them, paths that do not exist, environment variables the code reads that no doc names, package scripts and top folders the README never mentions, TODO and FIXME notes. Add what only reading finds: features and flags the README never mentions, promises the code does not keep, parts that look dead, limits the README hides. Each with its proof (a file, a line, a command and its output).

## 3. Build the page

`python scripts/sigmatour.py build <repo> --out <page> --minutes <N>` makes the page from [the template](assets/tour-template.html) and writes the scan into its data block. The page draws the numbers band, the folder explorer, the history band, the README check and the entry points from it. Fill every `FILL` by [tour.md](references/tour.md): the transit map, how it works, the trace of one request, the examples with their real output, the hidden and missing list, the deep dives (their count sets the length), where things are, and three hands-on tasks.

Write in the `/sigmawrite` voice: clear technical English a sharp outsider follows on the first read (the ASD-STE100 spirit). One lead line per stop, three sentences a paragraph at most, a tap-to-explain meaning for every term a newcomer would stop at (the wait-what check). When `/sigmahuman` is installed, give the text one pass with it.

## 4. Check

Run `python scripts/sigmatour.py check <page>` and fix its list. Open the page in a browser at desktop and phone width (390 px), look at screenshots, click the map, the explorer, the trace (Back, Next, a file in the trail), a quiz and a term, and read the console: no errors. Fix and look again.

## 5. Questions

Give the user the page path and invite questions. Answer each one short, with the real file or command, and add it to the page's "Your questions" section. Finish with: "Is there anything else you want to see?"

## Final response

1. The page path, its length in minutes and its stops.
2. What ran for real, and what could not run here and why.
3. The three most surprising things the README does not say.
4. That the page rendered with no console errors at both widths.
5. "Is there anything else you want to see?"

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
