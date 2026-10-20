# The onboarding guide

One file, `ONBOARDING.html`, at the root of the copy. A mini course of 10-15 minutes (the grill's Q8 sets the length and the mix). It teaches one person, the owner, to run, change and find his way around this repo. It is not a README with colours.

## Start from the template

Copy [assets/guide-template.html](../assets/guide-template.html) to `<dest>/ONBOARDING.html`. Replace every `FILL` (text and comments) with real content; `FILL` left anywhere is a defect. Keep the structure unless the grill asks for something else: a stop that does not fit this repo goes, a stop it needs comes in. The stops are a real sequence, so the course numbers them and the progress bar counts them.

**Look:** when the copy has a `DESIGN.md`, brand tokens or a theme file, map its colours and font to the template's `:root` tokens (`--paper`, `--surface`, `--ink`, `--mute`, `--rule`, `--accent`, `--font`) and its dark values to the dark block. The template's own look (a transit map in road-sign type) is the default only for a repo with no look of its own.

## The stops

| Stop | Minutes | What goes in |
|---|---|---|
| What it is | 1 | The job, the user, the result, and why this copy exists (Q1, Q2) |
| The map | 2 | The hero map explained line by line |
| Run it | 2 | The commands that ran in the copy, each with its real output |
| Real example projects | 4 | Two or three real projects from the repo (below) |
| How a change flows | 2 | One small diagram: the file you edit → each step → the result you see |
| Your first three tasks | 3 | Hands-on, easy to harder, each with the files to touch and how to see it worked |
| Where things are | 1 | The 8-12 rows he will need most, plus the installed skill bundle |
| Keys and access | 1 | Each login and key by name (never a value), where it goes, set or not; the shared read-only paths; the isolation result |
| Part 2 | — | Empty until step 5 |

## The map (the hero)

Draw the repo as a transit map in inline SVG: one coloured line per main flow (2-5 lines), one stop per folder, tool or step that matters, labelled with its real name. Where flows share a step, the lines meet at one bigger stop: that is the hub, and the course says so. Stops sit on a grid, lines bend at 45 or 90 degrees, labels never overlap a line. The map must be true: every stop is a real path or command in the copy. A repo with one flow gets one line and its branches.

For a spatial repo (a game, a 3D tool, a scene graph) and when Q8 asks for it, the map may be a small Three.js scene instead: load Three.js from cdnjs at an exact version, keep a static SVG fallback, and respect reduced motion.

## Real example projects

Pick from what the study found: demos, examples, fixtures, templates, the repo's own past work. For each: its name and path, what it shows about the repo, the one file to open first, the command that builds or runs it, and what really came out (text output, a file path, a screenshot saved next to the guide). Run each one in the copy before you write it up; if one cannot run here (a GPU, a paid key), say why and show its committed output instead. Never invent a hello-world.

## Writing

Short sentences, real names, active voice. Name the original by its name ("the original repo"), not by its absolute path: `verify` reads the guide too. Explain each term once, where it first appears. Every claim points at a file or a command. The owner learns by doing: each stop ends with a "check yourself" question whose answer is in that stop.

## Check it renders

Open the file in a browser (a browser tool, or a headless screenshot) at desktop width and at phone width (390 px). Look at the screenshot: the map is legible, nothing overflows sideways, the code blocks scroll inside themselves. Read the console: no errors. Click one "Mark as done" and one "Copy". Fix and look again.

## Part 2 (step 5)

For each of the owner's questions, add one block to the Part 2 section: the question in his words, the answer with the real file or command, and a diagram or snippet when it makes the answer stick. Replace the empty line. When an answer shows a hole in part 1 (a missing stop, a wrong row), fix part 1 too.

**Top 3 resources:** from the research, the three that teach the most per minute: an official tutorial, a talk or video walkthrough, a write-up by a heavy user. Each: title, link, length (minutes), and why it beats the others. Prefer recent ones that match the copy's version.
