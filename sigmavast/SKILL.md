---
name: sigmavast
description: 'Use when asked for sigmavast or to rent a GPU (vast.ai and other clouds) for one job through lacompute: pick the card, keep the spend cap, prove the teardown. Do not use for CPU sandboxes (SigmaBoat) or local GPUs.'
---

# SigmaVast

Rent a GPU for one job with `lacompute`, run the job, and prove the machine is gone. Every rental, start to teardown, goes through `lacompute`: it checks the price cap, names the machine, records the spend and deletes it at the end. `lacompute --help` names its guide; `lacompute config` shows the cap and the key paths. Not on PATH: look where the agent instructions or the toolkit checkout say. No `lacompute`, no rental: say so.

No card, price or cap is a rule here: read today's offers and the job's needs.

## 1. Settle the job

A rental needs four facts: the job, its length, the spend cap, and which data leaves the machine. Use what the owner gave. If he is there, ask the missing ones in one short round. If he said "do it overnight" or is away, take these defaults and name them in the final response (a fact he gave always wins):

- Job: the work you were given (loop file, issue, spec). None: stop, there is nothing to rent for.
- Length: the job's own estimate plus 25 %. No estimate: a smoke test first (`-- nvidia-smi`, `--max 10m`), then size the real run from it.
- Cap: the one `lacompute config` shows. Never raise it.
- Data: only what the job's own code fetches. No key reaches the machine by any route: not in `--env`, not in the job string, not in a file. No private repo copy, no `--repo`.

Rent only when the job needs a GPU, or more GPU memory than the local machines have free, and the owner asked for the run. CPU work goes to SigmaBoat; a job a local GPU can take stays local; the smoke test is the only rental to "try" a command.

## 2. Read today's offers

- Size by the model's memory need: weights (parameters x bytes per parameter) + KV cache or activations + about 20 % headroom. `-s NNgb` asks for that much.
- Read the offers now (`vastai search offers` with the owner's offer filter, the line in `~/.config/lazy/vast-offers.txt`); a card or price from memory or an older run is stale.
- Take the cheapest offer that fits the memory and the length, with hourly price x length under the cap. `lacompute` prints the price before the start.
- The offer filter must exclude China: `notin [CN]` in its line. No file, or no such line: stop and say so. Never loosen it.

## 3. Check before the start

```sh
lacompute check     # can each provider rent now? one line each, with the fix
lacompute config    # max_per_hour, max_per_day and where each came from
lacompute cost      # money spent so far
```

- The cap is the owner's; `lacompute` refuses a start above it. Never raise it yourself.
- A provider that cannot rent: apply the fix `check` prints, or take another provider `lacompute` supports that fits the job.
- **Login code.** When `check` says vast.ai needs 2FA, ask the owner for the code from his email and run the two `vastai tfa` steps in the guide (Owner steps). Never print the code back.

## 4. Run

```sh
lacompute -t gpu -s <NN>gb --max <time> --get <outputs> -- '<job>'
lacompute -t gpu -s <NN>gb --max <time> --detach -- '<job>'   # long job; lacompute logs -f follows it
```

- The job fetches its own code and inputs. `--repo` would copy the GitHub token to the rented machine.
- `--env` values show on command lines: settings only, never a key.
- `--max` is the provider-side end: the job's real length plus a margin.

## 5. Tear down and prove it

`lacompute` deletes the machine when the job ends. Prove it, printing named fields only:

```sh
lacompute list --json | python3 -c 'import json,sys; print([m.get("name") for m in json.load(sys.stdin)["machines"]])'
vastai show instances --raw | python3 -c 'import json,sys; print([i.get("id") for i in json.load(sys.stdin) if str(i.get("label","")).startswith("lc-")])'
```

Both must print `[]`. A leftover: `lacompute kill-all`, then check again.

**Never print a raw instance listing** (`vastai show instances --raw` whole): its `onstart` field holds an API key (a real run printed one). Filter to named fields every time. If a key was printed anyway, say so and ask the owner to rotate it.

## Docs

Read before you guess a flag, a filter or a price: https://docs.vast.ai (page list `/llms.txt`; add `.md` to a page for plain text), or the copy in `docs/vendor/Vast_docs/` of the toolkit checkout that holds `lacompute`. The pages that matter: `cli/reference/search-offers.md`, `cli/reference/create-instance.md`, `guides/instances/pricing.md`. Both unreachable: try the context7 MCP, a web search or `vastai <command> --help`, and say which route answered. A worker's brief gets these addresses.

## Final response

1. The job, the card (GPU, memory, region), minutes and cost of this run.
2. Spend to date against the cap, from `lacompute cost`.
3. The teardown proof: both lists printed `[]`.
4. The defaults you took (section 1), or "owner gave the details".
5. What did not finish, with its reason.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
