# Course repo setup

What steps 2, 5 and 6 write. Write only what the scale needs; the S column is the floor.

## Layout

```
AGENTS.md                 steering: rules, invariants, crew, check command (all scales)
CLAUDE.md                 one line: "Read AGENTS.md." (when Claude Code runs it)
docs/course/spec.md       the signed spec (all)
docs/course/done.md       the done list and the completion ladder (all)
docs/course/user-words.md the user's words, verbatim (all)
docs/course/doctrine.md   learner metrics and what each retro teaches (M and up)
docs/course/map.md        open decisions with defaults (L and up)
docs/learnings.md         Problem, Root cause, Fix, Rule per entry (M and up)
loop/queue.tsv            the job queue (all)
loop/run.md               the run file the loop re-reads every turn (all)
loop/STEER.md             the user's orders during the run (L and up)
checks/check.py           the one check command (all)
content/ media/ research/ lab/   the course itself, filled by the loop
books/                    git-ignored; the user drops bought books here (L and up)
```

## spec.md

```
OBJECTIVE (one sentence + the number):
SCALE: S | M | L | XL        LEARNER:          PLACEMENT:
GOAL:                        BASE RATE (source or assumption):
BAR (named comparison):      OUT OF SCOPE:
HOURS: core / history / life / per week       BUILD FIRST or PILOT:
VARIETY: shapes and ranges, tasks, levels, sameness rules (variety.md, adapted)
CASE FILES: count + axes     PERSONAS: teachers, guests, source floor, runtime
MEDIA: kinds, counts, video share, tools and machines, long-lecture bar
LAB TOOLS:                   HISTORY / LIFE:   SKILL MAP:
SOURCES: floors, kinds, corpora, book list, data
EVALUATOR: scripts + fresh reviewer one model up (+ user review packs)
CREW: slots, models, efforts, roles; jobs dynamic (a free slot takes the next unblocked row)      HOST: the loop host and run mode
STACK and LOOK:              SECRETS:
INVARIANTS: realism (source or assumption), compute in code, base rate beside every goal
SIGN-OFF: the user said "yes, exactly" [ ]
```

Each line records its source and date ("user 2026-…" or "default, logged"). When a newer user word replaces a line, mark the old one SUPERSEDED and keep its text.

## done.md

- One line per requirement: `R-001 <what> [script: <check> | review | user step]`. Script beats review.
- Group by area: lessons, variety, media, case files, personas, lab tools, research, books, polish.
- At the top: open decisions and conflicts, each with its default.
- The completion ladder at the bottom: done means `checks/check.py` prints `DONE` (every line passes, gated hours at target, every area at its count, the final review PASS). Then polish, then maintenance only if the user wants it.

## queue.tsv

Columns: `id  status  area  job  blocked_by  paths  done_when  notes`. Status is `pending`, `running`, `done` or `held`.

- Lesson rows are batches (S: 1–3 lessons; L: 4–8).
- Media, personas, case files, lab tools, research and books each get rows from the start, so every area moves in the first round.
- A check row is queued only beside the content it checks (see `lessons.md`, rule 1).

## checks/check.py

One script, no AI. It prints one line per area (`lessons 12/40 gated, 9.5/30 h`) and a last line: `DONE` or `OPEN <n>`. It reads front matter and the queue; it never trusts a typed number. Grow it with the course; write each new check test-first (Matt Pocock `tdd`, or a planted-defect test).

## AGENTS.md

Short. It holds:
- The user's words decide; the newest wins. The only confirm: deleting the repo or publishing a secret.
- The invariants from the spec.
- The check command, and "count what exists before saying what is left".
- The crew and roles (model names in one line only, so a retired model is one edit).
- Every brief names the task, the files, the done line, a scratch folder and the skills to read; the agent reads each skill itself; data files go by path.
- Every writing agent gets its own git worktree.
- Retro after every task into `docs/learnings.md`.

## loop/run.md

The run file is the build method the loop follows every turn. Write it from `build.md`, adapted to the spec: the lesson pipeline, the persona rules, the media routes, the review rule, the order for free slots, the retro step, and a link to `lessons.md`. SigmaLoop's loop file points to it; keep the two from saying the same thing twice.

Order for a free slot (default): (1) finish drafted lessons through review, since they turn into gated hours; (2) new lesson batches; (3) media, personas and case files in step with the lessons that need them; (4) fixes and checks.

## loop/STEER.md (L and XL)

The user's orders during the run, one dated line each. The loop reads it every turn, acts on a new line in the same turn and writes "done <date>" under it. `STOP` on its own line: finish the running step, start nothing new. STEER outranks the run file and the queue.

## doctrine.md

| # | Metric | Question |
|---|---|---|
| M1 | Speed to beginner | Hours until the learner does the whole job once, alone? |
| M2 | Speed to professional | Hours until the work matches a professional's, judged blind? |
| M3 | Ceiling | How far can it take someone? (proxies: unseen cases, calibration, reasoning quality) |
| M4 | Retention | Recall at 30, 90 and 365 days |
| M5 | Application | Use on real, new material |
| M6 | Learning per hour | Gain on M1–M5 divided by hours |
| M7 | Adherence | Hours a week sustained |

Then the evidence to research (do not assume it): cognitive apprenticeship, whole-task design (4C/ID), backward design, mastery learning, deliberate practice, desirable difficulties, retrieval, spacing and interleaving, worked examples, productive failure, dual coding. Exemplars: CS50 (lectures, sections, real problem sets, one big final project), 3Blue1Brown (examples before definitions), Nand2Tetris, Math Academy. Each retro adds a principle with its source, or marks it HEURISTIC.
