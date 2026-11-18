# House files

Your master rule files live in one place, usually one repo of yours. Every other repo carries copies. `scripts/house.mjs` compares the copies with the masters and brings them up to date in one go.

## Where the masters live

The script takes the first of these that is set:

1. `--source <folder | git URL | owner/repo>` on the command line.
2. The environment variable `SIGMASETUP_HOUSE`.
3. A `house:` line in the personal-instructions block of this skill's `SKILL.md`, between `<sigmaskills-custom>` and `</sigmaskills-custom>`. The installer keeps that block on every update.

A folder is read as it is. A git URL or `owner/repo` is cloned shallow into a temp folder; a private repo needs git signed in (`gh auth setup-git`).

When none is set, ask the owner once: "Where do your master rule files live? A folder or a repo." Then show both ways to save the answer and let the owner pick:

```
<sigmaskills-custom>
house: <folder or owner/repo>
</sigmaskills-custom>
```

or, for one shell: `export SIGMASETUP_HOUSE=<folder or owner/repo>` (PowerShell: `$env:SIGMASETUP_HOUSE = '<...>'`; for good: `setx SIGMASETUP_HOUSE <...>`).

## What gets synced: the map

Without map lines the script runs this default:

```
copy: ENGINEERING.md
copy: DESIGN.md
section: AGENTS.md#How we work
```

Map lines go in the same personal-instructions block, one rule per line. Paths are relative: the left side to the master folder, the right side to the repo.

| Line | Does |
|---|---|
| `copy: <master> [-> <repo path>]` | The whole file, byte for byte. For a file every repo shares unchanged. |
| `section: <master>#<heading> [-> <repo file>]` | Replaces the repo's `## <heading>` section with the master's and leaves the rest of the file alone. For `AGENTS.md` and `CLAUDE.md`, where the repo has its own content around the shared part. |
| `seed: <template> -> <repo path>` | Only reports a missing file. The agent writes it from the template with this repo's facts, because a template has placeholders. |

A section goes into every one of `AGENTS.md` and `CLAUDE.md` that already has it. When neither has it, it goes into the named file; when only `CLAUDE.md` exists, into `CLAUDE.md`. A repo-only line inside the section stays at the section's end, and `check` lists it. When the owner wants the section to be the master's word for word, run with `--exact`.

Example with every kind:

```
<sigmaskills-custom>
house: my-org/house-rules
copy: ENGINEERING.md
copy: DESIGN.md
copy: docs/guides/HOW_WE_WORK.md -> docs/HOW_WE_WORK.md
section: AGENTS.md#How we work
seed: docs/templates/AGENTS-template.md -> AGENTS.md
seed: docs/templates/CLAUDE-template.md -> CLAUDE.md
</sigmaskills-custom>
```

## Check, apply, undo

- `node <sigmasetup>/scripts/house.mjs check .`: a table with House file, Kind, State (`current`, `drift`, `missing`, `no master`) and Note. Exit 0 when all are current, 1 on drift.
- `node <sigmasetup>/scripts/house.mjs apply .`: saves the old copy of every file it will change, writes all rows, and prints the undo command. Line endings alone are not drift; a copy and a merged section keep the repo file's line endings.
- `node <sigmasetup>/scripts/house.mjs undo .`: puts back what the last apply changed and deletes the files it created. The saved copies live in the repo's git folder (`.git/sigmasetup-undo/`), outside the working tree; in a folder without git, in `.sigmasetup-undo/`.

## DESIGN.md without a house source

A repo with UI and no house `DESIGN.md` gets its design file from the Design.md pack (`packs/design-md.md`), or from `frontend-design` for a new look. Put it at the repo root and add one line to `AGENTS.md`: read `DESIGN.md` before any UI work. When `CLAUDE.md` starts with `@AGENTS.md`, that line reaches Claude Code too.
