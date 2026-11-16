---
name: sigmaboat
description: 'Use when asked for sigmaboat or to run authorized work (loop file, ship issue, spec) on boat.dev sandboxes: base once, fork per worker, delete. Do not use to plan work (SigmaLoop) or by default.'
---

# SigmaBoat

Give work the user already authorized extra machines: [boat.dev](https://boat.dev) sandboxes (Ubuntu VMs, no GPU). SigmaBoat keeps one stopped base per repo, forks one worker per item, runs each item's gate there, lands the result by the work's own rules, and deletes every worker it started.

## Operating contract

- **Explicit only.** Start a sandbox only when the user's message or the spec names boat. No size has a GPU: GPU work goes to `lacompute` (SigmaVast). Sizes are `small` (half the price), `default` and `large`: a worker has the size of its base, and `laboat fork <repo> --type small` picks another.
- **Authorized work only.** The input is a loop file, an issue with acceptance criteria or a spec. SigmaBoat writes no plan; the host runs the work with its own subagents, threads or `/goal`. SigmaBoat supplies the machines and cleans them up.
- **Through `laboat` only.** `laboat` signs in from the keys file of the machine it runs on, on every run, and passes keys on stdin. Use it for every boat call, not the raw `boat` CLI. `lahelp laboat` is the command list; read it once.
- **Secrets.** Never print a key or token. `laboat checkout` and `laboat job --key NAME` pass them on stdin.
- **Delete what you start.** At the end, and after any failure, every worker is gone. Keep only stopped bases.
- **Docs.** Live: https://docs.boat.dev (page list: https://docs.boat.dev/llms.txt; add `.md` to a page address for plain text). The machines also keep a copy that `lasynctoolkit` refreshes: `docs/vendor/Boat_docs/` in the toolkit checkout that holds `laboat` and its guide. Read `cli-reference.md`, `pricing.md` and `limits.md` there before you guess a flag, a price or a limit. When you brief a worker agent, paste these two addresses and the `docs/vendor/Boat_docs/` path into its brief.

## Where it runs

- `laboat` runs on the machine you type it on. `laboat --on <machine> ...` (a name from the hosts file) runs it on another. There, a machine failure stops with exit 75 and does not hand over.
- A **machine** failure (no CLI, no key, no network, a refused key) prints one line and hands the command to the next machine. A **job** failure inside a sandbox is never retried elsewhere: report its exit code.
- Every command on one sandbox takes its `bx_` id. Auto-stop ends a sandbox at its `--ttl` (trial maximum 2 h): split longer items.
- A fork is a start. boat counts starts per minute, hour and day and never queues one: start workers one at a time, and read `limits.md` for today's numbers.

## Steps

```sh
laboat limits --all                 # per account: sandboxes running of its cap, starts left today; workers = min(free slots, starts left, ready items)
laboat base <repo>                  # build or refresh the stopped base (clone, install)
laboat job <repo> <branch> [--key NAME]... -- '<command>'   # one whole item: fork, branch, run, bring the branch home, delete
```

By hand, the same item:

```sh
laboat fork <repo>                                  # prints the worker's bx_ id
laboat exec <id> --cwd <repo> -- git switch -c <branch>
laboat exec <id> --cwd <repo> -- <the item's work, committed>
laboat exec <id> --cwd <repo> -- <gate command>     # keeps the exit code
laboat pull <id> <repo> <branch>                    # the branch into your checkout
laboat delete <id>                                  # usage saved, then deleted
```

Then land by the rules of the work that was invoked (loop file, SigmaShip, spec): push, open the pull request, merge only if that work allows it. Last: `laboat clean` deletes only the sandboxes `laboat` made (named `worker-*`; exit 1 names one it could not delete), then `laboat list` shows only `base-*` and the sandboxes of other tools, which stay.

## Final response

1. A table: worker id (`bx_...`), item, gate exit code, minutes, cost, deleted (yes).
2. The base: id, revision, state (stopped).
3. The pull requests the landing produced, and each item that did not finish, with its reason.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
