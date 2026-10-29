# Sigma pack setup

The first-party skills. Most need nothing in the repo. For each skill: what it needs, and the one-time setup to offer. Do only what the owner says yes to.

Machine-wide for the whole pack: `git`, Python 3, and `gh` signed in (`gh auth status`) for every skill that opens issues or PRs.

## Repo setup shared by several skills

- **Agent docs.** sigmareview, sigmabrief, sigmaship, sigmarefactor and sigmaloop read `AGENTS.md` or `CLAUDE.md`. Offer to create `AGENTS.md` when neither exists.
- **Issue tracker.** sigmaloop reads `docs/agents/issue-tracker.md`; sigmaimprove uses "the tracker named in the repository's agent docs". The Matt Pocock setup writes that file (see `mattpocock.md`). Without it, sigmaimprove falls back to `.scratch/sigmaimprove/`.
- **Merge habit.** sigmaship squash-merges, closes the linked issue, deletes the local and remote branch, removes the worktree and syncs the base. Offer the GitHub settings that match: squash only, PR title as the commit title, delete the branch on merge:
  `gh api -X PATCH repos/<owner>/<repo> -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false -F delete_branch_on_merge=true -f squash_merge_commit_title=PR_TITLE`

### sigmareview

Needs: push rights or a fork, `gh`. Reads the agent docs, README, contribution rules and ADRs. Setup: none.

### sigmaimprove

Needs: `gh` and a named tracker. It uses labels only when they exist and never creates them. Setup: the tracker file above.

### sigmabrief

Needs: `gh`. Its briefs point to `/grilling` and `/tdd` (Matt Pocock pack). Setup: none.

### sigmaship

Needs: an issue with acceptance criteria, git worktrees, `gh` with merge rights, the repo's test, type-check and lint commands. Optional: the `t3` CLI for a named reviewer model. Companions: `/to-spec`, `/to-tickets`, `/grilling`, `/tdd`. Setup: write the deploy command and the docs-sync step into `AGENTS.md`, so the land step has real commands; apply the merge habit above.

### sigmawrite

Needs: nothing. Setup: optional, paste its system-prompt block into the host's instructions.

### sigmarefactor

Needs: the repo's tests. Optional: `laloc`. Setup: none.

### sigmaresearch

Needs: Python 3. Optional: `yt-dlp`, whisper, `GITHUB_TOKEN` or `GH_TOKEN`, an xAI key for X, Claude in Chrome. Setup: none in the repo.

### sigmadeeplook

Needs: Python. Many optional tools (ffmpeg, poppler, tesseract, LibreOffice, Ghidra and more). Setup: run `python sigmadeeplook/scripts/look.py doctor` and install only what the owner's files need.

### sigmawritegui

Needs: a browser. Setup: none.

### sigmacreatearena

Needs: Python 3 and a browser. Setup: none; it makes an `arena/` folder when it runs.

### sigmafreedom

Needs: Python. Setup: it is the setup. On a yes it copies `guardrail_lint.py` into the repo and wires it into the checks.

### sigmaloop

Needs: one long-run host (Claude Code, Codex, Antigravity, pi with lapi, or T3 Code). Reads `docs/agents/issue-tracker.md`. Setup: the tracker file above.

### sigmataste

Needs: a browser or renderer for screenshots. Reads `DESIGN.md` when present. Setup: none.

### sigmahuman

Needs: nothing. Optional: Python for `factcheck.py`. Setup: none.

### sigmafork

Needs: Python, git, `gh` signed in, `npx skills` for skill bundles. Setup: none; it sets up the copy it makes.

### sigmadesign

Needs: Python and a browser. Optional: Node for `npx @google/design.md lint`. Setup: on a yes, `DESIGN.md` at the repo root and a pointer line in `AGENTS.md`.

### sigmatour

Needs: Python, git, a browser. Setup: none.

### sigmafinanceman

Needs: Python 3.10+ and `pip install openpyxl python-pptx`. Optional: LibreOffice and `pdftoppm`. Setup: set `SEC_USER_AGENT="Name email"` in the environment (never in the repo).

### sigmaspeedloop

Needs: `pip install vastai`, SSH with `~/.ssh/id_ed25519.pub`, a Vast.ai account with credit. Keys live in the project's `secrets/` folder, never in git. Setup: `vastai set api-key` once per machine.

### sigmasetup

Needs: Node (the installer already needs it). Setup: none; it is the setup.
