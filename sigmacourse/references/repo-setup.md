# Course repo setup

What the spec, queue and run steps of SKILL.md step 3 write. Write a file only when its step ran.

## Layout

```
AGENTS.md                 steering: rules, invariants, crew, check command
CLAUDE.md                 one line: "Read AGENTS.md." (when Claude Code runs it)
docs/course/spec.md       the signed spec
docs/course/done.md       the done list and the completion ladder
docs/course/user-words.md the user's words, verbatim
docs/course/doctrine.md   learner metrics and what each retro teaches
docs/course/map.md        open decisions with defaults (when the decision map step ran)
docs/learnings.md         Problem, Root cause, Fix, Rule per entry
loop/queue.tsv            the job queue
loop/run.md               the run file the loop re-reads every turn
loop/STEER.md             the user's orders during the run
checks/check.py           the one check command
content/ media/ research/ lab/   the course itself
docs/books/book-list.md   the one book list (research-and-books.md)
research/books/           one distilled note per book, and the map
books/                    git-ignored; the user drops bought books here
```

## spec.md

```
OBJECTIVE (one sentence):
END STATE: the lines of SKILL.md step 1     MAP: nodes, proofs, minutes, longest chain (script output)
PROCESS: the step table of SKILL.md step 3  LEARNER:          PLACEMENT:
GOAL:                        BASE RATE (source or assumption):
BAR (named comparison):      OUT OF SCOPE:
LEARNER TIME: total, per sitting, sittings a week      BUILD FIRST or PILOT:
VARIETY: shapes, tasks, levels, sameness checks (variety.md, adapted)
CASES:                       PERSONAS:
MEDIA: kinds and the proof each serves, tools and machines
DELIVERY: design file, devices and widths, performance budget, accessibility standard
SOURCES:                     EVALUATOR: scripts + fresh reviewer one model up (+ user review packs)
CREW and HOST:               STACK:            SECRETS:
INVARIANTS: realism (source or assumption), compute in code, base rate beside every goal
SIGN-OFF: the user said yes to the playback (grill.md, Alignment) [ ]   FIRST PART: accepted, plan fixes logged [ ]
```

Each line records its source and date ("user <date>" or "default, logged"). When a newer user word replaces a line, mark the old one SUPERSEDED and keep its text.

## done.md

- One line per requirement the spec states: `R-<n> <what> [script: <check> | review | user step]`. Script beats review. Its length follows the spec.
- Group by area: lessons, variety, media, cases, personas, lab tools, delivery, research, books.
- At the top: open decisions and conflicts, each with its default.
- The completion ladder at the bottom: done means `checks/check.py` prints `DONE` (every line passes, accepted learner time at target, every area at its count, the final review PASS). Then polish, then maintenance only if the user wants it.

## queue.tsv

Columns: `id  status  area  job  blocked_by  paths  done_when  notes`. Status is `pending`, `running`, `done` or `held`.

- Lesson rows are batches (`build.md`).
- Every area the spec names gets rows from the start, so every area moves in the first round.
- A check row is queued only beside the content it checks (`lessons.md`, rule 1).

## checks/check.py

One script, no AI. It prints one line per area (`lessons 12/40 accepted, 9.5/30 h`) and a last line: `DONE` or `OPEN <n>`. It reads front matter and the queue; it never trusts a typed number. Grow it with the course; write each new check test-first.

## AGENTS.md

Short. It holds: the user's words decide and the newest wins; the only confirm (deleting the repo or publishing a secret); the spec's invariants; the check command and "count what exists before saying what is left"; the crew (model names in one line, so a retired model is one edit); the brief rule from `build.md`; a worktree per writing agent; a retro after every task.

## loop/run.md

Written from `build.md`, adapted to the spec, with a link to `lessons.md`. SigmaLoop's loop file points to it; the two never say the same thing twice. Order for a free slot (default): finish drafted lessons through review; new lesson batches; media, personas and cases in step with the lessons that need them; fixes and checks.

## loop/STEER.md

The user's orders during the run, one dated line each. The loop reads it every turn, acts on a new line in the same turn and writes "done <date>" under it. `STOP` on its own line: finish the running step, start nothing new. STEER outranks the run file and the queue.

## doctrine.md

| Metric | Question |
|---|---|
| Speed to first whole task | Learner time until the learner does one end-line task alone |
| Speed to the bar | Learner time until the work meets the named bar, judged blind |
| Ceiling | How far it takes someone on unseen cases |
| Retention | Recall at gaps that fit the course's length |
| Application | Use on real, new material |
| Learning per hour | Gain on the above divided by learner time |
| Adherence | Learner time sustained per week |

Research the evidence; do not assume it: backward design, whole-task design (4C/ID), cognitive apprenticeship, mastery learning, deliberate practice, desirable difficulties, retrieval, spacing and interleaving, worked examples, productive failure, dual coding. Exemplar courses to study, as examples: CS50, 3Blue1Brown, Nand2Tetris, Math Academy. Each retro adds a principle with its source, or marks it HEURISTIC.
