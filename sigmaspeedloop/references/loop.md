# Project files, the long run, steering, research, hand-off

## 1. File map of `assets/project-template/`

| Path | Role | Adapt for a new project? |
|---|---|---|
| `project.json` | per-project constants: score weights, floors, Vast filters, image label | yes |
| `GOAL.md` | run file, re-read every turn | yes - fill every <...> |
| `scripts/box.ps1` | run/copy on the box via `state(.tmp)/instance.json` | no |
| `scripts/launch.ps1` | invariants + push serve file + start `run_experiment.sh` (`-Record`, `-NoBenchy`) | no |
| `scripts/wait.ps1` | waits for DONE with retries, pulls `runs/<id>/raw` | no |
| `scripts/status.py` | the one status line the host's stop check reads | no |
| `scripts/record.py` | writes a results.tsv row from raw files (`SPEEDLOOP_IMAGE_LABEL` env) | no |
| `scripts/bench/common.py` | streaming client, `stop_after`, salts, long docs (`BENCH_MODEL` env) | defaults |
| `scripts/bench/gate.py` | fidelity + needles (`--record` writes references) | prompts, needle sizes |
| `scripts/bench/speed.py` | speed probes (v6 replay, c2, c3, chat) | efforts, tokens, contexts; non-LLM: rewrite |
| `scripts/bench/run_experiment.sh` | one measured run on the box | ToolEvalBench args, model path |
| `scripts/bench/verdict.py` | VOID/CRASH/RERUN/REJECT/ARCHIVE/KEEP; weights from `project.json` | components if not an LLM |
| `scripts/bench/aa.py` | A/A bands + file hashes -> `evaluator.lock` | no |
| `scripts/bench/invariants.py` | locked flags/env vs `baseline_serve.sh`; `OWNER_OK_DRAFTERS` | yes - lists |
| `scripts/bench/bw.py` | GPU copy-bandwidth probe (add a read-only probe for the true ceiling) | no |
| `scripts/bench/build_replay.py` | freezes real agent sessions into replay traces | session path/format |
| `check_state.py`, `plot_progress.py` | TSV validator, progress.png | chart labels |
| `box/*` | download, sha256 verify, smoke test, offline config check, serve_base.sh, b12x pread patch | model args |
| `docs/03_ANTI_GAMING.md` | shortcuts and the rule that blocks each | review |

Paths on the box: `/root/work/bench`, `/root/work/ref`, `/root/runs/<id>`. Grep for the old model dir name.

Workspace layout when several projects exist: `<root>/Projects/<Name>/` holds one project (all files above plus
`runs/`, `state/`, `secrets/`). The root holds a README and, if the host's stop check needs it, a shim `scripts/status.py`.

## 2. TSV headers

`ideas.tsv`: `id	status	idea	category	work_type	expected_effect	evidence	notes` (put `p=NN%` last in notes)
`ruled_out.tsv`: `id	direction	why_it_failed	evidence	reopen_condition`
`results.tsv`: `pass	utc	parent	idea_id	category	work_type	image	verdict	score	decode_tps	decode_long_tps	prefill_tps_64k	ttft_128k_s	replay_wall_s	replay_ttft_p50_s	c3_tps	mtp_accept	kv_tokens	start_s	low_mem_gib	gate_top1	gate_dlogp	gate_reliability	minutes	cost_usd	description`

Verdicts: BASELINE, AA, KEEP, ARCHIVE, REJECT, VOID, CRASH, RECON. Tabs only. Run `python check_state.py` after
every write.

## 3. The long-run prompt

The loop runs for days, so it needs the host's unattended mode. The stop condition is the one line
`scripts/status.py` prints: "LOOP FINISHED: ..." when the owner has destroyed the box and `REPORT.md` exists,
"LOOP RUNNING: ..." in every other case (a provider error prints RUNNING with a note). Paste the prompt after the
setup files exist. Replace the first word with the host's command.

```text
<host loop command> <Model> speed loop is done: `python scripts/status.py` prints "LOOP FINISHED: instance <id> destroyed by owner, REPORT.md written". Every turn: read <project>/GOAL.md first and follow it exactly, then print the output of `python scripts/status.py` at the end of the turn. Never end a turn without a live background job that waits on the box (scripts/wait.ps1) unless the instance is gone. Limits: never touch the owner's own machines; never quantize or cut precision on the target model; ideas.tsv keeps at least 3 pending ideas, sorted by success probability; one change per pass, and only scripts/bench/verdict.py decides KEEP; only the sub-agents the owner allows; never print a secret.
```

