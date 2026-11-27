# Examples: the seven parts filled in, two loops worked through, lessons

## 1. Eight fields

Examples, not a list of cases: a new goal does not need to fit a row. Noise, budget and stop rule follow the grill's defaults.

| Field | Target | Score | Guards | Measurer |
|---|---|---|---|---|
| A served model | the launch recipe and the serving code | output rate, prompt-reading rate, first-result time, parallel streams | the output stays the same within its noise; the memory cap | a script |
| A text (a 2-minute stock pitch) | the pitch | share of blind pairs the new version wins | every number, name and date is in the source; spoken length | the owner and people he names pick pairs; a script checks the guards |
| Game frame rate | engine settings, shaders, the render code | frames per second on a fixed camera path; 1 % low frame time | a frame comparison against the start; input latency | a script that plays the path; one probe uses a path made fresh each run |
| A film's look | the grade, the denoise and sharpen steps | share of blind pairs the new look wins | runtime and resolution unchanged; no banding | the owner picks between two stills, blind, on one fixed question |
| Video file size at the same quality | the encoder settings and pipeline | bytes per minute (lower is better) | a perceptual quality metric within the noise of the start; encode time | a script: size is the score and quality the guard, a speed loop reversed |
| Video render time | the render pipeline, its settings and code | seconds per finished minute | the frames match the start within a pixel metric | a script; one probe renders a timeline it has never seen |
| A build | the build graph, caching, compiler flags | wall time of a clean build and of a one-file change | the test suite passes; output size | a script; cold and warm builds are two probes |
| A solver | the algorithm and its data structures | run time on a fixed instance set | every answer equals the reference | a script; one probe draws a new instance each run |

## 2. Two loops, side by side

| | A model on a GPU | A 2-minute stock pitch |
|---|---|---|
| The owner says | "make my model answer faster on this card, same quality" | "make this pitch for a listed company better; keep going until I say stop" |
| Grill 1: who, how long | one agent, one night. One card measures one pass at a time, so a crew adds drafts, not speed | a crew: workers draft one candidate each, the orchestrator runs every pass; no end date (`run_hours` null) |
| Grill 2: time budget | from one timed run: a cold start plus the slowest probe, with headroom | seconds: both steps are scripts that read files |
| Target | the launch recipe and the serving code | the pitch file |
| Score | probes at the settings his client really sends, each with a fixed output length | share of blind pairs the new version wins |
| Guards | a same-seed fidelity check against recorded references; a task suite as a regression alarm; the memory cap. Invariants: weights, precision, context length | every number, name and date is in the source filing; two minutes spoken; the parts he names are all there |
| Measurer | `script` | `pairs`: he and the people he names pick, blind |
| Noise | 3 runs of the unchanged recipe | the champion against a copy of itself: how often a pick is a coin flip |
| `steps` | start the server with the change; a fixed warm-up; probes write `raw/score.json`; the fidelity check writes `raw/quality.json`; drain, then stop | score reads his picks into `raw/score.json`; quality runs the guard script; no start or stop |
| Compute | the local card first; else `sigmacollab` rents one | the local machine |
| Profile | time each part of one real request; the ceiling is bytes read per output unit over the card's measured memory speed | he marks the sentence where he stopped listening |
| Idea order | start-up caches, compiled graphs, drafting ahead, sizes for parallel use, prompt-reading chunks; kernel work last | the opening line, the one number that carries the case, the order of the parts, a sentence cut |
| A pass | `python climb.py run runs/0012 change.patch`, `verdict`, then `promote` or revert | the guard script first, so he never reads a pitch that lost a fact; he picks a batch of pairs in one sitting; then one pass per candidate reads his picks (`--work TEXT`) |
| Between his sittings | the script measures all night | research rounds and new drafts; nothing is promoted without his picks |
| Stop | `run_hours` used up, then `REPORT.md` | he writes `STOP`, then `REPORT.md` |

Other served models take the first loop with other probes:

| Kind | Score probes | Quality check |
|---|---|---|
| Language | output rate, prompt-reading rate, first-result time, parallel streams | fidelity against recorded references; long-context recall; a task suite |
| Image | seconds per image, peak memory | a same-seed image metric |
| Video | seconds per frame or clip, peak memory | a per-frame and a temporal metric |
| Voice, music | real-time factor, time to first chunk | a spectral distance; word error rate |

## 3. Lessons, each paid for once

**The scorer**

- Build the first scorer at the owner's real settings, read from his client's config. A scorer for a workload nobody runs threw away its first passes.
- Measure the unchanged target three times before the first idea. Identical runs differed by a tenth on the noisiest probe.
- Fix the amount of work per probe. A probe with natural output lengths rewarded the run that wrote less.
- Count work units from the target's own statistics, never from stream chunks.
- A quality check that measures difference, not direction, rejects real wins. Ask for his drift policy in the grill.
- He orders the probes; then every scored probe gets a real weight. Raw priority weights made the small ones invisible.
- Split the scorer's inputs from the agent's by construction where you can: a hash lock stops edits, not tuning.

**The machine**

- Smoke-test a new machine for a few minutes before the first baseline: disk, memory, driver, download speed, the system calls the target needs.
- A new machine is a new baseline. Copy the quality references home after every recording; they die with a rented machine.
- A remote machine keeps its own copy of the scorer. Compare hashes before a run reaches its probes.
- A status command that cannot reach its source says so. An error read as "the machine is gone" would have ended the run.
- Stop a target by draining its requests, then a timeout. Stop a process by the id you started.
- Put code in files and run the files; quoting through two shells breaks. A script that runs gets a new copy, not an edit.

**Ideas and decisions**

- Check that a setting exists, its default today and its dependencies. Several ideas were on by default already.
- Profile the path you have never profiled. One late profile found a tenth of the time in a step no guess had named.
- Measure the ceiling on the machine; a spec sheet is not one. Parts already near it are done.
- Test one variable before you write down a cause.
- Stack two changes only when each won alone and they touch different parts; test the pair as one pass.
- An enabler can be neutral alone. Log the ruling and run its second step as the same idea.
- Cheap settings first, every time, starves the code ideas. Built, one "days" idea took a small part of its estimate.
- A move to the owner's own machine is its own experiment: measure start and candidate there, prove the change is active, keep a rollback.
- Before a tuned recipe is published: pin every version, build cleanly from the pins, and prove that build matches the champion within noise.

Serving ceilings, the idea order, drain before stop and the clean-build check draw on [sybil-solutions/inference-optimisation-skill](https://github.com/sybil-solutions/inference-optimisation-skill) (MIT).
