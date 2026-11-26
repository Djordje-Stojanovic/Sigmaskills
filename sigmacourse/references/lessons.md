# Lessons from a real course build

What one long course build, run by unattended loops over several weeks, learned. The numbers below are what happened there, as evidence, not targets.

1. **Content before checks.** One loop finished 90 rows in 23 hours: 52 check scripts, 3 lessons, 0 personas; gated hours stayed 0. Build a check only when the content it checks exists and is about to be gated. Count evaluator passes as infra.
2. **Count before you report.** An orchestrator said "most of what is left is lessons". A count showed no video, audio or image, 10% of case files, a fraction of personas, no history track, one lab tool. Every status answer counts each spec area on disk against its target.
3. **Hardcoding hides in "every".** "Every lesson ends with work on a real case" and "the first writer slot writes lessons, the second makes media" were both rejected as hardcoding. Turn every "every lesson does X" into a range, and every fixed lane into a dynamic queue.
4. **Too small is a defect.** Planned counts that looked fine on paper (case files, persona count, history hours) were all too small for the user's bar. Size from the ability map and the bar, not from a round number; ask "is this enough to reach the bar?"
5. **Visuals before the voice pass.** A lesson edited after its voice pass cannot gate. Diagrams and numbers first, then the voice pass, then one review.
6. **Voice frames; plain prose carries.** Whole paragraphs in a persona's chat voice blurred numbers.
7. **Every target sits beside its base rate.** A lesson turned a goal into a 34% yearly growth rate and gave no odds; review failed it. Applies to every growth or success number, not only the headline goal.
8. **Write the counting rule once.** When several jobs filled one floor, each counted "met" its own way and four reviews failed on counts.
9. **Stored sources or it did not happen.** A quote came from an interviewer, not the teacher; a total came from one line of a filing, not the sum. Every quote, date and number matches a stored snapshot, and a schema check fails when it does not.
10. **Personas leak.** A persona run inside the repo talked about the tracker and the user's notes, and spoke in the user's plain-English style. The fix is in `hosts.md`; check with one OOC message when a new account wrapper appears.
11. **Never edit the user's files.** A persona sheet was trimmed and given a header without asking. Use user files byte for byte; propose changes.
12. **Blind tests leak through surface clues.** Only one side was cut with "...", so the real answer was guessable. Cut both sides the same way and surface-check before the user sees it.
13. **Slow voice passes are a scheduling bug.** A 4-lesson pass took over an hour, almost all waiting on serial persona calls. Group merges and measure minutes per pass (`build.md`, step 6).
14. **One list, one home.** Two book lists drifted. Keep one, and point the other at it.
15. **Count real content, not the plan.** A done line printed "COURSE DONE" while the course held about 305 hours of text and 85 of video against 2,000 planned. Count reading time, playable video runtime, workbooks and exam questions, each by script.
16. **A format grid is not variety.** Topic-times-format cells looked varied: 172 titles covered 1,669 of 3,044 units. Measure repetition by title and by repeated figures, and cap a topic by what it has to teach.
17. **Read what the checks passed.** Units that passed every number and length check held stems that could not be answered, and one answer-letter pattern in 25 of 47 tests. Read a sample of built units yourself; then fix the builder, not each unit.
18. **A program measures a persona, never a judge.** Two numbers: its small-word (function-word) score against the person's own 10th percentile, and the count of 8-word runs it copies from held-out answers. No model or agent grades it; the user's ear does the rest.
19. **One voice per video.** The user ruled out a narrator and a teacher's cloned voice in one film. The user's ruling there: a clone read only the person's own words, and course text took a narrator. Ask the user before mixing voices.
20. **Check once, delete bad checks, never content.** The builder checks each unit once and nobody regrades it; a unit that cannot be built as planned takes the nearest fit, and a check that blocks good content goes.
