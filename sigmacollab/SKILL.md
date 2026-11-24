---
name: sigmacollab
description: 'Use when asked for sigmacollab, sigmaboat, sigmavast, Colab, a cloud box or to rent compute for one job: a Google Colab runtime first (CPU, High-RAM, GPU, TPU, any card the plan allows) paid in plan units, a vast.ai GPU when Colab refuses, or a boat.dev Linux box for what Colab cannot hold (boxes, workers, the base, a preview). Shows the price, proves the teardown. Do not use for local machines or local GPUs.'
---

# SigmaCollab

Run one job on rented compute, then prove the machine is gone. Take the providers in this order:

1. **Google Colab first,** for a GPU, a TPU, High-RAM or a CPU job, repo work included: a Google AI or Colab plan pays for its compute units, so it costs no extra money, and its CPU costs less than a boat box. Any card the plan lists, any model the job runs.
2. **vast.ai second:** a card Colab refuses or times out on (record the exact text, try the next card first), or a job Colab's rules forbid.
3. **boat.dev last:** what Colab cannot hold, such as a box that must outlive Colab's runtime limit, a dev server preview, or a box per worker. Read [references/boat.md](references/boat.md) and follow it; the sections below are for Colab and Vast.

Colab and vast.ai are driven by their own CLIs, `colab` and `vastai`; read `--help` and the docs before you guess a flag.

No card, price or plan size is a rule here. Read them from the CLI and from [references/cards.md](references/cards.md).

## 1. Settle the job

A run needs four facts: the job, its length, the cap (units or money), and which data leaves the machine. Use what the owner gave. If he is there, ask the missing ones in one short round. If he is away, take these defaults and name them in the final response:

- Job: the work you were given (loop file, issue, spec). None: stop, there is nothing to run.
- Length: the job's own estimate plus 25 %. No estimate: a one-minute smoke test first, then size the real run from it.
- Cap: for Colab, the units the owner named, else at most 5 % of today's balance; for Vast, the dollars per hour he named, else stop and ask. Never raise a cap or buy units.
- Data: only what the job's own code fetches. No key reaches a rented machine: not the Google sign-in, not a token in the job, not a file.

Rent only when the owner or the spec asked for the run and no local machine can take it.

## 2. Colab's rules

From [Colab's FAQ](https://research.google.com/colaboratory/faq.html#disallowed-activities). A job that needs one of these goes to Vast or stays local: file hosting, media serving or other web services, torrents and peer-to-peer sharing, remote proxies, crypto mining, denial-of-service attacks, password cracking, several accounts to get around limits, creating deepfakes, containers to get around its checks. SSH and other remote control are allowed only while the unit balance is positive. Units arrive each month. Colab ends an idle runtime, and any runtime after 12 hours (24 hours of running code with background execution). Colab Enterprise is a Google Cloud product priced in money per machine hour ([pricing](https://cloud.google.com/colab/pricing)); no page says plan units pay for it, so it is paid compute: only on the owner's word.

## 3. Sign in, once per machine

- Install the [Colab CLI](https://github.com/googlecolab/google-colab-cli) (`uv tool install google-colab-cli`) and the Google Cloud CLI.
- `gcloud auth application-default login --no-launch-browser --disable-quota-project --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory`. The owner opens the link and picks the account that holds the plan (on a Google One family plan, only the plan manager's account gets the units: [help](https://support.google.com/googleone/answer/16286513)); ask for the code with a secret card, never in chat.
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
- Before a big card, stop your own idle runtimes: they burn units, and it may clear a 412.
- A refusal: record the exact text and read it ([the CLI's own skill](https://github.com/googlecolab/google-colab-cli/blob/main/skills/colab-operator/SKILL.md), its `commands/session.py`, [#73](https://github.com/googlecolab/google-colab-cli/issues/73)):
  - `400`: this account may not use the card. Take one `usage` lists as eligible.
  - `412` "Allocation refused": too many active runtimes, or a temporary usage or capacity limit for that card; the answer does not say which. Stop your own idle runtimes, ask once more, then the next card.
  - `503` "Service Unavailable": the CLI has already retried it; the cause (no free card or an outage) is not in the answer. The next card.
  - "Bad Gateway", or a start that times out: the next card. The CLI can hang for minutes: give the request a long timeout (`colab --help` names it) and pick the second card before you start.
- Ask for a refused card once more at most, never in a loop. One user reported an account blocked for "suspected abusive activity" after an agent retried a refused G4 all night ([colabtools#6288](https://github.com/googlecolab/colabtools/issues/6288), 22 Nov 2026, no answer from Google). When the cards run out: Vast, or stop and report.

## 6. Run on Vast

- Find the offer with the cap and the place in the query: `vastai search offers 'num_gpus=1 gpu_ram>=24 dph_total<=CAP geolocation notin [CN] reliability>0.98 rentable=true' -o dph_total --raw`. The owner's own filter adds to it; `geolocation notin [CN]` stays in every query.
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
