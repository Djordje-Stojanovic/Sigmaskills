# Build method (goes into loop/run.md)

The loop follows this every round. Adapt it to the spec; drop what the scale does not need (an S course has no personas, no voice pass and often no media beyond diagrams).

## The lesson pipeline

One job is a batch: 1–3 lessons for S, 4–8 for L and XL.

1. **Draw the mix.** Shape, tasks, level and media per lesson from `variety.md`, seeded by the lesson id.
2. **Read before writing.** The research and book notes the lesson cites, the doctrine, the glossary. Cite every note used.
3. **Draft.** Lead with the point. One term for one thing. Facts from the sources only. SigmaWrite for technical passages, SigmaHuman for all course prose (with the user's writing sample when given). Every number from a calc script; every goal or growth number beside its base rate.
4. **Visuals and media specs** before the voice pass, because an edit after the voice pass makes it stale. Load `dataviz` (or the host's chart skill) before any chart.
5. **Run the lesson checks.** Fix every finding first.
6. **Teacher voice pass** (when the lesson has a teacher persona). The persona reads the lesson and answers in its own words. Its voice frames the hook and the "in their words" parts; plain prose carries numbers and steps, because chat-style voice blurs them. Run the persona calls of a batch in parallel; at most 3 rounds, then log its last notes for the reviewer. The pass also catches wrong facts.
7. **One fresh review, one model up**, for the whole batch: SigmaReview-style findings with evidence, by an agent that did not write the work. A failed lesson goes back with the findings; the passed ones get their own PASS line.
8. **Gate.** Stamp the review after the last prose edit. The check script counts the hours.

## Code, checks and lab tools

- SigmaShip for an issue with acceptance criteria. Options: Matt Pocock `implement-spec` (after `to-spec` and `to-tickets`) or `implement`. Every check and tool test-first (Matt Pocock `tdd`, or a planted-defect test that turns the check red).
- Lab tool polish bar, all ten: does its one job end to end on real data in three clicks or fewer; a browser test covers the main flow, the empty state and the error state; works at phone width and on desktop, dark and light; accessible (WCAG AA); every number from a calc output; zero console errors; a SigmaTaste pass with every big visible item done; usable the first time with no manual; state survives a restart; every destructive action can be undone.
- When two or more jobs fill one count, ship the counting script before the second job starts.

## Personas

- Build one per teacher: `persona-forge` or the user's own persona builder when installed, else a SigmaResearch pass (the source floor from the spec) turned into a persona file. The user's own persona sheets are used byte for byte.
- Every quote is checked word for word against a stored source; read the passage around it.
- An "as of" setting lets a persona speak from a case's decision date.
- Run rules: `hosts.md`. Realism: blind pairs in SigmaCreateArena; cut both sides the same way so no surface clue gives the answer away.

## Media

The spec names the user's tools for each kind. Sigma routes when present: HyperFrames for lesson videos, animations and case intros from data; SigmaDeepLook to transcribe and cut real footage; the user's video, voice, image and 3D generators for likeness clips, cloned voices, pictures and shots. Every video gets a spec file, a transcript and a contact-sheet check before it counts. SigmaTaste on the first piece of every kind.

## Review gates

1. Source check: every quote, date and number matches a stored file.
2. Every number recomputed by script.
3. Hindsight check on historical cases: only what people knew then.
4. SigmaTaste on every new page type, chart look, film or deck.
5. A rigor test named after the field's strictest expert, and a practice test named after its best practitioner.

Kill rule: content the learner cannot apply to real material in the same block is cut or moved; a story stays only when it carries a mechanism.

## Briefs

Every brief names the task, the files, the done line, a scratch folder and the skills to read by path (SigmaBrief writes them). The agent reads each skill itself. Data files go by path. Every agent ends with one report: files changed, checks run with results, what was not done. Every writing agent gets its own worktree.

## Retro

After every job and every round: one entry in `docs/learnings.md` (Problem, Root cause, Fix, Rule), course lessons into `docs/course/doctrine.md`, and one improvement landed as code, a default or a run-file line.
