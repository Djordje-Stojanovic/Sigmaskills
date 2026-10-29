# Lessons from the first speed loop (la125 on a Vast GB10, 2026-10-22/23)

Every row cost real time or money once. Read all of them before renting a box.
Format: what happened -> what it cost -> the rule now.

## Contents
1. Spec and evaluator design
2. Vast.ai account and box
3. Engine bring-up (vLLM fork, b12x, GB10)
4. Scripts, shells and remote control
5. Running the loop
6. Interpreting results

---

## 1. Spec and evaluator design

**1.1 The first evaluator measured the wrong thing.** It ran greedy (T=0), short outputs (256 tokens),
thinking effort left at default, and the owner actually uses T=1.0, effort low/medium (sometimes xhigh),
max_tokens 65536. MTP spec decoding behaves very differently under greedy, so verdicts were wrong.
Cost: 4 passes and 8 runs thrown away, evaluator rebuilt 4 times (~6 hours).
Rule: pin the owner's real request settings in Phase 1 (sampling, thinking on/off, effort levels and
how their client maps names, max_tokens, streams, context sizes). Build v1 of the evaluator with them.

**1.2 Client effort names are remapped.** The owner said "high"; their agent client's config mapped high -> `xhigh`;
the chat template only accepts low/medium/xhigh. Read the client config (for the pi agent: `~/.pi/agent/models.json`,
`thinkingLevelMap`), never guess.

**1.3 The quality gate was too short at first** (8 texts, 12 prompts, 6 tool checks). The owner asked for
more. Final: ~75k teacher-forced positions incl. real agent text, 24 greedy prompts x 512 tokens, needles,
plus the full ToolEvalBench suite. Cheap things (teacher-forced prefill) scale well; generation does not.

**1.4 Homemade tool/JSON checks are redundant once ToolEvalBench runs.** Drop them, keep needles.

**1.5 The fidelity gate measures difference, not direction.** mbt 4096 shifted logprobs (top-1 agreement
87 %) while ToolEvalBench improved. Strict gate rejected a real win. Rule: get the owner's drift policy
in Phase 1 (strict, or "drift allowed if ToolEvalBench >= champion A/A min and needles pass").

**1.6 Temperature 1 makes everything noisy.** Agent replay varied 8 % between identical restarts, so the
keep floor became +6.1 %. Rules: >= 3 A/A runs (5 is better), confirmation re-run for every KEEP,
judge borderline ideas on a 2-run median, and say "inside noise" honestly.

