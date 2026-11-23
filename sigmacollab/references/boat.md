# boat.dev: boxes, workers and the base

Cloud machines on [boat.dev](https://boat.dev): Linux sandboxes, no GPU, rented by the second. Three kinds, told apart by name:

| Kind | Name | Life |
|---|---|---|
| **base** | `base` | stays stopped; holds tools, agent setup and repos, **no key**; only copied |
| **box** | `box-REPO` | a copy of the base for one task; ends merged and deleted |
| **worker** | `worker-REPO` | a copy of the base for one command; deleted when it ends |

This file makes them, watches them, keeps the base current, and leaves nothing running that nobody needs.

## Operating contract

- **Explicit only.** Start a box or a worker only when the user's message or the spec asks for a cloud machine or names boat.
- **Find the route.** The boat CLI, as in "The CLI" below. A lab wrapper that the agent instructions
  name (`AGENTS.md`, `CLAUDE.md`) may add accounts or agent-UI links: use it there. When a command fails or a flag is unclear, find 2-3 other ways to the same answer:
  `boat <command> --help`, the docs (https://docs.boat.dev, page list `/llms.txt`, add `.md` to a page for plain text), the
  boat API. Read before you guess a flag, a price or a limit, and say which route worked.
- **No key on the base.** The base runs with nothing of the owner's injected (`--no-env`), so its disk and snapshot hold no
  secret and no copy inherits one. A box gets its keys when it starts: over stdin, or from a boat environment. A login (Claude,
  Codex, `gh`) is a secret too. Keys go on stdin; print none; write none into a repo, a log, a pull request or a report.
- **Your sandboxes only.** A sandbox whose name is none of the three kinds belongs to the owner: never stop, change or delete it.
- **Pushed before deleted.** A box is deleted only after step 4 of the box flow passes.

## The box flow

1. **Make it.** Copy the base, give the copy its keys, set an auto-stop (boat's deadline, the safety net: 8 hours is a good
   default), pull the repo to the newest main, make the task's branch (`issue-N` for an issue). If the lab links boxes into an
   agent UI, the wrapper does it here.
2. **Work.** In the repo on the box: the change, the repo's own checks, the docs the change touches, commits.
3. **Open the pull request.** Push the branch; the body says `Closes #N` for an issue. Send the preview when there is one.
4. **Check.** On the box, `git status --porcelain` is empty and `git log --branches --not --remotes --oneline` prints only the
   task's branch, pushed as it is. Any other output: push it, or ask the owner.
5. **Land.** Merge by the repo's rules (squash unless it says otherwise; SigmaShip for a ship issue), delete the branch, then
   the box. The issue closes with the merge. Report the box id as deleted.

A pause: stop the box, start it later (the disk stays; the start moves its auto-stop).

**Preview.** Run the app on the box bound to `0.0.0.0` and give the owner a private address and port (the lab's private network
name when it joins boxes to one; else boat's `boat host ID PORT` URL, which is token-gated `--private` by default; pass `--public`
only after asking the owner). Send it before the merge.

## Watch

List every sandbox at the start and the end of every boat task, and whenever the user asks what runs. Then, per row:

- box whose pull request is merged or closed: step 4, then delete it;
- box you cannot tie to an open task, or running for hours with no work: warn the owner (id, repo, age, state; it bills until
  it stops); delete only on the owner's word;
- base running: an update failed or is running: finish it, or stop the base;
- worker: delete it (workers live one command);
- any other name: leave it, it is the owner's.

## The base

- **Update it** when the owner asks, after a change to the agent setup, or when it is a month old: start it, copy the agent
  setup (pinning the coding agents to the host's live versions and carrying the agent settings; check `<wrapper> -h` if the lab
  wrapper also has a `setup` command), pull and install every repo in it, stop it, save its snapshot again. Nobody works on it
  between updates.
- **Add a repo:** clone it during an update. Each repo installs from its own files (`.boat/setup.sh`, else its lockfiles).
- **A key changed:** the base stays as it is; boxes get the new keys at their next start.
- The base never joins a private network or serves an agent UI: every copy would share that identity.

## Workers

For a loop file, an issue with acceptance criteria or a spec the user already authorized. The host runs the work; this flow
supplies the machines. Workers = min(free slots, starts left today, ready items). Start them one at a time (boat never queues a
start), each a copy of the base with a 2-hour auto-stop and one command on its own branch. Fetch each branch back, land it by
the rules of the invoked work, and delete every worker at the end.

## Report of a boat task

1. Every sandbox this flow made or touched: id, kind, repo, task, state (deleted, stopped, running with its reason).
2. The pull requests, and each item that did not finish, with its reason.
3. The warnings from Watch, if any.

## The CLI

The flow above with the plain boat CLI (`boat <command> --help` for every flag). `ID` is a `bx_` id. Each fact names
the docs page that holds it (https://docs.boat.dev/PAGE.md).

## Keys: stdin, or a boat environment

The base and every copy run with `--no-env`: boat injects nothing of the owner's, and its own GitHub token (which reaches only the
repos its GitHub app may see, and replaces the `gh` login) stays out. Each box then gets the keys file when it starts:

```sh
base64 -w0 < "$KEYS_FILE" | boat ssh ID -- 'umask 077; base64 -d > ~/.box-keys'   # stdin, never an argument
```

On the box: `gh auth login --with-token` from the keys file, then `gh auth setup-git`.

With an API key that has `environment.write` (a `ci` key has none, `api-keys/scopes.md`), boat can hold the keys instead: once
`boat env new boxes && boat env set boxes --github false --secrets true`, then `boat env set-file boxes .box-keys < "$KEYS_FILE"`
after each key change, and fork boxes with `--environment boxes` in place of `--no-env`. A sandbox takes the environment's latest
version when it starts (`environments/versions.md`).

## Commands

| Step | Command |
|---|---|
| make the base | `boat new --no-env --name base --json`, set it up, `boat stop ID`, `boat snapshot ID base` |
| update the base | `boat resume ID --no-env`, update, `boat stop ID`, `boat snapshot ID base` (the name is replaced) |
| make a box | `boat fork BASE_ID --no-env --ttl 28800 --wait --json`, `boat rename NEW box-REPO`, then the keys |
| make a worker | the same fork with `--ttl 7200`, renamed `worker-REPO` |
| run a command | `boat exec ID --timeout 0 -- CMD` (the default timeout is 30 s) |
| move the auto-stop | `boat extend ID --ttl SECONDS` |
| pause, come back | `boat stop ID`, `boat resume ID --ttl SECONDS` |
| preview | `boat host ID PORT` (token-gated `--private` by default; add `--public` only after asking the owner) |
| watch | `boat list --all --json`, `boat limits --all` |
| delete | `boat delete ID --yes` |

## Facts that shape the work

- **Auto-stop is a deadline, not an idle timer** (`long-running-tasks/auto-stop.md`). It counts from the start or the last resume;
  `exec`, SSH and agent work never move it. Nothing starts a stopped sandbox by itself (`readiness.md`).
- **Stop keeps the disk, ends every program** (`snapshots/stop.md`). Enabled systemd services start again on resume; anything
  started by hand does not. The IP address and the SSH host key change.
- **A stopped disk is kept at least 14 days; a saved snapshot has no end** (`snapshots/templates.md`). Saving under a name that
  exists replaces it.
- **A fork copies the latest snapshot** (`snapshots/resume-and-fork.md`), every file on the disk included. A snapshot of a
  sandbox that ran with secrets can hold them (`environments/access.md`): that is why the base runs with `--no-env`.
- **Starts are counted** per minute, hour and day and never queued (`limits.md`).
- Sizes and prices: `pricing.md`; `boat limits --all` reads the live numbers.
