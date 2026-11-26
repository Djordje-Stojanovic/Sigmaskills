# The loop file

One Markdown file the loop agent re-reads at the start of every turn. Edits apply on the next turn. The host prompt stays short; everything long lives here.

Save to the place the user chose (default `.scratch/loops/<yyyy-mm-dd>-<slug>.md`). Keep its rules under about 1,200 words. Replace each `<...>`; a `<a | b>` is a choice by shape or answer: keep one side. Delete a section only when the answers made it empty.

## Template

```markdown
# Loop: <title>

Host: <host>. Shape: <S | M | L>. Stop line: <done command and its text, and/or date, time, zone>. Its output counts open, closed, parked and needs-owner apart, so no label hides a ticket. Re-read this file at the start of every turn.

## Stance
What can be undone runs and is logged; what cannot (deleting a repo, publishing a key) waits for the owner. Pre-authorised for this whole run: <list>. When no rule decides, take the option that keeps work moving and can be undone, and log `Ruling: <what> - <why> - <cost if wrong>`.
Speed metric: <accepted output per hour and per token, in the user's unit>. Drafted output that is not accepted counts as zero; when accepted output falls while drafting rises, stop drafting and land.
Owner's words: <path>. Every turn, copy each new message of his into it verbatim, one per numbered line, before anything else. Then rewrite the sections of this file it changes: his message wins. Cite a line as `W<n>`.
Needs the owner (play, pay, sign in, a call only he can make): one question at <owner page or chat>, with A, B, C, your pick first and what happens with no answer. Skip that item and take the next; nothing waits on him. A technical obstacle is work: never a question, never a park.

## Answers
<The user's reply to the question round, verbatim. Then one `Ruling:` line per default taken.>

## Budgets
No meter, no budget.
- <name>: limit <n> per <period>. Meter: `<command>` prints used against the limit. At the limit: <action>. "<his sentence>" (<date>)
- Spend with no usage store (a rented machine): a ledger file, one line per spend, written before the spend.

## Goal
At the stop line every item in <tracker> is accepted with dated evidence, or carries a dated line: done, left, why, next step.

## Crew
<S: this session plans, builds, re-reads its own diff in a fresh read and lands each item, top down, with no sub-agents. Delete the rest of this section.>
Slots: <N> workers, each on <its own git worktree | its own rented machine (sigmacollab)>, capped by CPU and by independent tracks. Models: <one or two ids with effort, from the user or the host's live list>.
1. **Tracks, not tickets.** The open items are packed into <N> tracks, one per slot. A track is a spec path and a done line; its files are disjoint from every other track's, and at most one track waits on another. A track with no spec gets one first (`to-spec`, or by hand).
2. **Any slot, any job.** A free slot takes what unblocks the most, in the same turn the last job ended: a build, a review of another track, a fix or the integration. The orchestrator picks each time.
3. **Warm sessions.** A track keeps its session: review fixes and follow-ups reach it as a message (hosts.md names the tool), so its context is paid for once. Only a review starts a fresh session.
4. **Orchestrator.** <M: plans, starts and steers workers, and merges each passed track into the feature branch. | L: writes specs, starts, steers and stops workers, answers their questions and keeps this run's files. Workers do every build, review, commit, merge and deploy, so its turns stay short.>
5. **Review.** The builder first re-reads its own diff. Then one reviewer in a fresh session (<another slot | a model of another provider>) runs the change, not only reads it, and ends with MERGE or a finding list. Its diff leaves out the paths the repo names as the owner's content, so no model passes or fails his words. The builder fixes P0-P2 findings and drops style nits; a finding it holds wrong is answered with the command that shows it. Rounds per track: max <2>; a clean round ends it. A track is parked only after <3> failed fix tries. No human review.
6. **State.** Each track is Ready, Working, Reviewing or Landed; findings send it back to Working. The worker that finished a part ticks it off itself, where the to-do is: the spec, the PR's checklist or the issue.
Crew files <3 or more workers; else delete>, in this file's folder:
- `crew.md`, written only by the orchestrator, read by every worker at start and when steered. It holds each trap (a command or flag that hung or wasted <15> minutes: two lines, written the moment it is seen) and each contract tracks must agree on (a shared type, an interface, a landed commit).
- `qna.md`: a worker appends `[OPEN] <slot>: <question> - default: <what it does meanwhile>` and keeps working on that default. The orchestrator answers in place on its next turn and copies a shared answer to `crew.md`.
Watchdog: <off | <15> minutes | none: this host has no timer>. On: one timer (hosts.md names it for this host) wakes the orchestrator when no worker reported for that long. It then runs the Stuck rule on every worker and sets the timer again. Why a timer: when every worker hangs at once, no completion notice comes.

## Failure rules
- **Stuck:** a job with no new commit and no new output for <15> minutes is stuck. Read the time from its last commit or log line when a notice or the watchdog wakes you, never by polling.
- **Restart:** a stuck job is steered once. Still stuck: it gets a WIP commit, is stopped, and restarts from that commit with the same spec; its cause goes to `crew.md` as a trap. A job stuck <3> times is parked: write why in the handoff and take the next unit.
- **Provider:** a provider that fails twice on transient errors (429, rate limit, cut-off run) drops to last place; an account at its limit drops out until its period resets. A model that refuses the task's domain once takes its whole provider family out for the rest of the run, with no second try.
- **Stronger model:** a job that fails twice moves to the stronger model or the higher effort, when the Models line names one.
- **Cleanup:** remove a finished job's worktree or rented machine; stop a stray process only by a process id this run wrote into the handoff, never by name and never an id it did not start.
- **No polling.** No sleep loops, no "still waiting" turns. Wait for completion notices.

## Speed rules
- **Accepted is final.** Check only what changed since the last acceptance.
- **Fast checks while building, full gates once.** A builder's checks cover the changed units only (<< 2s> target, `<new test LOC <= src LOC>`). The full or slow suite runs once per finished track and once at Finish.
- **Look at the real output.** <Work that is seen or heard: UI, rendering, animation, video, audio; else delete.> One gate shows the reviewer the result itself: screenshots, or a contact sheet of frames across the motion, beside a reference where one exists (sigmadeeplook reads video and audio). Green tests on a broken screen are not done.
- **Bulk compute.** Many small computations of the same kind run as one bulk job, not one run per unit.
- **A gate that never passes** is fixed or cut in the first hour.
- **One lock, one worker.** At most <N> heavy processes at once; a worker runs one server and one browser at a time and closes them when its check ends. Slots that queue behind one checkout, one build lock or one machine are one slot: give each its own. Give a process the time the work needs, never a cap of a few seconds.
- **Commands on another machine** carry a time limit and name exact folders, never a whole disk.
- **Records a machine reads.** Write a record only when a script or the next turn reads it: the handoff, the crew files, the tracker.

## Each turn
1. Read the clock (<zone>). At or after the stop line: Finish.
2. Read the handoff, `qna.md` when the run keeps crew files, and any new owner message (copy it to the words file first). Run <status command>.
3. For each finished job: send it to review, or accept it; refill its slot at once.
4. Fill every free slot from Priority. Skip units that share files with a running job.
5. Update the handoff (<path>) at <= <300> lines (<= <30 KB>) in two parts. **Live State**, overwritten in place each turn: active jobs with machine, process id and worktree, open blockers, owner steps, the exact resume command. **Shipped Ledger**: one line per accepted commit and gate status; old turn logs are compressed into it, shipped commit SHAs and open blockers stay, full history goes to <log file>. A fresh thread resumes from the handoff, never from chat history.

## Priority
<The ranked list, or the tracker section that holds it. Items that need the user live: write their facts, never decide them.>

## Landing
- Shape: <one feature branch and one PR for all tracks (default): each track branches from it and is merged into it when it passes; the PR merges after the full gate at Finish | a PR per track, each with `Closes #N`>.
- One branch: each track is its own issue, a sub-issue of the spec issue (`gh issue create --parent <spec>`, gh 2.94 or later) listed there as `- [ ] #N`. Its builder closes it after its branch is merged into the feature branch, so a track that waits for it does not start early. Two workers ticking boxes in one issue text lose a tick: GitHub keeps the last save.
- A track built on a rented machine comes back as a git bundle (sigmacollab), fetched into its branch.
- One shared checkout (only when asked): commit by path, `git add <paths>` then `git commit -m <msg> -- <paths>`; `git add -A`, `commit -a`, `stash`, `reset`, `checkout <file>` and `clean` take another worker's open work.
- Code first, with the unit's tests. <Changed-unit check command.>
- Also lands in: <docs, changelog, tracker>.
- Merge: <worktree off origin/base; PR; squash merge; delete branch and worktree>. Never skip hooks.
- Commits end with <trailer>. PR bodies end with <line>.