**1.7 ToolEvalBench at T=1 is not deterministic.** Use it as a regression alarm (reject below A/A min
minus max(3, 2 x A/A range); with the owner's drift rule: drifted candidates need >= A/A min, no slack).

**1.8 Check for the newest ToolEvalBench on GitHub, not only PyPI.** 2.8.0 on PyPI, but `--hardmode`
has 97 scenarios (docs said 74) and GitHub main had a grading fix. Install pinned:
`pip install "git+https://github.com/SeraphimSerapis/tool-eval-bench.git@<commit>"`.

**1.9 `--context-fill-tokens 32768` made ToolEvalBench take 24 min** (median 32 s/scenario) and lowered
scores. Without fill, 97 scenarios at `--parallel 8` took ~9.4 min. The speed probes already cover long context.

## 2. Vast.ai account and box

**2.1 A 2FA session is required even with no 2FA method set up.** All account calls returned
"requires you to have logged in using Two Factor Authentication". Fix: `vastai tfa send-email`, the
owner reads the 6-digit code, `vastai tfa login --method-type email --secret <S> -c <code>`. The UI
button that "sends" the code text sent it empty twice - ask the owner to type the digits.

**2.2 Passing `--api-key` explicitly bypasses the 2FA session** -> 401. The status script then parsed the
error object as "no instances" and printed "instance is gone" - that would have ended the loop and
written the final report. Rules: use the CLI's stored login, and treat any non-list response as
"cannot reach Vast", never as "gone".

**2.3 CLI quirks:** `show instance <id>` denied (no `api.instance` route) - use `show instances`.
`destroy instance` needs `-y`. `search offers 'gpu_name=GB10'` returned 0; `cpu_arch=arm64` found 17.

**2.4 Offers go stale.** The cheapest offer returned `success:false` and stayed "loading" with intended
"stopped" ("Required resources are currently unavailable"). Destroy and take the next one.

**2.5 No Docker inside Vast instances.** The serving image must be the instance image (`--image ...`).
Vast wraps it with SSH; `vllm` and Python come from the image.

**2.6 io_uring is blocked** by Vast's default Docker seccomp (`io_uring_setup` -> EPERM). The b12x loader
and its 26.8 GiB PLE disk table both needed it. GPUDirect Storage also failed (cuFile 5027). Renting a box
with `--security-opt seccomp=unconfined` weakens the sandbox; do not do it.
Fix that worked: a pread fallback patch in the engine's C reader, kept in the project's `box/` folder.
Rule: probe io_uring in the 5-minute test rental, before planning around the vendor recipe.

**2.7 Do a 5-minute test rental first** (cheap base image, SSH in, nvidia-smi, io_uring probe, HF download
speed, destroy). It cost $0.006 and found three of the problems above.

**2.8 Box clock is UTC, the owner is not.** Several false "stuck" alarms came from comparing local time
with UTC log stamps. Always print `date -u` on the box next to local time.

## 3. Engine bring-up (vLLM fork, b12x, GB10)

**3.1 Verify weights by sha256 against Hugging Face** (tree API with `lfs.oid`) after download. The owner
asked "did you download the same weights as my machine?" - only hashes answer that.

**3.2 Overlay repos (abliterated shards on top of a base) - check the overlay's commit history.** One commit
-> the owner's home copy is identical.

**3.3 First start compiles for 10-15 min.** Later starts with an unchanged config take ~5 min. Any change to
compile shapes (e.g. max_num_batched_tokens) recompiles once (+2-8 min).

**3.4 max_num_batched_tokens 4096 crashed the start** (host OOM kill at ~4 GiB free) - same as on the owner's
home Spark. Cause: PyTorch caching allocator during b12x scale preparation. Fix:
`PYTORCH_CUDA_ALLOC_CONF=per_process_memory_fraction:0.95,garbage_collection_threshold:0.8`.
Lowest MemAvailable during start went from ~4 GiB to ~16 GiB. Log MemAvailable every second during start.

**3.5 max_num_batched_tokens 16384 cannot serve max_model_len 262144 at GMU 0.75** (KV left 2.23 GiB, one
request needs 4.93 GiB). Bigger chunks eat KV memory.

**3.6 The KV pool size moves between starts** (559k-745k tokens, CUDA-graph memory profiling). Log it, do not
score it.

**3.7 Check defaults before every flag/env idea.** Already on by default in the image: CUDA graphs
FULL_AND_PIECEWISE, custom_ops all, three NVIDIA "speed" envs, FlashInfer sampler, async scheduling with MTP.
Read `envs.py` / `config/*.py` / `serve --help=all` in the image (the installed fork beats upstream docs).

**3.8 Dynamic speculative decoding (adaptive depth, per-batch-size depth) fails config validation** on this
fork for Qwen3.8 + mamba align cache (needs request-boundary checkpoints). Build the config offline first:
`box/cfgcheck.py` (EngineArgs.create_engine_config without loading weights) - catches it in 1 minute instead of 6.

**3.9 Don't trust a quick hypothesis about numerics.** "4096 drift comes from A4 prefill" was wrong; a
controlled run with A4 off showed the same drift. Test one variable before writing it down as cause.

## 4. Scripts, shells and remote control

**4.1 `pkill -f "vllm serve"` killed the SSH session** that carried the command (its own command line
matched). Use `pkill -f "[v]llm serve"`.

**4.2 Never edit a bash script while it runs** (bash reads it incrementally). Write versioned copies
(`run_experiment_v5.sh`) and point the launcher at the new file.

**4.3 PowerShell parameter traps:** a `[string[]]$Push` param silently swallowed only the first path; use named
`-Src/-Dst`. Variables are case-insensitive: `$benchy` collided with switch `$Benchy`. A failed
`Set-Content -NoNewline` after an earlier `Remove-Item` deleted the source file - write the new file first,
delete the old one last. Use the Write tool for whole files instead of fragile `-replace` chains.

**4.4 Quoting across PowerShell -> ssh -> bash -> python breaks.** Put Python in files, push them, run them.
Use `\$` for awk/bash variables inside PowerShell double quotes, or single-quote the whole remote command.

**4.5 scp/ssh through Vast's proxy works**, but give it a separate known_hosts file
(`secrets/vast_known_hosts`) and `StrictHostKeyChecking=accept-new` for disposable boxes only.

**4.6 The background watcher died on one scp hiccup at 03:04 and nothing woke the agent until 10:40.**
~8 hours of idle box (~$2.40). Rules: `wait.ps1` retries every box call and the result pull; the goal line
says "never end a turn without a live background waiter"; chain the next launch inside the same job only
if it stops on failure.

**4.7 Build numbers by script.** `record.py` writes results rows from raw files; `check_state.py` validates
TSVs after every write. Hand-typed numbers drift.

## 5. Running the loop

**5.1 One change per pass, from the FIFO queue.** Reordering needs an owner OK and a logged ruling.

**5.2 An enabler pass can be speed-neutral** (the allocator setting alone at 2048). If the research defines a
two-step experiment, log the ruling and run step 2 as the same idea.

**5.3 Confirmation re-runs paid off:** both promoted winners repeated within 0.5 % of their first score.

**5.4 The progress chart's cumulative line must count promotions only** (it counted the KEEP and its
confirmation twice -> 1.31x instead of ~1.18x).

