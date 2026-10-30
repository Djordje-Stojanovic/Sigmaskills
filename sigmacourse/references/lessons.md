# Lessons from a real course build

Each rule cost a real build hours or days. The run file links this list; read it before the first round.

1. **Content before checks.** One loop finished 90 rows in 23 hours: 52 check scripts, 3 lessons, 0 personas; gated hours stayed 0. Build a check only when the content it checks exists and is about to be gated. Count evaluator passes as infra.
2. **Count before you report.** An orchestrator said "most of what is left is lessons". A count showed no video, audio or image, 10% of case files, a fraction of personas, no history track, one lab tool. Every status answer counts each spec area on disk against its target.
3. **Hardcoding hides in "every".** "Every lesson ends with work on a real case" and "the first writer slot writes lessons, the second makes media" were both rejected as hardcoding. Turn every "every lesson does X" into a range, and every fixed lane into a dynamic queue.
4. **Too small is a defect.** Planned counts that looked fine on paper (case files, persona count, history hours) were all too small for the user's bar. Size from the skill map and the bar, not from a round number; ask "is this enough to reach the bar?"
5. **Visuals before the voice pass.** A lesson edited after its voice pass cannot gate. Diagrams and numbers first, then the voice pass, then one review.
6. **Voice frames; plain prose carries.** Whole paragraphs in a persona's chat voice lost a blind test 17 of 20 and blurred numbers. Use the teacher's voice for the hook and the "in their words" part.
7. **Every target sits beside its base rate.** A lesson turned a goal into a 34% yearly growth rate and gave no odds; review failed it. Applies to every growth or success number, not only the headline goal.
8. **Write the counting rule once.** When several jobs filled one floor, each counted "met" its own way and four reviews failed on counts. Ship the counting script before the second job starts.
9. **Stored sources or it did not happen.** A quote came from an interviewer, not the teacher; a total came from one line of a filing, not the sum. Every quote, date and number matches a stored snapshot, and a schema check fails when it does not.
10. **Personas leak.** A persona run inside the repo talked about the tracker and the user's notes, and spoke in the user's plain-English style. Run personas outside the repo with every global rule file excluded; check with one OOC message when a new account wrapper appears.
11. **Never edit the user's files.** A persona sheet was trimmed and given a header without asking. Use user files byte for byte; propose changes.
12. **Blind tests leak through surface clues.** Only one side was cut with "...", so the real answer was guessable. Cut both sides the same way and surface-check before the user sees it.
13. **Slow voice passes are a scheduling bug.** A 4-lesson pass took over an hour, almost all waiting on serial persona calls. Run persona calls in parallel, cap rounds at 3, batch 6–8 lessons, group merges, and measure minutes per pass.
14. **A crew change touches every check that counts slots.** The slot total lived in several files and their tests. Search for every place a count is hardcoded before changing it.
15. **Name the exact row in a brief.** A brief that names the exact requirement row passes review in one round; a general rule does not.
16. **Read the clock; never guess it.** Status times were off by 30 minutes once.
17. **One list, one home.** Two book lists drifted. Keep one, and point the other at it.
