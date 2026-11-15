# Phase 1: the owner interview

One round of questions fills the seven parts of the loop. Use `/grilling` when it is installed; this file is the
question list. Ask them together, each with its recommended answer and the reason. **"All recommended" is an answer**:
then write the defaults and go. Never ask what a rule below already decides.

## Before you ask: run the target

Start the target once or twice as it is, and time it. The recommended numbers come from that run, not from a guess:
how long one pass takes, how much one run differs from the next, how long the quality check takes. A default is a
rule ("twice the measured spread"), never a number copied from another project.

## The questions

| # | Question | Recommended answer | Why |
|---|---|---|---|
| 1 | **Target.** What exactly do we change, and what may never change (the invariants)? | the thing you pointed at; everything you did not name as changeable stays locked | a loop that may change anything finds the cheapest trick |
| 2 | **Score.** What must get better, in which direction, and under which real use? | your own words, made countable: your sizes, settings and workload | a score for a workload nobody runs measures nothing |
| 3 | **Several numbers?** If the score has parts, which matter most? | weights in your order, each part at least a fair share; parts you do not rank become guards (weight 0) | a part with a tiny weight is invisible; a guard still may not drop |
| 4 | **Guards.** What may not get worse, and how much worse still counts as the same? | the output stays as good as the start, within the noise of its check | the quality check beats the score |
| 5 | **Measurer.** Is there a number, or do we compare versions? | a script when a number exists; blind pairs when it does not (see below) | the loop needs a verdict and its spread, nothing more |
| 6 | **Quality check size.** How long may the check take? | at most a quarter of a pass (`quality_share_max` 0.25) | a check longer than the measurement halves the ideas per day |
| 7 | **Noise.** How many runs of the unchanged target set the noise? | 3 (`repeats`) | fewer cannot show a spread |
| 8 | **Smallest gain.** How big must a gain be to count? | twice the measured spread (`min_gain` null) | a gain inside the noise is luck |
| 9 | **Confirmation.** When does a win need a second run? | only when the gain is under twice the smallest gain (`confirm_below` 2) | a big gain does not need it; a small one might be luck |
| 10 | **Held-out check.** Should a second input set guard against tuning to the visible inputs? | off; if you have your own machine, your run there is the last check | it costs a pass per KEEP and blocks without a reason when it is broken |
| 11 | **Budget.** Time and money per pass and for the whole run? | as measured in the first run; whole run until you say stop | the loop reports its own cost per idea |
| 12 | **Stop rule.** When does the loop end? | when you say stop and `REPORT.md` exists | a machine-checked line ends; "until it is good" never does |
| 13 | **Logistics.** Where do the keys live, which machine, git or not, who may touch your own machines? | keys in the project's `secrets/`; your machines read-only; git on | the loop must never print a secret or touch what it was not given |

Bold ideas need no question: code and design changes are wanted, and at least every third pass is one
(`bold_every` 3). Category changes need no question either: after 3 passes without a win in one category
(`category_switch_after` 3).

## When the owner has no number

"More beautiful", "better", "reads well": the interview asks one more question. **"Here are two versions. Which is
better, and what did you look at?"** Show two real versions of the target (the start and one quick change).

- His answer names the measurer's question ("which frame looks more like film", "which chapter would you keep
  reading"). Write it down word for word: it is the fixed question of every pair.
- The measurer is blind pairs: each pair shows the champion's and the candidate's version of the same input, in
  random order, without saying which is which. The owner judges, or a judge he accepts (a model with that fixed
  question, a panel). **His own pick beats a judge model**; a judge stands in only where he says so.
- The score is the share of pairs the new version wins (`"measurer": "pairs"`). A/A runs (the champion against
  itself) give the noise. For the pair mechanics, use SigmaCreateArena; do not copy its rules here.
- Size the pair count to the budget: enough pairs that the A/A spread is smaller than the gain he cares about.

## Write it down

`SPEC_DRAFT.md` holds every answer and each `Ruling: <decision> - <reason> - <cost if wrong>` you took for him.
`project.json` holds every setting of the loop; the scripts read them from there. The owner signs off with a "yes".
