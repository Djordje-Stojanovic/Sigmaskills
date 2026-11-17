---
name: sigmacourse
description: 'Use when asked for sigmacourse or to plan a tutorial, guide, course or curriculum of any length, from a one-minute tutorial or a one-pager to a program of thousands of hours. It starts from what the learner can do at the end and cuts its own steps to the size. Do not use for live tutoring.'
---

# SigmaCourse

Plan teaching of any length, at the weight that length needs. A one-minute tutorial gets three questions and one file. A 50-hour course gets a spec, a done list, a course repo and one goal prompt for an unattended loop. The size decides how many steps run; small work never pays for big machinery.

On a machine with the local skill `storgestudio-shipcourse`, that skill builds the course with that machine's own stack (pages, films, personas); it runs steps 1 and 2 of this skill first.

## Operating contract

- **The user decides.** Subject, depth, voice, media, real people as teachers, generated likenesses: all the user's call. Add no limits of your own. The only confirm: an action that deletes the repo or publishes a secret.
- **One question at a time, your pick first.** The recommended answer and its reason, then the other options, then one example. "Just build it": draft every answer as a guess and ask for corrections once.
- **The user's newest word wins** over every default here. When it clashes with a rule here, say once what it costs, then do what the user picks.
- **Realism.** Every number has a source or a stated assumption. Every goal sits next to its real base rate. Counts and sums run in a script, never in prose.
- **Method follows evidence.** The learner does work, retrieves from memory and gets feedback on it. Retrieval, spacing and worked examples have the evidence; "learning styles" do not.
- **No secrets** in any file, brief or prompt. Plain words: short sentences, one idea each, active voice.

## 1. Size

Ask it first, as learner time: any length the user names. Pick the tier by the learner time, and pick the smaller tier when in doubt.

| Tier | Learner time | Examples | What runs | What it writes |
|---|---|---|---|---|
| **Piece** | up to ~15 min | a one-minute tutorial, a one-pager, a ten-minute guide | steps 1, 2, then write it | the piece, one file |
| **Session** | ~15 min to ~3 h | a 45-minute workshop, a 2-hour course | steps 1, 2, a plan file, write it, one review | a plan file and the lesson files |
| **Course** | ~3 h to ~50 h | a 10-hour course, a 40-hour bootcamp | the full flow, short grill, no map | the course repo and one goal prompt |
| **Program** | ~50 h and up | a 50-hour introduction, a 1,000-hour school | the full flow, deep grill, map, personas, crew | as Course, plus `map.md`, `STEER.md`, a book list |

Learner time is what the learner spends: reading at an assumed 200 words a minute (say it is an assumption), video at its real runtime, and tasks at a fixed number of minutes by type. A one-pager is about 500 words, so about 2 to 3 minutes of reading plus its task. The check counts it; nobody types a time.

## 2. The end state, then the parts (every tier, before any outline)

1. **Write the end state.** One to seven lines, each in this form: "At the end, the learner can <do what> on <real material> to <what standard>." A Piece has one line. Each line names a task the learner can do to prove it.
2. **Derive the parts.** Under each line, write what the learner must be able to do just before it. Repeat for each new line, down to what the learner can already do (ask if you do not know). The tree is the parts list.
3. **Fit the size.** Give each part its minutes; a script sums them from Course up. Over the size: drop the parts or the end line that matter least, and tell the user which. Under the size: stop; do not pad.
4. **Only now write the outline.** Order the parts so each comes after what it needs. Nothing goes in that no end line needs.

**Done when** every outline item names the end line it serves, and the sum fits the size.

## 3. Build by tier

### Piece

- Ask at most three questions (the learner, the end line, the medium), and none the request already answers.
- Write it in one file: the point first, one worked example, one task the learner does, the answer after the task. A one-minute video is a script of about 150 spoken words.
- Check: read it aloud in your head against the size, and that the task proves the end line. Then stop. No spec, no repo, no loop.

### Session

- Ask the grill's areas 1 and 2 (the learner, the goal) in a few questions.
- Write `course-plan.md`: the end state, the parts tree, the outline with minutes, the sources, the media per part, and the variety draw (2 to 4 lesson shapes from [variety.md](references/variety.md)).
- Write the lessons in one session (`content/`), then one review by a fresh agent that did not write them. No queue and no loop.

### Course and Program

Each step names its tool. Read a named skill's own `SKILL.md` before the step; when it is not installed, do the step by its done line and say which skill was missing.

1. **Grill.** [grill.md](references/grill.md): a Course asks areas 1 to 7, 13 and 14, one or two questions each; a Program asks all areas in depth. Options: Matt Pocock `grilling` or `grill-with-docs`. Save the user's words verbatim in `docs/course/user-words.md`. Done when each area has a pinned line or "not needed: <reason>".
2. **Spec and done list.** `docs/course/spec.md` and `docs/course/done.md` from [repo-setup.md](references/repo-setup.md); the end state and the parts tree from step 2 go at the top of the spec. Done when the user answers "yes, exactly". Silence is not yes.
3. **Map (Program).** Matt Pocock `wayfinder`, or `docs/course/map.md`: open decisions, each with a default. Done when no open decision blocks the build.
4. **Research.** SigmaResearch for public sources, SigmaDeepLook for video and audio. [research-and-books.md](references/research-and-books.md). Research what the plan needs now (the base rate for the goal, the first block's sources); the rest becomes queue rows. Done when the base rate has a source.
5. **Queue.** `loop/queue.tsv` ([repo-setup.md](references/repo-setup.md)). Done when every `done.md` line is covered by a row.
6. **Repo.** `AGENTS.md`, `checks/check.py`, `loop/run.md` from [build.md](references/build.md). Done when the check command runs and prints the done line (all open is fine).
7. **Goal prompt.** SigmaLoop writes it for the user's host ([hosts.md](references/hosts.md)). Done when the prompt names `python checks/check.py` as the proof and tells the agent to re-read `loop/run.md` every turn.

The loop then builds, reviews one model up, runs the check and writes a retro line each round. [lessons.md](references/lessons.md) lists what a real 1,000-hour build learned; the run file links it.

## Final response

- Piece: the file path, the end line, and the minutes it takes.
- Session: the plan file, the lesson files, and the review's findings.
- Course and Program: one line per file written; the base rate beside the goal, with its source; the goal prompt in one fenced `text` block; at most five lines of notes (defaults taken, steps the user must do first).

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
