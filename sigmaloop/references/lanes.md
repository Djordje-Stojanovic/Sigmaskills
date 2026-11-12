# A run with more than one lane

Read this only when the run has two or more lanes. One agent alone does not need it. Budgets, the review rule, the words log and the owner page are in [loop-file.md](loop-file.md); this file adds what several lanes need.

## Levels

| Level | Who | Ends? |
|---|---|---|
| Top | Orchestrator: one thread, owns the backlog, the owner page and the stop line | Never, until the stop line |
| Lane | One manager per lane: thinks, checks, cuts big tickets into worker jobs | No: ticket after ticket |
| Worker | Up to three per lane, one whole ticket each | Yes: it ends when the ticket is done |

Two levels under the top, never three. Why: a worker that never ends fills its context; a manager that ends drops its queue. A job with no end state (a speed hunt) is a lane: a failed try is logged and the next one starts.

## One backlog, lanes without a topic

One file, one ticket per line. The mark says who holds it:

```
- [ ] T07 one line of what | proof: `<command>` prints <text> | size M
- [~LANE 2] T09 ... | claimed 14:05
- [y] T11 ... | waits for the owner: card q-11, no answer = A
- [x] T04 ... | proof: <one line>, 2026-11-12, PR 12
- [d] T05 ... | dropped: "<his sentence>"
```

- A free lane takes the first open ticket it may take, of any kind. It prefers a repo it knows and never idles for that.
- Claim rule: the top is the only writer. It marks `[~LANE n]` before it hands the ticket out, and only if no branch `<run>/<ID>` and no live thread with `<ID>` in its title exists. A worker's title starts with the ticket id and its branch carries it, so the guard can see double work. Why: run 1 rendered one film twice.
- The top hands each lane a queue of several tickets. A lane with one ticket left says so in its status block.
- A ticket that needs the owner is marked `[y]`, gets one card, and the lane takes the next ticket in the same turn.
- Small tickets go to one worker as a batch. A big ticket is cut by its manager.
- Done means the proof on the ticket line was printed in that turn.

## Models

Difficulty picks the model first. The meter's `next=<family>` picks between equal fits. Never stop a running job for the split. A cheap job on the wrong family may be stopped and restarted. Tiers and ids: the Crew table of the loop file.

## The lane brief

One shared file, read by every manager first and after every compaction. A launch message holds only the lane's own queue. The file ends with dated facts the top has proved, newest first. A lane reads them before it raises an alarm. Why: a false alarm cost four minutes of every lane once.

Each lane overwrites its status file at the end of every turn (12 lines at most) and ends its turn with the same block:

```
STATE: <ticket ids in work, what is next>
RUNNING: <worker title, model, job> (one line per worker)
LANDED: <ticket id: the proof, PR number>
POSTPONED: <ticket id: the reason>
FOR_ORCHESTRATOR: <a spend ask, a PR to merge, a decision; or "nothing">
FOR_OWNER: <only taste, new money, a delete of his things, a step for his hands: one question, A, B, C, your pick first; or "nothing">
```

The top waits on these files, never by polling a thread: reading a whole thread costs far more than the 12 lines.

## Merging

Name once, per repo, who merges: the lane for low-risk repos, the top for code that can break live service or publishing. A change to the publishing path waits for a quiet window between slots.

## The owner page

The owner reads on a phone. One page, not folders or logs. Open cards first; answered ones go to a log tab. A card is one JSON file named `<id>.json`, written as `x.tmp` then renamed:

```json
{"id": "q-11", "kind": "question", "title": "One plain sentence", "body": "Two lines of context.",
 "options": ["A ...", "B ...", "C ..."], "rec": 0, "media": [{"file": "clip.mp4", "caption": "what he sees"}],
 "state": "open", "added": "2026-11-12T03:10:00Z"}
```

- `kind` is `question`, `step` (a command with a copy button), `answer` or `note`. An id is never reused for another question.
- The builder reads every card file, rebuilds the page when one changes, and serves it behind the owner's login. Use the repo's own builder when one exists.
- He answers in one reply block that names each card by id. An unanswered card comes back with the same id.

## The meter

Three lines it must do. It reads the provider's own usage store, read-only. It prints each family's share of spend for the period against its target and `next=<family>`. It never blocks a job. Use the repo's own script when one exists. With no usage store there is no budget: ask for a ledger.