**5.5 Stop vacuous runs early.** If you notice the flag is default-on after launch, kill the run (also kill
its waiter task) and record a RECON-style ruled_out row.

**5.6 Keep the owner's home machine read-only.** Reading facts (recipe, help, logs, a token) was OK when
asked; running anything heavy there was forbidden.

**5.7 Disk-space panic is usually not you.** When the owner asked why C: was full, a 2-day large-file scan
showed 300 GB of someone else's VHDX images. Answer with evidence. Hard deletes are the owner's to do.

## 6. Interpreting results

**6.1 Biggest lossless win came from the I/O path, not from flags:** reading the PLE/n-gram table through the
page cache (O_DIRECT off, POSIX_FADV_RANDOM) gave +17.5 % prefill and +13 % agent replay with identical numerics.
Look at what the engine reads from disk per token.

**6.2 Prefill budget (4096 vs 2048) gave +15 % prefill** on top, but changes numerics (owner accepted).

**6.3 Losers on this stack:** probabilistic drafting (inside noise at T=1, costs batch>1), MTP n=3 (+12 %
long thinking, -5 % short answers, net inside noise), prefill-compute-share auto (-6 % replay at 1-3 streams),
stream-interval 4 (neutral).

**6.4 Some upstream "wins" were measured at T=0 or on other models.** Treat research numbers as "worth a
test", never as expected gains; they do not add up.

**3.10 A flag check must include its Python dependencies.** `VLLM_USE_FASTOKENS=1` crashed in 15 s because the image lacked the `fastokens` package; `pip install 'fastokens>=0.2.0'` on the box fixed it. Grep the code path a flag enables for imports before launching.

**3.11 Unpacking another image into the running container works** (`box/pull_image_pkgs.py`: Docker Hub layers -> dist-packages, run with PYTHONPATH). The regular-lane vLLM ignored `VLLM_PLE_TABLE_MEMORY` (needs `--engram-config '{"host_file_gather": true}'`) and rejected FORCE_A16 MoE on this checkpoint - check env names and kernel layout support before a full run.


**2.9 The Vast 2FA session lasts about 25 hours.** When it expires, SSH and running jobs keep working, but account calls (credit, instance list, status.py) fail. Request a new email code early, and keep the loop running over SSH meanwhile.


---

# Part 2 - lessons from days 2-4 (la125 champion #1 to #8, 2026-10-23 to 10-26)

Same format: what happened -> the rule now. Numbers come from the la125 project; the rules are general.

## 7. Noise and decisions

**7.1 Noise bands are large.** The champion itself swung about 10 % on the 2-agent and 3-agent probes between
identical runs (run 0086: c2 86.7 vs 97/96, c3 104.5 vs 120/113), and agent replay varied up to 15 %. A
deficit of 5-10 % on one probe is often noise. Rule: put the A/A band next to every result, say "inside
noise" when it is, and keep a median of 3 runs as the champion reference, not one run.

