# The tour page

One self-contained HTML file. It teaches one reader how a repository works, in the minutes the user chose. Most of it is pictures the reader can tap; the words around them are short.

## Length

The stops carry their minutes in `data-min`; the page adds them up in the hero, and `check` warns when the sum is more than 25 % away from the target.

| Target | Stops |
|---|---|
| 15 min | the base stops, at most one deep dive |
| 30 min | the base stops, two or three deep dives, a longer trace (6-8 steps) |
| 45 min | four or five deep dives, a second trace for the second main flow |
| 60 min | five to eight deep dives, two traces, every example the repo ships that runs here |

A deep dive covers one part that matters: what it does, the file to open first, the lines that do the work, how it talks to the parts around it, and what breaks it.

## The stops

| Stop | What goes in |
|---|---|
| Hero | The repo as a transit map (inline SVG): one coloured line per main flow (2-5), one stop per folder, tool or step that matters, real names, stops on a 40 px grid, lines at 45 or 90 degrees. Each stop is `<g class="stop" data-stop="ID">` with a note in `#map-notes` (title, what, path, open, run) |
| What it does | One line: the job and the result. Who uses it, which problem it solves, what it does not do |
| The repo in numbers | One line on where the weight is and how alive the repo is. The explorer and the history band are drawn; give the main folders a note in `#folder-notes` |
| How it works | One card per map line, then the architecture figure: 4-9 boxes with real names and folders, an arrow per call or data flow, the main path as `.wire.hot` |
| One request, end to end | The trace: one real command or request from entry to result, one `li.step` per hop (4-10): title, `file:line` in `.where`, one to three sentences, the few real lines that do it. The page makes it a stepper with a file trail |
| Examples, run end to end | Two or three real examples, each run during the tour: the command, the real output, a screenshot when it makes one |
| What the README says | The verdict tiles and the check table are drawn. Under them, the hidden and missing list: one item per finding, tagged Hidden or Missing, with its proof |
| Deep dives | One section per part, by the length table |
| Where things are | The entry points table is drawn; add the 8-12 rows a reader needs most (want, look in, run) |
| Try it yourself | Three hands-on tasks, easy to harder: what to do, the files, how you see it worked |
| Your questions | Filled after the question round |

Each stop ends with a check-yourself quiz (`.quiz`, `data-answer` = the number of the right option, 1-based) when the stop teaches a fact worth testing.

## Hidden and missing

The scan marks what a machine can prove. Reading adds the rest. Good findings:

- **Hidden:** an environment variable or flag that changes behaviour; a command or script the README never mentions; a folder that does real work; a limit (a size cap, a timeout, a rate limit) found only in the code; a second way to run it.
- **Missing:** a README command whose script is gone; a feature the README promises that the code does not have; a doc link to a file that does not exist; tests or CI the README claims that are not there; setup steps the README skips (a key, a service, a system package).
- **Dead:** a folder or file nothing imports or calls (prove it with a search).

Write each as a fact with its proof, not as a judgement. The tour is not a review: name what is there and what is not, and leave the fixes to the owner.

## Pictures

At least 6 figures (`check` counts them): the map, the numbers band, the history band, the architecture, the trace, the README check, plus screenshots of real runs. Save screenshots next to the page (`<repo name>-tour/`) and link them relatively. For a spatial repo (a game, a 3D tool) a small Three.js scene may replace the map: cdnjs, an exact version, a static SVG fallback, reduced motion respected.

**Look:** the template wears a near-black zinc canvas, one emerald accent, hairlines and Inter. When the repo has its own `DESIGN.md`, brand tokens or a theme file, map them onto the template's `:root` tokens and change nothing else. `--l1` to `--l5` are diagram colours, never buttons or links.

## Writing

- **Lead with the point.** Each stop opens with one line (`.oneline`). A reader who reads only those lines still gets the tour.
- **Three sentences a paragraph at most**, 70 words at most. One idea per sentence. Active voice: who does what.
- **Commands go in code blocks**, not in running text. More than three inline code chips in one paragraph is a defect.
- **Every word a newcomer would stop at gets a meaning** where it first appears: `<span class="term" data-def="One line that says what it is">router</span>`.
- **Real names, real numbers.** Every claim points at a file, a line or a command.
- No staging lines, no closers that repeat the paragraph, no all-caps labels you add yourself.
