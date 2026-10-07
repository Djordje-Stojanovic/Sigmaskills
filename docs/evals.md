# Skill evals

A skill is a set of instructions, so an edit can quietly break what it produces. The evals catch that in two layers.

## Layer 1: contract checks in `npm test` (runs in CI)

- `scripts/eval-contracts.js` holds one check per skill. A check reads what a run left behind (the files and the final chat reply) and lists every way it breaks the skill's documented output. An empty list is a pass.
- `test/fixtures/eval-samples/<skill>/good` and `bad` hold small sample outputs. The test asserts that each check accepts the good sample and rejects the bad one. A new skill fails this test until it has a check and samples.
- `test/fixtures/skill-triggers.json` holds near-miss prompts: each one names the skill it should reach and the neighbour it must not reach. The test routes each prompt with a simple keyword score over the skill descriptions: a prompt word counts for a skill when it appears before "Do not use", and against it when it appears after. This is a deterministic stand-in for the host's model-based routing. It fails when a description edit drops the words that separate two skills.

What each check requires:

| Skill | Output checked | Required shape |
|---|---|---|
| SigmaReview | `SIGMAREVIEW-YYYY-MM-DD.md` at the root | Title; sections Verdict, System and promises, Fix plan, Findings index, Findings, Coverage in order; verdict and wave tables; `SIG-001`… numbered in order, each in the index with priority, evidence class, broken promise, fix, proof test, and done-when |
| SigmaImprove | `.scratch/sigmaimprove/*.md` (local tracker) | 1–20 category files titled `SigmaImprove · <ID> <name>`; Where we stand, Entries, History; entries table; each Idea has problem, recommendation, done-when; each Signal has what we see, gap, questions; at least 10 entries across 5 category groups |
| SigmaBrief | Final chat reply | Dispatch lines `wave N \| … \| isolation: … \| type: …`; fenced `text` briefs that each say do not merge and end with the fixed report-back line; no fixture file added or changed (no `SIGMABRIEF-*.md`, no code edits) |
| SigmaShip | `PR-BODY.md` and `CLEANUP.md` (the runner asks for them) | `Closes #N`, spec and map line, Acceptance with every box ticked, Rulings, Follow-ups, Review rounds table with at least one round; cleanup output shows `main in sync` and `tree clean` |
| SigmaWrite | `docs/NOTES.md` in the fixture, rewritten | Code names `step`, `saveBest`, `src/scores.js` survive; the planted jargon is gone; no sentence over 30 words |
| SigmaRefactor | `REFACTOR-SCAN.md` (the runner asks for it) | Counting method named (`laloc` or fallback); ranked files with line counts; choices with risk and verification |
| EasyTalk | `status-board.html` and final chat reply | Installed template preserved outside its DATA block; valid JavaScript with PAGE, DO, ANS, FYI; reply links the saved board |
| Arena Create | `arena/arena.json` and final chat reply | Valid config with title, question, metrics, groups, at least four players and items that name known players and groups; no `picks.jsonl`; reply links the local arena (port 3410-3499) |
| SigmaResearch | Final chat reply | Sources table with platform, URL, publication/access dates, route, scope and evidence (or None with a gap); explicit Access gaps section |

## Layer 2: live runs on demand (not in CI)

```bash
node scripts/eval-skills.js                 # all skills
node scripts/eval-skills.js sigmareview     # one or more skills
```

For each skill, the runner copies `test/fixtures/eval-repo` (Snake Lite, a tiny terminal game) to a temp folder, makes it a Git repository with a local bare `origin`, installs the skill in `.claude/skills/`, and runs `claude -p` headless. Then it runs the skill's contract check and prints pass or fail, wall time, cost, and tokens. The run folders stay on disk for inspection.

SigmaResearch receives an offline HN record, a Reddit 429 log and unavailable Chrome tools. Its eval checks honest source scope and access gaps, not current platform access. Contract checks validate output structure; they cannot prove factual accuracy, pacing or browser behavior. Independent scenario review covers those instructions.

The fixture has seeded defects: the snake survives one cell past two walls, food scores 10 instead of the documented 1, `src/scores.js` runs `eval` on a file, and one weak test. It also has obvious gaps for SigmaImprove: no pause, no difficulty levels, no color.

