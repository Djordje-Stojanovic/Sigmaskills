# Personal instructions live in one file outside every skill folder

Each skill's personal instructions live in one file outside every skill folder: `custom/<skill>.md` in the private state folder (`~/.agents/.sigmaskills/` for a Global Installation, `<project>/.agents/.sigmaskills/` for a project). The `<sigmaskills-custom>` block in each copy's `SKILL.md` stays, but as the rendered view of that file. Every install, update and replace writes the file's lines into the block of every copy the installer owns. A linked host folder shows the canonical copy.

This supersedes one part of ADR 0001. That ADR rejected a sidecar file because a separate file is harder to find. The block still shows the lines where the user reads the skill, and an edit typed into a block is taken into the file on the next run. So that reason no longer holds. What 0001 did not foresee: the block was the only place the lines lived, so copies that cannot be links (Antigravity) carried empty blocks, and a run that rewrote a folder could lose them.

The pattern is the standard one for a user's additions to package files: systemd drop-in folders, git's `include.path`, and the separate user and project instruction files of agent tools. The Agent Skills format has no such layer, so the installer does the merge.

## Consequences

- An edit in a block wins when the file has not changed since the last run. When both changed, the file wins and the block's lines are saved beside it under a dated name. Nothing is deleted.
- The first run moves each non-empty block into its file. A second, different block is saved beside it.
- Copies are compared without their blocks and line endings. A personal block is not drift.
- A personal file that holds a marker is not rendered. The run says so, and the blocks stay as they are.
- `purge` leaves the `custom/` folder alone.
