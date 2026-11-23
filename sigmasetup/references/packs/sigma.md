# Sigma pack setup

The first-party skills. Most need nothing in the repo. For each skill: what it needs, and the one-time setup to offer. Do only what the owner says yes to.

Machine-wide for the whole pack: `git`, Python 3, and `gh` signed in (`gh auth status`) for every skill that opens issues or PRs.

## Repo setup shared by several skills

- **House files.** `ENGINEERING.md`, `DESIGN.md` and the shared sections of `AGENTS.md` come from the owner's masters: `../house-files.md`.
- **Agent docs.** sigmareview, sigmaship, sigmamusk and sigmaloop read `AGENTS.md` or `CLAUDE.md`. Offer to create `AGENTS.md` when neither exists.
- **Issue tracker.** sigmaloop reads `docs/agents/issue-tracker.md`; sigmaimprove uses "the tracker named in the repository's agent docs". The Matt Pocock setup writes that file (see `mattpocock.md`). Without it, sigmaimprove falls back to `.scratch/sigmaimprove/`.
- **Merge habit.** sigmaship squash-merges, closes the linked issue, deletes the local and remote branch, removes the worktree and syncs the base. Offer the GitHub settings that match: squash only, PR title as the commit title, delete the branch on merge:
  `gh api -X PATCH repos/<owner>/<repo> -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false -F delete_branch_on_merge=true -f squash_merge_commit_title=PR_TITLE`

### sigmareview

Needs: push rights or a fork, `gh`. Reads the agent docs, README, contribution rules and ADRs. Setup: none.

### sigmaimprove

Needs: `gh` and a named tracker. It uses labels only when they exist and never creates them. Setup: the tracker file above.

### sigmaship

Needs: an issue with acceptance criteria, git worktrees, `gh` with merge rights, the repo's test, type-check and lint commands. Optional: the `t3` CLI for a named reviewer model. Companions: `/to-spec`, `/to-tickets`, `/grilling`, `/tdd`. Setup: write the deploy command and the docs-sync step into `AGENTS.md`, so the land step has real commands; apply the merge habit above.

### sigmawrite

Needs: nothing for plain use; the GUI option ("easy talk") needs a browser; the humanize mode optionally Python for `factcheck.py`. Setup: optional, paste its system-prompt block into the host's instructions.

### sigmaresearch

Needs: Python 3. Optional: `yt-dlp`, whisper, `GITHUB_TOKEN` or `GH_TOKEN`, an xAI key for X, Claude in Chrome. Setup: none in the repo.

### sigmadeeplook

Needs: Python. Many optional tools (ffmpeg, poppler, tesseract, LibreOffice, Ghidra and more). Setup: run `python sigmadeeplook/scripts/look.py doctor` and install only what the owner's files need.

### sigmadebug

Needs: a writable folder (Downloads by default) and a text editor. Hands each clear topic to `sigmaship` in a background agent, uses `sigmawrite` for its voice and `grilling` when installed. Setup: none.

### sigmacreatearena

Needs: Python 3 and a browser. Setup: none; it makes an `arena/` folder when it runs.

### sigmafreedom

Needs: Python. Setup: it is the setup. On a yes it copies `guardrail_lint.py` into the repo and wires it into the checks.

### sigmaloop

Needs: one long-run host (Claude Code, Codex, Antigravity, pi with lapi, or T3 Code). Reads `docs/agents/issue-tracker.md`. Its briefs point to `/grilling` and `/tdd` (Matt Pocock pack). Setup: the tracker file above.

### sigmataste

Needs: a browser or renderer for screenshots. Reads `DESIGN.md` when present. Setup: none.

### sigmatour

Needs: Python, git, a browser. Setup: none.

### sigmafinanceman

Needs: Python 3.10+ and `pip install openpyxl python-pptx`. Optional: LibreOffice and `pdftoppm`. Setup: set `SEC_USER_AGENT="Name email"` in the environment (never in the repo).

### sigmacourse

Needs: nothing beyond the agent host. The goal prompt it ends with needs `sigmaloop`; research steps use `sigmaresearch` and `sigmadeeplook` when installed. Setup: none; it sets up the course repo it plans.

### sigmamusk

Needs: nothing for `cut` and `reset` but the repo's tests; `gh` signed in to file the issue (without it, the issue body prints in chat). Hands off to `sigmaship` when installed. Setup: none.

### sigmacorrect

Needs: the repo's test or check command. Setup: none.

### sigmacreate

Needs: git; `gh` for a public skill shipped by PR. Setup: none; it installs the skill it makes.

### sigmaclimb

Needs: Python 3 and a target it can measure or the owner can judge. Uses `/grilling` when installed. Setup: none; it writes its own project folder.

### sigmacollab

Needs: the `colab` CLI (`uv tool install google-colab-cli`), the Google Cloud CLI for the sign-in, and a Google AI or Colab plan with units. For Vast: the `vastai` CLI with credit. Setup: `gcloud auth application-default login` once per machine (the skill names the scopes), then `colab --auth adc usage`; `vastai set api-key` once for Vast. For boat.dev boxes: the `boat` CLI (static download from boat.dev for Linux, macOS and Windows) and `BOAT_API_KEY` in the environment or a secrets file; `boat login --key-stdin` once per machine; a repo installs on a box from `.boat/setup.sh`, else its lockfiles.

### sigmavast

Needs: `sigmacollab`, which it points to. Setup: none.

### sigmaask

Needs: Node 22 for `scripts/ask.mjs` (standard library only). Setup: none. It reads the skill folders of every host and the installer's state, and asks npm for the newest release; `--offline` skips that.

### sigmasetup

Needs: Node (the installer already needs it); git to read a house source that is a repo. Setup: none; it is the setup. Point it at the owner's masters once: `../house-files.md`.
