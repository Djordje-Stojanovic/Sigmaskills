---
name: sigmaboat
description: 'Use when asked for sigmaboat or to run authorized work (loop file, ship issue, spec) on boat.dev sandboxes: base once, fork per worker, delete. Do not use to plan work (SigmaLoop) or by default.'
---

# SigmaBoat

Give work the user already authorized extra machines: [boat.dev](https://boat.dev) sandboxes (Ubuntu VMs, no GPU). SigmaBoat keeps one stopped base per repo, forks one worker per item, runs each item's gate there, lands the result by the work's own rules, and deletes every worker it started.

## Operating contract

- **Explicit only.** Start a sandbox only when the user's message or the spec names boat. No size has a GPU: GPU work goes to `lacompute` (SigmaVast).
- **Authorized work only.** The input is a loop file, an issue with acceptance criteria or a spec. SigmaBoat writes no plan; the host runs the work with its own subagents, threads or `/goal`. SigmaBoat supplies the machines and cleans them up.
- **Through `laboat` only.** `laboat` signs in with the key of the machine it runs on and reads keys and limits for you. The raw `boat` CLI is not the way here: Git Bash cannot run `boat.exe`, and a hand login leaves a key on a command line. `lahelp laboat` is the command list; read it once.
- **Secrets.** Never print a key or token. `laboat checkout` and `laboat job --key NAME` pass them on stdin.
- **Delete what you start.** At the end, and after any failure, every worker is gone. Keep only stopped bases.

## Where it runs

- `laboat` runs on the machine you type it on. `laboat --on <machine> ...` (a name from the hosts file) runs it on another.
- A **machine** failure (no CLI, no key, no network, a refused key) prints one line and hands the command to the next machine. A **job** failure inside a sandbox is never retried elsewhere: report its exit code.
- Every command on one sandbox takes its `bx_` id. Auto-stop ends a sandbox at its `--ttl` (trial maximum 2 h): split longer items.

## Steps

```sh
laboat limits --all                 # free slots per account; workers = min(slots, ready items)
laboat base <repo>                  # build or refresh the stopped base (clone, install)
laboat job <repo> <branch> [--key NAME]... -- '<command>'   # one whole item: fork, branch, run, bring the branch home, delete
```

By hand, the same item in four steps:

```sh
laboat fork <repo>                                  # prints the worker's bx_ id
laboat exec <id> --cwd <repo> -- <gate command>     # keeps the exit code
laboat pull <id> <repo> <branch>                    # the branch into your checkout
laboat delete <id>                                  # usage saved, then deleted
```

Then land by the rules of the work that was invoked (loop file, SigmaShip, spec): push, open the pull request, merge only if that work allows it. Last: `laboat clean` (deletes every sandbox but the bases; exit 1 names one it could not delete) and `laboat list` shows only `base-*`.

## Final response

1. A table: worker id (`bx_...`), item, gate exit code, minutes, cost, deleted (yes).
2. The base: id, revision, state (stopped).
3. The pull requests the landing produced, and each item that did not finish, with its reason.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