## Limits
Nothing outside these three lists limits the run.
- Owner's orders: <one line each: the order, then `(owner, <date>): "<his sentence>"`>.
- Mechanical guards, each with the fault it prevents: <from the answers>. A machine the run uses restarts only in the window the answers name: a restart ends every background job.
- Scope notes: <what no ticket covers>. A scope note marks where the work ends; it bans nothing.

## Finish (at the stop line)
Start nothing new. Let running jobs finish and write their state. Run the full gate once and print it. Prove sync: no open PR of this run, one worktree, no stray process, no rented machine (sigmacollab's teardown proof), no timer of this run. Write the final handoff: accepted (with evidence), open (reason, next step), owner steps. Check an owner step before you list it: look up the machine, account or file it names, run its command once yourself, and label an undo block "only to take it back later".
```

## Rules for the file

- Every number comes from an answer or the repo; a `<15>` style default is a recommendation the question round confirms.
- Failure rules, Speed rules and Finish are defaults: copy each whole. Drop a line only when an answer contradicts it.
- Write rules as checks the agent can run, not as wishes.
- A preference that would put several slots behind one checkout, one build lock or one machine is a serial bottleneck: name the trade-off in the question round before it becomes a Limit.
- Model ids appear only on the Models line of Crew.
- Host-only facts (wake tools, cache flags, proxies) belong in hosts.md, not here.
