---
name: sigmaboat
description: 'Use when asked for sigmaboat or a cloud box: work a task of any repo on a boat.dev box, watch, delete or update boxes and the base, preview a dev server from a box, or run authorized work (loop file, ship issue, spec) on boat workers. Do not use to plan work (SigmaLoop) or for GPU jobs (SigmaVast).'
---

# SigmaBoat

Cloud machines on [boat.dev](https://boat.dev): Linux sandboxes, no GPU, rented by the second. Three kinds, told apart by name:

| Kind | Name | Life |
|---|---|---|
| **base** | `base` | stays stopped; holds tools, agent setup and repos, **no key**; only copied |
| **box** | `box-REPO` | a copy of the base for one task; ends merged and deleted |
| **worker** | `worker-REPO` | a copy of the base for one command; deleted when it ends |

SigmaBoat makes them, watches them, keeps the base current, and leaves nothing running that nobody needs.

## Operating contract

- **Explicit only.** Start a box or a worker only when the user's message or the spec asks for a cloud machine or names boat.
- **The lab's wrapper first.** Before the first command, look for the lab's boat guide, if this machine has one: search the agent
  instructions (`AGENTS.md`, `CLAUDE.md`) for "boat" and run the wrapper they name with `-h` (a lab may wrap boat in one command,
  such as `laboat`). The wrapper and the guide win over this skill: they hold the account, the repos, the machines and the
  commands. With no wrapper, use the boat CLI as in [references/boat.md](references/boat.md).
- **Keys live in a boat environment, never on the base.** boat injects an environment's variables and secret files into each
  sandbox at its start; the base runs in an environment that injects nothing, so its disk and snapshot hold no secret and no fork
  inherits one. A login (Claude, Codex, `gh`) is a secret too. Pass keys on stdin; print none; write none into a repo, a log, a
  pull request or a report.
- **Your sandboxes only.** A sandbox whose name is none of the three kinds belongs to the owner: never stop, change or delete it.
- **Pushed before deleted.** A box is deleted only after step 4 of the box flow passes.
- **Docs.** https://docs.boat.dev (page list `https://docs.boat.dev/llms.txt`; add `.md` to a page for plain text). Read the page
  before you guess a flag, a price or a limit.

## Branches

| The user wants | Go to |
|---|---|
| a task done on a box ("a box for this repo", "work issue 12 on boat") | The box flow |
| to try a running app before the merge | Preview |
| what runs, what costs, what to clean up | Watch |
| the base current, a repo added to it | The base |
| a loop file, ship issue or spec run on parallel workers | Workers |

## The box flow

1. **Make it.** Copy the base into the keys environment, with an auto-stop (boat's deadline, the safety net: 8 hours is a good
   default), pull the repo to the newest main, make the task's branch (`issue-N` for an issue). If the lab links boxes into an
   agent UI (T3 Code and similar), the wrapper does it here.
2. **Work.** In the repo on the box: the change, the repo's own checks, the docs the change touches, commits.
3. **Open the pull request.** Push the branch; the body says `Closes #N` for an issue. Send the preview (below) when there is one.
4. **Check.** On the box, `git status --porcelain` is empty and `git log --branches --not --remotes --oneline` prints only the
   task's branch, pushed as it is. Any other output: push it, or ask the owner.
5. **Land.** Merge by the repo's rules (squash unless it says otherwise; SigmaShip when the work came as a ship issue), delete
   the branch, then delete the box. The issue closes with the merge. Report the box id as deleted.

A pause: stop the box, later start it again (the disk stays). Starting it again also moves its auto-stop.

## Preview

Run the app on the box bound to `0.0.0.0` and give the owner the box's private network address and port (a tailnet name when
the lab joins boxes to Tailscale; boat's own `boat host` URL otherwise, which is public: ask first). Send it before the merge, so
the owner tries the change first.

## Watch

List every sandbox at the start and at the end of every boat task, and whenever the user asks what runs. Then act on each row:

| Row | Do |
|---|---|
| box, its pull request merged or closed | step 4, then delete it |
| box you cannot tie to an open task | warn the owner: id, repo, age, state; delete only on the owner's word |
| box running for hours with no work | warn the owner: it bills until it stops |
| base, running | an update failed or is running: finish it, or stop the base |
| worker | delete it (workers live one command) |
| any other name | nothing: it is the owner's |

The final report lists every box still running, with its task.

## The base

- **Update it** when the owner says "update the base", after a change to the agent setup, or when it is a month old: start it,
  copy the agent setup, pull and install every repo in it, stop it, save its snapshot again (the backup). Nobody works on it
  between updates.
- **Add a repo:** clone it during an update. Each repo installs from its own files (`.boat/setup.sh`, else its lockfiles), so
  nobody keeps a repo list.
- **A key changed:** save the keys again into the keys environment; the base stays as it is. New boxes get the new keys.
- The base never joins a private network or serves an agent UI: every copy would share that identity.

## Workers

For a loop file, an issue with acceptance criteria or a spec that the user already authorized. SigmaBoat writes no plan; the host
runs the work and SigmaBoat supplies the machines. Workers = min(free slots, starts left today, ready items). Start them one at a
time (boat never queues a start), each a copy of the base with a 2-hour auto-stop and one command on its own branch. Fetch each
branch back, land it by the rules of the work that was invoked, and delete every worker at the end.

## Final response

1. Every sandbox SigmaBoat made or touched: id, kind, repo, task, state (deleted, stopped, running with its reason).
2. The pull requests, and each item that did not finish, with its reason.
3. The warnings from Watch, if any.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
