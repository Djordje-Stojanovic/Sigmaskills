---
name: sigmacollab
description: 'Use when asked for sigmacollab, Colab, sigmavast or to rent compute for one job: a Google Colab runtime (CPU, High-RAM, GPU, TPU) paid in plan units, or a vast.ai GPU when Colab refuses. Drives the colab and vastai CLIs, shows the price, proves the teardown. Do not use for CPU dev boxes (SigmaBoat) or local GPUs.'
---

# SigmaCollab

Run one job on rented compute, then prove the machine is gone. Google Colab comes first: a Google AI or Colab plan pays for its compute units, and its CPU costs less than a boat box. vast.ai is the second provider: for a card Colab refuses, or a job Colab's rules forbid. Both are driven by their own CLIs, `colab` and `vastai`; read `--help` and the docs before you guess a flag.

No card, price or plan size is a rule here. Read them from the CLI and from [references/cards.md](references/cards.md).

## 1. Settle the job

A run needs four facts: the job, its length, the cap (units or money), and which data leaves the machine. Use what the owner gave. If he is there, ask the missing ones in one short round. If he is away, take these defaults and name them in the final response:

- Job: the work you were given (loop file, issue, spec). None: stop, there is nothing to run.
- Length: the job's own estimate plus 25 %. No estimate: a one-minute smoke test first, then size the real run from it.
- Cap: for Colab, the units the owner named, else at most 5 % of today's balance; for Vast, the dollars per hour he named, else stop and ask. Never raise a cap or buy units.
- Data: only what the job's own code fetches. No key reaches a rented machine: not the Google sign-in, not a token in the job, not a file.

Rent only when the owner or the spec asked for the run and no local machine can take it.

## 2. Colab's rules

From [Colab's FAQ](https://research.google.com/colaboratory/faq.html#disallowed-activities). A job that needs one of these goes to Vast or stays local: file hosting, media serving or other web services, torrents and peer-to-peer sharing, remote proxies, crypto mining, denial-of-service attacks, password cracking, several accounts to get around limits, creating deepfakes, containers to get around its checks. SSH and other remote control are allowed only while the unit balance is positive. Units arrive each month. Colab ends an idle runtime, and any runtime after 12 hours (24 hours of running code with background execution).

## 3. Sign in, once per machine

- Install the [Colab CLI](https://github.com/googlecolab/google-colab-cli) (`uv tool install google-colab-cli`) and the Google Cloud CLI.
- `gcloud auth application-default login --no-launch-browser --disable-quota-project --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory`. The owner opens the link and picks the account that holds the plan; ask for the code with a secret card, never in chat.
- His other machines: copy the sign-in file (`~/.config/gcloud/application_default_credentials.json`; Windows `%APPDATA%\gcloud\`) over SSH, piped, never printed: `ssh -n A 'cat FILE' | ssh B 'umask 077; mkdir -p DIR; set -o noclobber; cat > FILE'`. Never to a rented machine, a repo or a log.
- Check: `colab --auth adc usage` prints the balance, the rate per hour and the active runtimes. Vast: `vastai set api-key` once; account calls may need the emailed login code (`vastai tfa`), which only the owner can read.

## 4. Pick the card, show the price

- The names: `colab new --help`. The cards this account may use: `eligibleGpus` and `eligibleTpus` in `colab --auth adc --logtostderr usage`.
- Size by memory: weights + cache or activations + about 20 %. Take the cheapest card that fits; CPU or High-RAM when the job needs no accelerator.
- Show the price before the start: units per hour from [references/cards.md](references/cards.md), times the length. A card with no rate there: the change in `usage`'s rate in its first minute is the price; add it to the file.

## 5. Run on Colab

`colab run` starts a runtime, runs one script and stops it, also when the script fails. For files in and out, keep the runtime and stop it yourself:

```sh
colab --auth adc run -s JOB-NAME --gpu L4 --timeout 0 job.py ARGS   # --tpu V6E1, --high-mem, nothing for CPU
colab --auth adc new -s JOB-NAME --gpu L4
colab --auth adc upload -s JOB-NAME inputs.zip content/inputs.zip
colab --auth adc exec -s JOB-NAME --timeout 0 -f job.py   # can exit 0 when the code raised: print a marker last, check it
colab --auth adc download -s JOB-NAME content/out.mp4 out.mp4
colab --auth adc stop -s JOB-NAME
```

- Name every runtime of the job; touch only those names. Other workers' runtimes are not yours: never `stop --all`.
- A refusal ("Service Unavailable", "Allocation refused"): record the exact text and take the next card, or Vast.

## 6. Run on Vast

- Find the offer with the cap and the place in the query: `vastai search offers 'num_gpus=1 gpu_ram>=24 dph_total<=CAP geolocation notin [CN] reliability>0.98 rentable=true' -o dph_total --raw`. The owner's own filter wins where he keeps one.
- Rent it with a label and an end on the machine itself: an `--onstart-cmd` that sleeps to the deadline, then runs `vastai destroy instance $CONTAINER_ID --api-key $CONTAINER_API_KEY`. That key is the instance's own and can only touch that instance (`guides/instances/docker-environment.md` in the docs).
- The job fetches its own code; settings go in, keys never do. `vastai copy` brings results back.
- Docs: https://docs.vast.ai (`/llms.txt`; add `.md` to a page). A lab wrapper the agent instructions name may add a price cap or a ledger: use it there.

## 7. Tear down and prove it

- Colab: `colab --auth adc sessions` no longer lists your names (other workers' rows may stay). `usage` before and after gives the units.
- Vast: `vastai destroy instance ID`, then `vastai show instances --raw` filtered to `id` and `label` shows yours gone. Never print a raw instance listing: its `onstart` field can hold a key.

## Final response

1. The job, the provider, the card (memory), the minutes and the units or money.
2. The balance or spend to date against the cap.
3. The teardown proof: your names absent from the lists.
4. The defaults you took (section 1), or "owner gave the details".
5. What did not finish, with its reason.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