**7.2 Every KEEP needs a confirmation run.** First runs that looked like wins (+13 % long thinking, +16 %
replay) came back at +7.9 % and +5 % on repeat. Judge borderline cases on the 2- or 3-run median.

**7.3 Keep floor 5 %, single-probe rule 10 %.** The owner set the floor to 5 % (v5 noise had pushed it to
6.1 %, which hid real small wins). Single-probe rule: one probe >= +10 % while every other probe stays >= -5 %
is a KEEP even if the weighted score dilutes it. Both live in `evaluator.lock`, not in code.

**7.4 Bundles of small changes lost.** Five lossless micro-wins stacked in one pass gave replay -11 %, then -9 %
without one piece. Leave-one-out found nothing clean. Rule: stack only two changes that touch different files,
that each won alone, and test the pair as one pass. Do not bundle "probably fine" pieces.

**7.5 Trade-offs go to the owner as a table, not as a verdict.** Several candidates sped one probe and cost
another (block verification and attn-quant fusion: agent replay +11 %, 3 streams -4 %; GDN async commit: 2 agents
+9 %, long thinking -3 %). The script says ARCHIVE; the owner rules. Log `Ruling: <what> - <why> - <cost if wrong>`.

**7.6 What the owner cares about, in order:** 1 stream > 2 agents > 3 > 4 agents; prefill speed = decode speed;
agent-turn latency (warm TTFT). Weights v7: replay .30, decode .30, 2 agents .15, prefill .15, 3 agents .10.
Ask for this order in Phase 1 and encode it in `project.json`.

**7.7 Queue by success probability, not FIFO.** Put `p=NN%` in the notes of every idea and keep the file sorted
by it (owner ruling 2026-10-25). Re-sort after every pass. Down-rank with a reason when evidence arrives
(a closed-source code path, a CUDA graph already used, a microbench at 90 % of the floor).

**7.8 Owner rulings change the rules mid-run.** Log each with date and the runs it re-judged. Examples:
drift allowed when quality is not worse; floor 5 %; promote on a delegated ruling ("you know better");
"real gains >= 1 % with no degradation are worth keeping". Never apply a new rule silently to old rows.

## 8. Measure before you optimize

**8.1 Profile before optimizing.** The torch profile of 1-stream decode showed BF16 small GEMMs as the biggest
lossless target (14.5 %), and later showed the same kernels already at 90 % of the bandwidth floor. A prefill
profile (GPU busy 98 %) found a 397-token tail step that cost 715 ms = 10 % of a 16k prefill. Profile at the
probe's real shape (short context, long context, prefill) before writing a kernel.

**8.2 Measure the real memory-bandwidth ceiling.** A read-only probe (`bw_read.py`: torch sum, tuned Triton
loads, 1 and 4 GiB) reached 238-240 GB/s on a 273 GB/s GB10, 87-88 %. Nothing went higher. Re-base every
"percent of roofline" on the measured ceiling before claiming "at the limit" or "no headroom".

**8.3 Context length did not slow decode; acceptance did.** A diagnostic (same prompt at 1k and 64k, low and
xhigh effort) showed identical speed per context and a drop in draft acceptance on xhigh thinking text
(0.38-0.49 vs 0.57-0.64). Run a one-variable diagnostic before building a kernel for a slowdown.

**8.4 Switches that change numerics fail the gate.** `VLLM_USE_BREAKABLE_CUDAGRAPH=0` drifted, produced empty
output and lowered tools to 136. Check that a speed switch keeps results the same; the gate does this.

**8.5 Flags that only move one probe are still useful data.** PDL on one kernel family alone: neutral (1.008).
Hardware features pay only when the whole chain uses them.

## 9. Overlays, builds and Vast quirks

**9.1 Overlay loader via `sitecustomize.py` - never stack two.** Patches that must change engine files without
rebuilding the image go in a directory on `PYTHONPATH` whose `sitecustomize.py` patches modules. Two such dirs
on one path recurse. Rule: one overlay dir per champion; a combined pass needs a merged dir (`lane11/stack`).

