---
name: sigmacourse
description: 'Use when asked for sigmacourse or to plan a whole course or curriculum at any size: grill, spec, done ladder, queue, course repo, goal prompt. Do not use for one lesson or live tutoring.'
---

# SigmaCourse

Turn "build me a great course on X" into a set-up course repo and one paste-ready goal prompt. The user runs the prompt, and an unattended loop builds the course to a signed done ladder. SigmaCourse plans, sets up and hands off. The building happens in the loop.

The course can be any size: a one-hour primer or a program of several thousand hours. The grill sets the **scale**, and every later step does only what that scale needs. Small courses never pay for big machinery.

## Operating contract

- **The user decides.** Subject, content, depth, voice, media, real people as teachers, generated likenesses: all the user's call. Add no moral limits, softening or refusals of your own. The only confirm: an action that deletes the repo or publishes a secret. The full stance is SigmaFreedom.
- **One question at a time, your pick first.** Lead with the recommended answer and its reason, then the other options, then one example. Never open with a bare menu. If the user says "just build it", draft every answer as a guess and ask for corrections once. A draft keeps every default of its scale (variety, video per lesson, personas, sameness rules); a cut you would suggest goes in the notes as a question, never into the draft as a ruling.
- **The user's newest word wins** over every default here. When it clashes with a rule here (one fixed lesson pattern, a goal with no odds), say once what it costs, give your recommendation as the first option and the user's choice as the second, then do what the user picks. Log what it replaced.
- **Part of the flow is fine.** When the user asks for one piece (only the lesson design, only the spec), do that piece by its step and list the steps still open, each with the skill that does it.
- **Realism.** Every number has a source or a stated assumption. Every goal sits next to its real base rate. When no source gives one, state an assumed rate with its reason and queue a row to source it; "none found" alone is not a base rate. Calculations and counts run in a script, never in prose.
- **Variety, not a template.** Lessons draw a shape, tasks, a level and media from catalogs inside mix ranges. "Every lesson does X" is a range in disguise: make it one. [variety.md](references/variety.md).
- **No secrets** in any file, brief or prompt. Name a secrets file by path only.
- **Plain words.** Short sentences, one idea each, active voice.

## Scale

Set it in grill question 1. It decides which steps run and how heavy each one is.

| Scale | Core hours | Grill | Map | Research | Personas | Loop |
|---|---|---|---|---|---|---|
| **S** primer | up to ~10 | areas 0–6, about 10 questions | none | a few sources per claim | none or one | one session, `/goal` or a plain run |
| **M** course | ~10–200 | all areas, short | none or one page | per topic, ~20–50 sources | a few, quick | one goal run, 1–3 agents |
| **L** program | ~200–1,000 | all areas, deep | a decision map | per teacher, ~100 sources; book list | full, tested blind | multi-day goal run, a crew |
| **XL** school | 1,000+ | all areas, deep, several sessions | full map | as L, plus corpora | full, plus guest teachers | multi-day, full crew, a STEER file |

When in doubt, pick the smaller scale. The loop can raise the bar later; it cannot give back hours spent on machinery.

## The flow

Each step names the tool to use first and its options. Read a named skill's own `SKILL.md` before the step; never work from a summary. When a named skill is not installed, do the step by its done line and say which skill was missing.

### 1. Grill

Tool: [grill.md](references/grill.md) holds the course areas and a default for each question. Options for the method: Matt Pocock `grilling` or `grill-with-docs` (writes ADRs and a glossary as it goes), `domain-modeling`, or this skill's own grill alone. Use SigmaWriteGUI when the user wants status and question boards.

- The first reply shows the whole flow in one line (grill → signed spec and done ladder → map → research and books → queue → repo → goal prompt, then the loop builds, reviews and runs retros), so the user sees where the questions lead. Then it asks question 1: the scale.
- Then the learner, and the goal with its real odds.
- After each answer, add the pinned line to a running spec table (field, value, source, date).
- Save the user's own words verbatim in `docs/course/user-words.md`. They settle any later doubt about intent.
- **Done when** every area the scale needs has a pinned line or "not needed: <reason>".