| Host | Loop command and stop check | Notes |
|---|---|---|
| Claude Code | `/goal`: a judge reads the transcript for the printed status line | The owner ends it with `/goal clear`; a `/goal stop` sent mid-turn may not register. See `sigmaloop/references/host-claude-code.md`. |
| Codex | `/goal`, with the status line as the done check | `sigmaloop/references/host-codex.md` |
| pi, T3 Code, Antigravity | their own loop or goal mode | `sigmaloop/references/hosts.md` and the host file there |
| No loop mode | the owner re-sends "continue" | Every turn still starts by reading `GOAL.md` and ends with the status line. |

Why it is built this way:
- **The stop condition is machine-checked.** A sentence like "until it is fast enough" never ends.
- **"Every turn read GOAL.md":** an edit to that file steers the next turn. Put rulings there.
- **The limits in the prompt** are the ones a long session must not forget after its context is compacted.
- Owner prerequisites: a permission mode that lets the agent run commands, the PC stays on, credit on the GPU host.
- In a multi-project workspace the root `GOAL.md` is a one-line shim that points to the project's `GOAL.md`.
- When the owner says stop, stop starting runs, even while the stop check still says RUNNING. Say what keeps billing.

## 4. How the owner steers

- Decisions come as **tables**: option, effect on each probe, risk, recommended answer. One question at a time,
  with a default the owner can accept with "yes". Keep the box busy with the next lossless idea meanwhile.
- Every idea carries a **chance of success** (`p=NN%`) and the queue is sorted by it. The owner may say "sort by
  chance", "run X first", "drop low-value ideas", "run it all". Log each as `Owner <time>: ...` in `insights.md`.
- **Never idle.** Each turn starts, polls, measures, records or researches. If the box is waiting, build the next
  overlay or run a research round. If the queue is empty and no lossless idea is left, say so, recommend
  wrapping up, and write `REPORT.md` drafts.
- When no rule decides: take the safer option and log `Ruling: <what> - <why> - <cost if wrong>`.
- Trades (one probe up, one down) are ARCHIVE. Present a table; the owner may promote on a ruling.
- Status answers: local time + box UTC, current pass and stage, last verdicts table, champion vs the owner's home
  setup (decode, long thinking, prefill 64k, TTFT 128k, 3 agents, replay, tools, KV), credit left
  (`show user --raw`), experiments left at ~40 min each, and the chart (`progress.png`).

## 5. Research rounds

Start one when fewer than 3 ideas are pending, after 5 passes without KEEP, or when asked.

**Own agents.** A background research agent reads existing docs, `ideas.tsv`, `ruled_out.tsv` first and
reports only NEW ideas. Proven targets: the engine fork's repo and PRs, the vendor model card, the NVIDIA
developer forum (Discourse `/raw`), issues of the image maintainer, practitioner repos with raw benchmark data.
Deliverable: `docs/NN_RESEARCH_*.md` with a ranked list (id, exact change, expected effect, quality risk, works
in a Vast container?, evidence URL), a skip list, sources, contradictions, access gaps.

**Outside models.** For kernel and decode ideas, write self-contained prompts (see `docs/16_EXTERNAL_PROMPTS.md`
and `docs/17_PROMPTS_STRONGEST.md` of the la125 project). Each prompt carries: system facts (GPU, memory
bandwidth, model structure), the measured profile, the invariants and the lossless rule, what was already tried
(the ruled-out list), the answer format (change, expected effect, code path, risk), and a request to flag claims
that were measured at T=0 or on another model. Paste one prompt per model into 2-3 outside models in parallel,
save answers under `Temp-Research/`, keep only ideas with a concrete code path.

Merge ideas by expected value with `p=NN%`, and log the ordering ruling in `insights.md`.

## 6. Sub-agent rules

- Ask the owner which models and effort levels sub-agents may use, and record the answer in `SPEC_DRAFT.md`.
  The first project allowed only mid-size models at medium or high effort and a small model for recon.
- Roles that worked: a small model for recon (flag defaults, image scans); a mid-size model for research rounds
  and for building an overlay; a second model to review a builder's patch for losslessness before it runs.
- The main session owns decisions, verdicts and edits to the TSVs. Agents write code and docs only.
- Brief each agent as a peer: goal, files to read, what is ruled out, the lossless rule, the deliverable path.
- If the owner says "stop using sub-agents", the main session does all work.

## 7. Hand-off when usage runs out

Before the limit hits (or when asked), leave the project resumable by a fresh session:
1. `PROGRESS.md` current: gear, box id and $/h, credit, champion table vs home, queue top, what is running now.
2. `state/pass.json` correct; any waiter job named in `PROGRESS.md` with its run id.
3. `insights.md` has every ruling and owner decision up to now.
4. `GOAL.md` still says what to do first on resume: recover the pass, then continue.
5. Say so in one line to the owner: what is running on the box, when it ends, what the next session does first.
The box keeps running and billing; a resumed session reads GOAL.md, PROGRESS.md and `status.py` and continues.
