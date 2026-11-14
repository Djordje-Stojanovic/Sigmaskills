---
name: sigmavast
description: 'Use when asked for sigmavast or to rent a GPU (vast.ai and other clouds) for one job through lacompute: pick the card, keep the spend cap, prove the teardown. Do not use for CPU sandboxes (SigmaBoat) or local GPUs.'
---

# SigmaVast

Rent a GPU for one job with `lacompute`, run the job, and prove the machine is gone. Every rental, start to teardown, goes through `lacompute`: it checks the price cap, names the machine, records the spend and deletes it at the end. `lacompute --help`, `lacompute config` and the guide it names hold the owner's own facts (cap, key paths, offer filter); read them there.

## When to rent

- Rent when the job needs a GPU or more GPU memory than the local machines have free, and the user asked for the run.
- Do not rent for CPU work (SigmaBoat), for a job a local GPU can take, or to "try" a command. A smoke test is `-- nvidia-smi` with `--max 10m`.

## 1. Pick the card

- Size by the model's memory need: weights (parameters x bytes per parameter) + KV cache or activations + about 20 % headroom. `-s NNgb` asks for that much GPU memory.
- Take the smallest size that fits. The price per hour grows with it, and `lacompute` prints it before the start.
- No hosts in China: `lacompute config` shows the offer filter; it must exclude `CN`. If it does not, stop and say so.

## 2. Check before the start

```sh
lacompute check     # can each provider rent now? one line each, with the fix
lacompute config    # max_per_hour, max_per_day and where each came from
lacompute cost      # money spent so far
```

- The cap is the owner's. A start above it is refused; never raise it yourself.
- **Login code.** When `check` says the provider needs a login code, stop. Ask the owner for the code through a secret card (the host's secret request), never in chat, then run the login command `check` names.

## 3. Run

```sh
lacompute -t gpu -s <NN>gb --max <time> --get <outputs> -- '<job>'
lacompute -t gpu -s <NN>gb --max <time> --detach -- '<job>'   # long job; lacompute logs -f follows it
```

- The job fetches its own code and inputs; `--repo` is not used for a GPU rental.
- `--env` values show on command lines: settings only, never a key.
- `--max` is the provider-side end. Set it to the job's real length plus a margin.

## 4. Tear down and prove it

`lacompute` deletes the machine when the job ends. Prove it, printing named fields only:

```sh
lacompute list --json | python3 -c 'import json,sys; print([m.get("name") for m in json.load(sys.stdin)["machines"]])'
vastai show instances --raw | python3 -c 'import json,sys; print([i["id"] for i in json.load(sys.stdin)])'
```

Both must print `[]`. A leftover: `lacompute kill-all`, then check again.

**Never print a raw instance listing** (`vastai show instances`, `--raw`, `lacompute list --json` unfiltered): its `onstart` line holds an API key. Filter to named fields every time. If a key was printed anyway, say so in the report and ask the owner to rotate it.

## Final response

1. The job, the card (GPU, memory, region), minutes and cost of this run.
2. Spend to date against the cap, from `lacompute cost`.
3. The teardown proof: both lists printed `[]`.
4. What did not finish, with its reason.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
