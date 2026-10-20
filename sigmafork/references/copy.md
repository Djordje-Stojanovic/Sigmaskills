# Fork or copy, by source kind

`<src>` is the original, `<dest>` the new folder, `H` the helper `scripts/sigmafork.py` (run it with `python`). Record the original's state first:

```
git -C <src> status --porcelain ; git -C <src> rev-parse HEAD      # a git repo
python H scan <src> --source <src> --json > before.json             # any folder: read-only, lists its paths
```

## GitHub: fork (to change it and open pull requests upstream)

```
gh repo fork <owner>/<repo> --clone=false [--fork-name <name>]
git clone https://github.com/<me>/<name>.git <dest>
git -C <dest> remote add upstream https://github.com/<owner>/<repo>.git
git -C <dest> remote set-url --push upstream DISABLED                # pushes go to the fork only
```

`gh` needs a login: the owner runs `gh auth login` himself if `gh auth status` says no.

## GitHub: clone (own copy, upstream read-only)

```
git clone https://github.com/<owner>/<repo>.git <dest>
git -C <dest> remote rename origin upstream
git -C <dest> remote set-url --push upstream DISABLED
```

To give it a home on GitHub later: `gh repo create <name> --private --source <dest> --push`.

## GitHub: template (fresh history)

```
git clone --depth 1 https://github.com/<owner>/<repo>.git <dest>
```

Then delete `<dest>/.git` (it is the copy's own, just cloned), `git -C <dest> init`, and make the first commit after step 3 is done.

## Local git repo

`git clone --no-hardlinks <src> <dest>` brings only committed files. When the owner wants uncommitted work, ignored data or local assets too (Q3), use the helper copy below instead. Either way, `origin` must not point at `<src>`: a push there writes into the original.

```
git -C <dest> remote -v
git -C <dest> remote set-url origin <the upstream URL of src, if it has one>   # or:
git -C <dest> remote remove origin
```

Worktrees of the original (`<src>/.git/worktrees`) do not belong in the copy: after a helper copy, run `git -C <dest> worktree prune`.

## Local folder (git or not)

```
python H copy <src> <dest> --exclude "animations/2*" --exclude "renders" --exclude "*.log"
```

- `--exclude` takes a glob on the relative path (`animations/2*`) or a bare name (`renders`). Keep templates and examples; leave out the source's own past output.
- Installed dependencies and caches are skipped by default (`node_modules`, venvs, `__pycache__`, tool caches); the copy reinstalls them from its lock files. `--keep-heavy` copies them anyway (offline machine).
- `--no-git` leaves out `.git` (a fresh history).
- Links (symlinks, Windows junctions) that point inside `<src>` are made again inside `<dest>`, pointing at the same place in the copy. Links that point outside are copied as real files, so the copy never writes through them.
- The log `<dest>/.sigmafork/copy.json` lists what was skipped, every link, and the ten biggest files.

## Cut every path back to the original

```
python H scan   <dest> --source <src>
python H fix    <dest> --source <src> [--map "D:\out\Src=D:\out\Copy" ...]
python H verify <dest> --source <src>
```

- `scan` finds the source path in every spelling a file may use: `C:\x`, `C:/x`, `C:\\x` (escaped in JSON or code), `/c/x` (Git Bash), `/mnt/c/x` (WSL), `file:///C:/x`. It also lists git remotes and links into the source, other absolute paths outside the copy (grouped by their first folders, with counts), and relative paths that climb out of the copy (`../sibling-repo`).
- `fix` rewrites each hit to the same spelling of `<dest>`, byte for byte, so line endings and file encodings stay. `--map OLD=NEW` does the same for an outside folder the copy must own (Q3). It leaves `.git/config` to you: fix remotes with `git remote`.
- `verify` exits 1 while anything still reaches the source. It does not block on the review lists; read them and decide each with the grill's answers:
  - an output folder, cache or database the copy writes to → `--map` it into the copy or to a new folder;
  - shared read-only config (a keys file, a tool's global config) → leave it, and name it in the guide;
  - a relative path to a sibling repo → copy that sibling too (ask), or point it at the original read-only and say so.
- Config the scan cannot see: environment variables set outside the repo (shell profile, a service file) and paths built at run time from a home folder plus a name (`~/.<tool>/`). Grep the code for `HOME`, `USERPROFILE`, `expanduser`, `homedir` and `APPDATA`; when the copy would share state with the original there, give it its own name through the tool's config or an environment variable in the copy's `.env`.

## Owner-only inputs

Make one list from the study: each login, key or token, what needs it, and where it goes (`.env` line name, a config file, a CLI login). Show it to the owner, and wait while he types each one himself. Then check without printing: a status command (`gh auth status`), the tool's own doctor, or a one-line script that says "found" or "missing" per name.

## Prove it runs

Install from the copy's lock file (`npm ci`, `pnpm install --frozen-lockfile`, `uv sync`, `pip install -r requirements.txt`, `cargo build`), then run its own check (`npm test`, the repo's check script) or one real example from the grill (Q2). Note the command and its real output for the guide. A check that fails only because it reads a folder the grill left out (live tickets, past projects, a sibling repo) is expected: name each one and why in the guide's "Run it"; fix every other failure.

## Before you leave this step

- `verify` prints `ISOLATED`.
- The original's state matches what you recorded (same `git status --porcelain` and HEAD, or the same scan).
- `grill.md` and `study.md` are in `<dest>/.sigmafork/`.
