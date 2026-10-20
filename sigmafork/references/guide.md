# The onboarding guide

One file, `ONBOARDING.html`, at the root of the copy. A mini course of 10-15 minutes (the grill's Q8 sets the length and the mix). It teaches one person, the owner, to run, change and find his way around this repo. It is not a README with colours: most of it is pictures he can tap, and the words around them are short.

## Make it

1. `python scripts/sigmafork.py guide <copy> --source <original>` makes `ONBOARDING.html` from [the template](../assets/guide-template.html) and writes the repo data into it: files, folders, code lines (no blank lines, no comment lines), doc lines, languages, the biggest code files, the folder tree, what was left out (installed packages, build output, caches, venvs, generated files), and the copy facts from `copy.json`, `paths.json` and `verify`. The page draws the numbers band, the folder explorer and the copy-and-original figure from that data. Never type these numbers by hand. Run `guide` again after any change to the copy; it only replaces the data block.
2. Replace every `FILL` (text and comments). Keep the stops unless the grill asks for something else: a stop that does not fit this repo goes, a stop it needs comes in.
3. `python scripts/sigmafork.py guide <copy> --check` lists what is still wrong: `FILL` left or no data (blocking), then fixes (long paragraphs, too many inline code chips, terms without a meaning, fewer than 6 figures). Fix the list.

**Look:** the template wears the Storge-Black-Green look (`DESIGN.md` of this skill pack): near-black zinc, a green glow at the top right, one emerald accent, hairlines, Inter. When the copy has its own `DESIGN.md`, brand tokens or a theme file, map its colours and font onto the template's `:root` tokens and change nothing else. `--l1` to `--l5` are diagram colours (map lines, the language bar), never buttons or links.

## The stops

| Stop | Minutes | What goes in |
|---|---|---|
| What it is | 1 | One line: the job and the result. Then who uses it and why this copy exists (Q1, Q2) |
| One job, start to finish | 2 | The use case three ways: a two-sentence story, 4-5 frames (picture, title, sentence, command), the real result as the last frame |
| The repo in numbers | 2 | One line on where the weight is; the folder explorer (drawn); a one-line note per main folder in `#folder-notes` |
| The map | 1 | One card per map line; the stops above are tappable and show their notes from `#map-notes` |
| Run it | 2 | The commands that ran in the copy, each with its real output |
| Real example projects | 3 | Two or three real projects from the repo, with pictures when they make one |
| How a change flows | 1 | The flow strip: the file you edit → each step → what you see |
| Your first three tasks | 1 to read | Hands-on, easy to harder: what to do, the files, how you see it worked (tick boxes) |
| Where things are | 1 | The 8-12 rows he needs most, plus the installed skill bundle (the table has a filter) |
| Keys and access | 1 | The copy-and-original figure (drawn), then each login and key by name (never a value), where it goes, set or not |
| Part 2 | — | Empty until step 5 |

## The pictures

The course needs at least 6 figures; `--check` counts them. Two are drawn from data (numbers band, explorer, copy-and-original figure). The rest the agent makes:

- **The map (the hero).** The repo as a transit map in inline SVG: one coloured line per main flow (2-5 lines), one stop per folder, tool or step that matters, labelled with its real name. Where flows share a step, the lines meet at one bigger stop: the hub. Stops sit on a 40 px grid, lines bend at 45 or 90 degrees, labels never overlap a line. Each stop is `<g class="stop" data-stop="ID">` with a note in `#map-notes`: title, one or two sentences, its folder (the page adds the folder's numbers), the file to open first, the command. Every stop is a real path or command in the copy. For a spatial repo (a game, a 3D tool) and when Q8 asks, the map may be a small Three.js scene instead (cdnjs, exact version, a static SVG fallback, reduced motion respected).
- **The story frames.** Real pictures first: a screenshot of the copy running, an output frame, a rendered result, saved next to the guide (for example `onboarding/`). An inline icon only where no picture exists.
- **The flow strip and the line cards.** Real names: the file, the command, the result.
- **Example pictures.** When an example makes something visible, show it in `.shots`.

## Real example projects

Pick from what the study found: demos, examples, fixtures, templates, the repo's own past work. For each: its name and path, what it shows about the repo, the one file to open first, the command that builds or runs it, and what really came out (text output, a file path, a screenshot saved next to the guide). Run each one in the copy before you write it up; if one cannot run here (a GPU, a paid key), say why and show its committed output instead. Never invent a hello-world.

## Writing

Write in the `/sigmawrite` voice: clear technical English a sharp outsider follows on the first read. When `/sigmahuman` is installed, give the finished text one pass with it (Docs lane).

- **Lead with the point.** Each stop opens with one line (`.oneline`) that says what this stop teaches. A reader who reads only those lines still gets the course.
- **Three sentences a paragraph at most**, 70 words at most. One idea per sentence. Active voice: who does what.
- **Commands go in code blocks**, not in the middle of a sentence. In running text, name things plainly ("the film kit") and keep inline code for the one thing to type or open. More than three code chips in one paragraph is a defect.
- **Every word a newcomer would stop at gets a meaning** where it first appears: `<span class="term" data-def="One line that says what it is">Board 3</span>`. Tap or hover shows it. This is the wait-what check: if a stranger would ask "wait, what is that?", define it.
- **Real names, real numbers.** Every claim points at a file or a command. Name the original by its name ("the original repo"), not by its absolute path: `verify` reads the guide too.
- **Each stop ends with a check-yourself quiz** (`.quiz`, `data-answer` = the number of the right option, 1-based) whose answer is in that stop, with a one-line reason.
- No staging lines ("Here's the thing"), no closers that repeat the paragraph, no all-caps labels you add yourself, no single accented word in a headline.

## Check it renders

Open the file in a browser (a browser tool, or a headless screenshot) at desktop width and at phone width (390 px). Look at the screenshots: the map is legible, nothing overflows sideways, the code blocks scroll inside themselves. Read the console: no errors. Click a map stop, a folder in the explorer, a quiz answer, a term, one "Mark as done" and one "Copy". Fix and look again.

## Part 2 (step 5)

For each of the owner's questions, add one block to the Part 2 section: the question in his words, the answer with the real file or command, and a diagram or snippet when it makes the answer stick. Replace the empty line. When an answer shows a hole in part 1 (a missing stop, a wrong row), fix part 1 too.

**Top 3 resources:** from the research, the three that teach the most per minute: an official tutorial, a talk or video walkthrough, a write-up by a heavy user. Each: title, link, length (minutes), and why it beats the others. Prefer recent ones that match the copy's version.
