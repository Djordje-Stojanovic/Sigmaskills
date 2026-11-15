---
name: sigmavast
description: 'Use when asked for sigmavast or to rent a GPU (vast.ai and other clouds) for one job through lacompute: pick the card, keep the spend cap, prove the teardown. Do not use for CPU sandboxes (SigmaBoat) or local GPUs.'
---

# SigmaVast

Rent a GPU for one job with `lacompute`, run the job, and prove the machine is gone. Every rental, start to teardown, goes through `lacompute`: it checks the price cap, names the machine, records the spend and deletes it at the end. `lacompute --help` and `lacompute config` show the settings (the cap, the key paths). The guide named in `lacompute --help` explains the rest.

This skill types no card, no price and no cap as a rule. It reads today's offers and the job's needs.

## 1. Settle the job

A rental needs four facts: the job, its length, the spend cap, and which data leaves the machine.

- **The owner gave them:** use them. Ask only about what is missing.
- **The owner gave none and is there to answer:** ask one short round, all four at once: what job, how long, what spend cap, which data leaves the machine. Then go.
- **The owner said "do it overnight" (or "do stuff"), or is not there:** do not wait. Take these defaults for each fact the owner did not give. A fact the owner gave always wins. Say which defaults you took in the final response:
  - Job: the work you were given (loop file, issue, spec). None: stop, there is nothing to rent for.
  - Length: the job's own estimate plus 25 %. No estimate: a smoke test first (`-- nvidia-smi`, `--max 10m`), then size the real run from what it showed.
  - Cap: the one `lacompute config` shows. Never raise it.
  - Data: only what the job's own code fetches. No key reaches the machine by any route: not in `--env`, not in the job string, not in a file. No private repo copy, no `--repo`.

Rent only when the job needs a GPU, or more GPU memory than the local machines have free, and the owner asked for the run. Do not rent for CPU work (SigmaBoat), for a job a local GPU can take, or to "try" a command (the smoke test of section 1 is the one exception).

## 2. Read today's offers

- Size by the model's memory need: weights (parameters x bytes per parameter) + KV cache or activations + about 20 % headroom (a rule of thumb). `-s NNgb` asks for that much GPU memory.
- Read the offers now: `vastai search offers` with the owner's offer filter, the line in `~/.config/lazy/vast-offers.txt`. Never use a card or price from memory or from an older run.
- Take the cheapest offer that fits the memory need and the length, with hourly price x length under the cap. `lacompute` prints the price before the start.
- The offer filter must exclude China: `notin [CN]` in its line of `~/.config/lazy/vast-offers.txt`. No file, or no such line: stop and say so. Never loosen it.

## 3. Check before the start

```sh
lacompute check     # can each provider rent now? one line each, with the fix
lacompute config    # max_per_hour, max_per_day and where each came from
lacompute cost      # money spent so far
```

- The cap is the owner's. A start above it is refused by `lacompute`. Never raise it yourself.
- **Login code.** When `check` says vast.ai cannot rent (2FA), stop and ask the owner for the code from his email. Then run the two `vastai tfa` steps in the guide (Owner steps). Never print the code back.

## 4. Run

```sh
lacompute -t gpu -s <NN>gb --max <time> --get <outputs> -- '<job>'
lacompute -t gpu -s <NN>gb --max <time> --detach -- '<job>'   # long job; lacompute logs -f follows it
```

- The job fetches its own code and inputs. Do not pass `--repo`: it copies the GitHub token to the rented machine.
- `--env` values show on command lines: settings only, never a key.
- `--max` is the provider-side end. Set it to the job's real length plus a margin.

## 5. Tear down and prove it

`lacompute` deletes the machine when the job ends. Prove it, printing named fields only:

```sh
lacompute list --json | python3 -c 'import json,sys; print([m.get("name") for m in json.load(sys.stdin)["machines"]])'
vastai show instances --raw | python3 -c 'import json,sys; print([i.get("id") for i in json.load(sys.stdin) if str(i.get("label","")).startswith("lc-")])'
```

Both must print `[]`. A leftover: `lacompute kill-all`, then check again.

**Never print a raw instance listing** (`vastai show instances --raw` as a whole): its `onstart` field holds an API key (a real run printed one). Filter to named fields every time. If a key was printed anyway, say so in the report and ask the owner to rotate it.

## Docs

Live: https://docs.vast.ai (page list: https://docs.vast.ai/llms.txt; add `.md` to a page address for plain text). Once `lasynctoolkit` has mirrored them, the toolkit checkout that holds `lacompute` and its guide keeps a copy in `docs/vendor/Vast_docs/`. Read `cli/reference/search-offers.md` (every offer filter field), `cli/reference/create-instance.md` and `guides/instances/pricing.md` in either place before you guess a flag, a filter or a price. When you brief a worker agent, paste these two addresses and the `docs/vendor/Vast_docs/` path into its brief.

## Final response

1. The job, the card (GPU, memory, region), minutes and cost of this run.
2. Spend to date against the cap, from `lacompute cost`.
3. The teardown proof: both lists printed `[]`.
4. The defaults you took (section 1), or "owner gave the details".
5. What did not finish, with its reason.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