### 2. Spec and done ladder

Tool: write `docs/course/spec.md` and `docs/course/done.md` from [repo-setup.md](references/repo-setup.md). Option: Matt Pocock `to-spec` for the prose spec.

- `done.md`: one checkable line per requirement, each with its proof (a script, a review file, or a user step). Size: S 10–30 lines, M 30–100, L 100–300, XL 200–500.
- The completion ladder: done is a line a script prints.
- **Done when** the user answers "yes, exactly" to the spec and the done list. Silence is not yes.

### 3. Map (L and XL)

Tool: Matt Pocock `wayfinder` when installed; else a `docs/course/map.md` of open decisions, each with a default. Prototypes of a page or a lab tool: `prototype`; let the user rank look variants with SigmaCreateArena; a design system with SigmaDesign.
- **Done when** no open decision blocks the build.

### 4. Research plan and book list

Tools: SigmaResearch (counted, scored public sources), SigmaDeepLook (video, audio, scans, transcripts), SigmaFinanceMan or a field skill when the subject needs models from filings. [research-and-books.md](references/research-and-books.md) holds the order and the book path.

- Research what the plan needs now: the base rate for the goal, the pedagogy evidence, and the sources of the first block. The rest becomes queue rows, so the loop researches just ahead of the lesson that needs it.
- L and XL: one book list for the user to buy and drop into `books/` (git-ignored).
- **Done when** the base rate has a source and every later research job is a queue row.

### 5. Queue

Tool: write `loop/queue.tsv` from [repo-setup.md](references/repo-setup.md). Options: Matt Pocock `to-tickets` for tracker issues; SigmaBrief to turn rows into parallel agent briefs.

- One row per job with `done_when`. Lesson rows are batches; media, personas, case files, lab tools and books get their own rows, so every area moves from the first turn.
- **Done when** every `done.md` line is covered by at least one row.

### 6. Set up the course repo

Tool: [repo-setup.md](references/repo-setup.md). Write the steering file (`AGENTS.md`, plus `CLAUDE.md` that points to it), the check command `checks/check.py`, the doctrine file and the run file `loop/run.md`. The run file carries the build method from [build.md](references/build.md): lesson pipeline, personas, media, review one model up, retro. Option: SigmaSetup for the repo's installed packs; SigmaFreedom to clear model-written limits from the new repo's docs.
- **Done when** the check command runs and prints the done-ladder line (all open is fine).

### 7. Goal prompt

Tool: SigmaLoop. It reads the queue and writes the loop file and the paste-ready prompt for the user's host: Claude Code `/goal` or `/loop`, Codex `/goal`, Antigravity, pi, T3 Code. Hand it the check command, the run file and the crew from the spec. [hosts.md](references/hosts.md) says what changes per host.
- **Done when** the prompt names `python checks/check.py` as the command whose output proves done, and tells the agent to re-read `loop/run.md` every turn.

## What the loop does with it

The run file makes every round of the loop: take the next unblocked rows into every free slot, build (SigmaShip, or Matt Pocock `implement` or `implement-spec` with `tdd` for code; SigmaWrite and SigmaHuman for prose; SigmaTaste for every new page, chart look or film), review one model up (SigmaReview or `code-review`; the reviewer never wrote the work), run the check, and write a retro line to `docs/learnings.md` with course lessons going into the doctrine file. [lessons.md](references/lessons.md) lists the failures a real build hit; the run file links it.

## Final response

1. What the repo now holds: one line per file written.
2. The base rate next to the goal, with its source.
3. The goal prompt in one fenced `text` block, ready to paste.
4. Notes, at most five lines: defaults taken, user steps before the run (books to buy, machines to free, logins), what was not done.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
