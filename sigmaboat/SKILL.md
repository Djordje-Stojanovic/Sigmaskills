---
name: sigmaboat
description: 'Use when asked for sigmaboat or to run authorized work (loop file, ship issue, spec) on boat.dev sandboxes: base once, fork per worker, delete. Do not use to plan work (SigmaLoop) or by default.'
---

# SigmaBoat

Give work the user already authorized extra machines: [boat.dev](https://boat.dev) sandboxes (full Ubuntu VMs, no GPU). SigmaBoat builds one stopped base per repo, forks one sandbox per worker, runs each worker's gate there, lands the result by the work's own rules, and deletes every sandbox it started. The host runs the work with its own mechanism (subagents, threads, `/goal`); SigmaBoat only supplies and cleans up the machines.

## Operating contract

- **Explicit only.** Start a sandbox only when the user's message or the spec names boat. Never by default, never for GPU work or renders.
- **Authorized work only.** The input is a loop file, an issue with acceptance criteria, a speed-loop project or a spec. SigmaBoat writes no plan: SigmaLoop writes prompts, SigmaShip ships tickets. The host runs that work with its own mechanism; SigmaLoop stays a prompt writer.
- **No cost guard of ours.** boat's auto-stop is the control. Read the live limits; do not invent a budget.
- **Secrets.** Read `BOAT_API_KEY` from the environment or a secrets file named by path. Sign in with `--key-stdin`. Pass a worker's tokens (for example `GH_TOKEN`) with `-e KEY=VALUE` on its fork, never into the base. Never print a value.
- **Delete what you start.** At the end, and after any failure, every worker is gone. Keep only stopped bases.

## Facts that change commands

- `boat exec` stops a command after 30 s unless you pass `--timeout`; `0` means no limit.
- Piped or captured, every command prints JSON (`--json` turns on by itself). Read ids from the `ready` event of `boat new --json`.
- Auto-stop counts from start or resume. Only a running `boat prompt` extends it; `exec`, SSH and threads do not. Set `--ttl` on every `new` and `fork`.
- A fork copies the whole disk of the source's newest snapshot. Fork only a stopped base (`boat info` says `stopped`), and never put a Tailscale, T3 or secret identity on a base.
- Free trial: 2 sandboxes at once, `--ttl` at most 7200, sizes `small` and `default`, no saved snapshots. Read the real numbers with `boat limits --json`.

## 1. Sign in and read the limits

```sh
printf '%s' "$BOAT_API_KEY" | boat login --key-stdin --json   # POSIX
boat limits --json
```

```powershell
$env:BOAT_API_KEY | boat login --key-stdin --json             # Windows PowerShell
boat limits --json
```

From the JSON take: the active-sandbox maximum minus the running ones (the worker slots), the machine types that are `available`, and the trial line. Workers = min(slots, ready items).

## 2. Build or reuse the base

Look for `base-<repo>` in `boat list --filter sr --json`. Reuse it when it is stopped and its recorded revision is the one the work needs. Otherwise:

```sh
boat new --ttl 7200 --name base-<repo> --json          # id from the "ready" event
boat exec <base> --timeout 0 -- git clone <url> <repo>
boat exec <base> --cwd <repo> --timeout 0 -- <install command>
boat exec <base> --cwd <repo> --timeout 0 -- <gate command>   # once, to prove the base is green
boat exec <base> -- du -sh <repo>                             # report the disk use
boat stop <base>
boat info <base> --json                                       # repeat until the state is stopped
```

Clone public repos anonymously, or pass a token with `-e GH_TOKEN=...` on `new` and remove any credential file before `stop`. A base holds no secret on its disk.

## 3. Fork the workers

```sh
boat fork <base> --ttl 7200 --wait --json -e GH_TOKEN=<value>   # id from the "ready" event
```

One fork per worker, at most the free slots. A failed fork is retried once with `--fail-fast`; then that item waits for a free slot.

## 4. Run each worker's item

The host's worker (subagent, thread or loop step) does the item. Commands it runs on its sandbox:

```sh
boat exec <id> --cwd <repo> --timeout 0 -- git switch -c <branch>
boat exec <id> --cwd <repo> --timeout 0 -- <command>
boat exec <id> --cwd <repo> --timeout 0 -- <gate command>   # the item's own check; keep its exit code
boat ssh <id>                                               # an interactive shell when needed
```

A worker whose job may pass the 2 h auto-stop on the trial splits it, or stops and resumes with `boat resume --ttl 7200 <id>`.

## 5. Land

Follow the landing rules of the work that was invoked (the loop file, SigmaShip, the spec): push the branch from the sandbox, open the pull request, merge only if that work authorizes it. SigmaBoat adds no landing rule of its own.

## 6. Collect usage and delete

For every worker, also after a failure:

```sh
boat usage <id> --json
boat delete <id> --yes --json
boat list --all --json      # only base-* remain
```

## Final response

1. A table: worker id, item, gate exit code, minutes, cost from `boat usage`, deleted (yes).
2. The base: id, revision, disk use, state (stopped).
3. What the work's own landing produced (pull request links), and any item that did not finish, with its reason.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
