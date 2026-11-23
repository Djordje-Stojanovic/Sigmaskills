---
name: sigmacollab
description: 'Use when asked for sigmacollab, Colab, sigmavast or to rent compute for one job: a Google Colab runtime (CPU, High-RAM, GPU, TPU) paid in plan units, or a vast.ai GPU through lacompute when Colab refuses. Shows the price, proves the teardown. Do not use for CPU dev boxes (SigmaBoat) or local GPUs.'
---

# SigmaCollab

Run one job on rented compute, then prove the machine is gone. Google Colab comes first: a Google AI or Colab plan pays for its compute units, and its CPU costs less than a boat box. Vast.ai through `lacompute` is the second provider: for a card Colab refuses, or a job Colab's rules forbid.

No card, price or plan size is a rule here. Read them from the CLI and the lab's config.

## 1. Settle the job

A run needs four facts: the job, its length, the cap (units or money), and which data leaves the machine. Use what the owner gave. If he is there, ask the missing ones in one short round. If he is away, take these defaults and name them in the final response:

- Job: the work you were given (loop file, issue, spec). None: stop, there is nothing to run.
- Length: the job's own estimate plus 25 %. No estimate: a one-minute smoke test first, then size the real run from it.
- Cap: for Colab, the units the owner named, else at most 5 % of today's balance; for Vast, the cap `lacompute config` shows. Never raise a cap or buy units.
- Data: only what the job's own code fetches. No key reaches a rented machine: not the Google sign-in, not a token in the job, not a file.

Rent only when the owner or the spec asked for the run and no local machine can take it.

## 2. Colab's rules

Colab forbids, and a job that needs one goes to Vast or stays local: file hosting, media serving, remote proxies, crypto mining, password cracking, torrents, several accounts to get around limits, containers to get around its checks. Creating deepfakes is on Colab's restricted list. SSH and background work are allowed only while the unit balance is positive. Units arrive each month. Colab ends an idle runtime, and any runtime after 12 hours (24 hours with background execution).

## 3. Sign in, once per machine

- Install the [Colab CLI](https://github.com/googlecolab/google-colab-cli) (`uv tool install google-colab-cli`; the lab guide pins a revision) and the Google Cloud CLI.
- `gcloud auth application-default login --no-launch-browser --disable-quota-project --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory`. The owner opens the link and picks the account that holds the plan; ask for the code with a secret card, never in chat.
- His other machines: copy the sign-in file (`~/.config/gcloud/application_default_credentials.json`; Windows `%APPDATA%\gcloud\`) over SSH, piped, never printed: `ssh -n A 'cat FILE' | ssh B 'umask 077; mkdir -p DIR; set -o noclobber; cat > FILE'`. Never to a rented machine, a repo or a log.
- Check: `colab --auth adc usage` prints the balance, the rate per hour and the active runtimes.

## 4. Pick the card, show the price

- The names: `colab new --help`. The cards this account may use: `eligibleGpus` and `eligibleTpus` in `colab --auth adc --logtostderr usage`.
- Size by memory: weights + cache or activations + about 20 %. Take the cheapest card that fits; CPU or High-RAM when the job needs no accelerator.
- Show the price before the start: units per hour from the lab's rates file (the wrapper prints it), times the length. A card with no rate: its `rate now` in the first minute is the price; write it into the rates file.
- What one account saw on each card: [references/cards.md](references/cards.md). A dated record, not a promise.

## 5. Run

The lab's wrapper first: search the agent instructions for "colab" and run what they name with `-h` (the toolkit's is `lacolab`). Without one, `colab run` starts a runtime, runs one script and stops it, also when the script fails:

```sh
colab --auth adc run -s JOB-NAME --gpu L4 --timeout 0 job.py ARGS   # --tpu V6E1, --high-mem, nothing for CPU
colab --auth adc new -s JOB-NAME --gpu L4   # for several steps: upload, exec, download, then stop -s JOB-NAME
```

- Name every runtime of the job; touch only those names. Other workers' runtimes are not yours: never `stop --all`.
- `colab exec` can exit 0 when the remote code raised: print a marker at the end and check for it.
- A refusal ("Service Unavailable", a card not eligible): record the exact text and take the next card, or Vast.

## 6. Vast, the second provider

Every Vast rental goes through `lacompute`: it checks the price cap, names the machine and deletes it at the end. `lacompute --help` names its guide. No `lacompute`, no Vast rental: say so.

- Read today's offers (`vastai search offers` with the owner's filter line in `~/.config/lazy/vast-offers.txt`). The filter must exclude China (`notin [CN]`); no such line: stop.
- `lacompute check`, `lacompute config`, `lacompute cost` before the start. vast.ai asks for a login code: ask the owner, run the `vastai tfa` steps of the guide, never print the code.
- `lacompute -t gpu -p vastai -s RTX4090 --max <time> --get <outputs> -- '<job>'`. No `--repo` (it copies the GitHub token); `--env` holds settings, never a key.
- Docs: https://docs.vast.ai (`/llms.txt`), or `docs/vendor/Vast_docs/` of the toolkit checkout.

## 7. Tear down and prove it

- Colab: `colab --auth adc sessions` no longer lists your names (other workers' rows may stay). `usage` before and after gives the units.
- Vast: your machine is absent from `lacompute list --json` and from `vastai show instances --raw`, each filtered to named fields. Never print a raw instance listing: its `onstart` field can hold a key.

## Final response

1. The job, the provider, the card (memory), the minutes and the units or money.
2. The balance or spend to date against the cap.
3. The teardown proof: your names absent from the lists.
4. The defaults you took (section 1), or "owner gave the details".
5. What did not finish, with its reason.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