**9.2 io_uring is blocked on Vast -> pread fallback.** Patch the loader's C reader to `pread` with a thread
pool; test with a byte-identical check on ~69k rows. The page-cache variant (O_DIRECT off) was the biggest
lossless win (+17 % prefill). Probe io_uring in the first test rental.

**9.3 Vast 2FA session expiry.** The session lasts about 25 hours. SSH and runs keep working; account calls
(credit, `show instances`, `status.py`) fail. Run `vastai tfa send-email`, put "NEED VAST EMAIL CODE" at the top
of `PROGRESS.md`, and wait for the owner's six digits. `status.py` must print LOOP RUNNING, not LOOP FINISHED, then.

**9.4 Git Bash rewrites scp paths** (`/root/x` becomes `C:/Program Files/Git/root/x`). Do pushes and pulls from
PowerShell (`box.ps1`), or set `MSYS_NO_PATHCONV=1`.

**9.5 References die with the box.** The gate's reference outputs lived only on the old box and were lost at
destroy. Pull `/root/work/ref` to `refs/` after every record run. A new box means re-recording (a new baseline).

**9.6 A new box is a new baseline.** Bandwidth, noise and the PLE/page-cache behaviour differ per box. Measure
the champion's reference runs on the new box before judging any candidate.

**9.7 Hardware or upstream changes often invalidate an idea.** A newer b12x tree renamed APIs the image's vLLM
calls; the regular-lane image rejected the checkpoint's kernel layout. Overlays need a matching base.

## 10. Process

**10.1 Sub-agents.** Ask the owner which models and effort levels are allowed (the first project allowed only
mid-size models at medium or high effort, and a small model for recon). Use them for research rounds, recon of
flags, building an overlay with one model and a second model as reviewer. The main session decides and records. See `loop.md`.

**10.2 Outside research models beat in-house guessing for kernels.** Paste self-contained prompts (system facts,
profile, rules, answer format) into 2-3 outside models; keep only ideas with a concrete code path
(`docs/16`, `docs/17`). Down-rank anything that is closed source or measured at T=0 on another model.

**10.3 Do not end a turn without a live waiter**, and do not poll a log. Use a background `wait.ps1`.

**10.4 Update `PROGRESS.md` as one table:** champion vs the owner's home setup. The owner reads that first.

## 11. Late lessons (2026-10-26 to 10-29)

**11.1 A replay probe with natural answer lengths rewards luck.** Same recipe, two runs: 2,855 vs 6,758 output
tokens, wall time 146 s vs 193 s. A "+32% replay" KEEP was pure length. Fix: every replay turn writes the same
number of tokens (`max_tokens = min_tokens`, `ignore_eos`) and score warm-turn first-token time on its own
(evaluator v8). Check `completion_tokens` per turn before trusting any wall-time gain.

**11.2 The box keeps its own copy of the evaluator.** After any change to `scripts/bench/*`, push the files to the
box (`/root/work/bench/`) and compare sha256 before the run reaches its probes.

**11.3 Profile the slow path you have never profiled.** The first prefill profile (after 80 passes) found a 397-token
tail step costing 10% of a 16k prefill, caused by where the prefix-cache checkpoint sits. A one-flag change
(`--recurrent-prefill-tail-stride 32`) then cut warm agent-turn first token by 13%.

**11.4 Check the client round trip once.** Send a real two-turn agent conversation the way the owner's client sends it
(thinking returned in `reasoning` / `reasoning_content`, tool calls, tool result) and read the server's prefix-cache
counters. Here: 99.69% of turn 2 came from cache (39 tokens recomputed). A replay trace that drops the thinking
is harsher than real use.

**11.5 Let the owner set the score weights, then soften them once.** Raw priority weights (0.35 / 0.25 / 0.15 / ...
/ 0.01) made prefill and 2 agents nearly invisible and let one swingy component carry a KEEP. v8.2 kept the order
and gave every probe a real weight; the "no probe may drop past its band" rule protects the rest.

**11.6 Home transfer is its own experiment.** At home the baseline was already faster (io_uring, warm caches), so
gains were smaller on some probes and larger on others. Measure home baseline and candidate with the locked
evaluator inside the container, prove each change is active in-process, keep a rollback.
