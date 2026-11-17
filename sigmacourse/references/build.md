# Build method (goes into loop/run.md)

The loop follows this every round. Keep only what the spec needs: a course with no teachers has no persona step, a text course no media step.

## The lesson pipeline

A job is a batch of lessons. Size it so one review can read the whole batch with care; measure minutes per batch and adjust.

1. **Draw the mix** from `variety.md`, seeded by the lesson id.
2. **Read before writing.** The notes the lesson cites, the doctrine, the glossary. Cite every note used.
3. **Draft** by SKILL.md step 4. Lead with the point. One term for one thing. Facts from the sources only. SigmaWrite for technical passages, SigmaHuman for course prose (with the user's writing sample when given). Every number from a calc script; every goal beside its base rate.
4. **Visuals and media specs** before the voice pass, because an edit after the voice pass makes it stale.
5. **Lesson checks.** Fix every finding first.
6. **Teacher voice pass** (when the lesson has a teacher persona). The persona reads the lesson and answers in its own words. Its voice frames the hook and the "in their words" parts; plain prose carries numbers and steps. Run a batch's persona calls in parallel, stop when a round changes nothing, and log its last notes for the reviewer.
7. **One fresh review, one model up**, for the whole batch, by an agent that did not write it, with the rendered pages in hand (SKILL.md step 5). A failed lesson goes back with the findings; passed ones get their own PASS line.
8. **Gate.** Stamp the review after the last prose edit. The check script counts the learner time.

## Code, checks and lab tools

- SigmaShip for an issue with acceptance criteria. Every check and tool test-first (Matt Pocock `tdd`, or a planted-defect test that turns the check red).
- A lab tool meets SKILL.md step 5 in full, does its one job end to end on real data, covers its main, empty and error states in a browser test, keeps its state over a restart, and lets the learner undo every destructive action.
- When two or more jobs fill one count, ship the counting script before the second job starts.

## Personas

- One per teacher: the user's persona builder when installed, else a SigmaResearch pass turned into a persona file. The user's own persona sheets are used byte for byte.
- Every quote is checked word for word against a stored source; read the passage around it.
- An "as of" setting lets a persona speak from a case's decision date.
- Run rules: `hosts.md`. Realism: `lessons.md`, the blind mix.

## Media

The spec names the user's tool for each kind. HyperFrames, when installed, for lesson videos and animations from data; SigmaDeepLook to transcribe and cut real footage; the user's generators for likenesses, voices, pictures and 3D. Every video gets a spec file, captions, a transcript and a contact-sheet check before it counts.

## Review gates

1. Source check: every quote, date and number matches a stored file.
2. Every number recomputed by script.
3. Hindsight check on historical cases: only what people knew then.
4. SigmaTaste on every new page type, chart look, film or deck.
5. A rigor test named after the field's strictest expert, and a practice test named after its best practitioner.

Kill rule: content the learner cannot apply to real material in the same part is cut or moved; a story stays only when it carries a mechanism.

## Briefs

Every brief names the task, the files, the done line, a scratch folder and the skills to read by path (SigmaBrief writes them). Data files go by path. Every agent ends with one report: files changed, checks run with results, what was not done. Every writing agent gets its own worktree.

## Retro

After every job: one entry in `docs/learnings.md` (Problem, Root cause, Fix, Rule), course lessons into `docs/course/doctrine.md`, and one improvement landed as code, a default or a run-file line.
