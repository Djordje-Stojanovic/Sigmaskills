# Plain words for the owner

The scripts use short labels. The owner reads plain phrases. Reports, status answers and `PROGRESS.md` use the right
column; a label appears only in a code span, after the phrase. Say what a thing does before you name it.

| Label in the files | Say this |
|---|---|
| KEEP | the change is better and stays |
| STAGE1-WIN | the change scored better; the quality check runs next |
| REJECT | the change is not better; it is undone |
| ARCHIVE | not a clean win: one part got better and another worse, or the gain is too small overall; you decide |
| VOID | the run does not count (the scorer or a locked setting changed) |
| CRASH | the run failed before it measured anything |
| champion | the best setup so far |
| baseline, start | your setup as it was before the loop |
| promote | make the change the new best setup |
| pass | one try of one change |
| probe | one measurement, for example "decode speed" |
| score | the combined result of all measurements |
| quality check, gate | the test that the result is still as good |
| guard | a measurement that may not get worse |
| noise, spread, A/A | how much the result moves when nothing changed |
| the smallest gain, keep floor | the gain needed to be sure it is not luck |
| confirmation run | the same change measured once more |
| held-out check | the same test on inputs the loop never tuned to |
| scorer, evaluator | the scripts that measure; the loop cannot edit them |
| lock, evaluator.lock | the fingerprint that shows the scripts were not edited |
| profile | where the time (or size, or flaw) goes, part by part |
| idea queue | the list of changes to try, best chance first |
| ruled out | tried, does not work, and why |
| measurer | what compares two versions: a script, you, or a judge you accept |
| blind pairs | two versions shown without saying which is which |

## How a report starts

1. What changed for the owner, in one line: "Your setup now answers 12 % faster than at the start; quality is the same."
2. The table: the best setup so far against the start and against his current setup.
3. What runs now, and what comes next.

Bad: "P9 KEEP, gate ok, ARCHIVE on c3, held-out sealed FAIL."
Good: "Pass 9: the change is better and stays (6 % faster than the best setup before). The quality test passed."