Isolation: `--setting-sources project` drops the user's settings files, and with them the user's permissions and plugins. The `claude --help` text (2.1.283) does not say that it also hides personal skills in `~/.claude/skills/`, so a personal skill with the same name may still load; remove it before a run if you need a clean result. `--strict-mcp-config` loads no MCP servers; `gh`, WebFetch, and WebSearch are denied; Bash is limited to `git`, `node`, `npm test`, `ls`, and `wc`; edits are allowed only in the temp folder. The prompt tells each skill that the run is offline. Skills whose real output is a GitHub artifact write it to a file instead. Each run is capped at $4 and the whole run at $15. This is a guard, not a sandbox: the allowed `git` and `node` commands could still reach the network if a skill ignored the prompt.

## First run: 2026-09-27

Model: `claude-opus-5-5` through Claude Code 2.1.283, on Windows 11. Total spend: $4.16 (the six-skill run, one earlier SigmaWrite trial, and one SigmaImprove re-run).

| Skill | Result | Time | Cost (USD) | Tokens | Notes |
|---|---|---:|---:|---:|---|
| SigmaReview | pass | 187 s | 0.79 | 651,814 | Found the three seeded code defects (walls, score, `eval`) and named the weak test in the verdict and coverage, not as a finding. Also found two real extras: the best score is cleared on the first frame, and food can spawn under the snake |
| SigmaImprove | fail, then pass | 279 s / 235 s | 0.94 / 0.91 | 457,248 / 563,620 | 15 valid category files. The first run also wrote an index `README.md`, which the first check wrongly read as a category file. The check now reads only `<category ID>-<slug>.md` files; the saved run and a live re-run both pass |
| SigmaBrief | pass | 65 s | 0.26 | 151,090 | Two parallel greenfield briefs with worktree lifecycle and the report-back line |
| SigmaShip | pass | 105 s | 0.61 | 1,199,291 | Built the wall fix test-first, squash-merged, pushed to the local `origin`, removed branch and worktree; `main in sync`, `tree clean` |
| SigmaWrite | pass | 33 s | 0.14 | 168,330 | Jargon gone, code names kept |
| SigmaRefactor | pass | 89 s | 0.39 | 383,428 | Fallback count, five files ranked, choices with risk; no code edited |

Tokens include cache reads. A full six-skill run took about 13 minutes and $3.10.

Environment limits: `laloc` is not installed here, and the restricted Bash rules denied some compound commands (`a && b`). So SigmaImprove could not start the game, and SigmaShip ran each verify command on its own.

Near-miss triggers (in `npm test`). Score = prompt words found in the "Use when" part minus words found in the "Do not use" part of each description.

| Prompt | Expected skill, score | Near miss, score | Result |
|---|---|---|---|
| Do a full review of this repository and find every bug | sigmareview 3 | sigmaimprove 1 | pass |
| Run a security review and a performance audit of the repo | sigmareview 3 | sigmaimprove -1 | pass |
| Hunt for bugs and security holes in my game | sigmareview 4 | sigmaimprove -2 | pass |
| What should we improve or add next to this game? | sigmaimprove 2 | sigmareview 0 | pass |
| Suggest what to redesign or cut to make the product better | sigmaimprove 3 | sigmareview -1 | pass |
| Compare my app with the top products and list feature ideas | sigmaimprove 4 | sigmareview -2 | pass |
| Write parallel agent briefs for these GitHub issues | sigmabrief 5 | sigmaship 2 | pass |
| Give me a handoff prompt so a fresh agent can continue | sigmabrief 5 | sigmaship 3 | pass |
| Implement and ship issue #12 end to end and merge the PR | sigmaship 4 | sigmabrief 0 | pass |
| Build this ready ticket in a worktree with a draft PR | sigmaship 4 | sigmabrief 0 | pass |
| Explain this in simplified technical English with less jargon | sigmawrite 6 | sigmabrief 0 | pass |
| Rewrite this for an outsider: clear, no gibberish | sigmawrite 2 | sigmarefactor -1 | pass |
| Review my large files and simplify them to reduce code size | sigmarefactor 7 | sigmareview -1 | pass |
| Run a laloc scan and help me shrink the biggest files | sigmarefactor 3 | sigmaimprove 0 | pass |

## Recommendation

Keep the live runs on demand. Keep the contract and trigger checks in CI, as they are now.

- The contract checks already stop the failure that SC-015 names: an edit that breaks a skill's documented output shape and nobody notices. They are free, fast, and deterministic.
- A live run costs about $3 and 13 minutes, and model output changes from run to run. The first run had one false failure. A CI gate would need an API key in pull-request workflows and would turn model noise into red builds.
- Run `node scripts/eval-skills.js` before each Release, and after any edit to a skill's workflow or output contract.
