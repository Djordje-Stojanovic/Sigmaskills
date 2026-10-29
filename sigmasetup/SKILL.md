---
name: sigmasetup
description: 'Use when asked for sigmasetup or to set up installed skills in a repo after the Sigma installer. Per-project setup for each pack, with the owner. Do not use to install skills or for global setup.'
---

# SigmaSetup

The installer puts skills on the machine. Most packs still need a little per-project setup before they work well: a tracker file, labels, a tool, a key in the environment, a git guard. SigmaSetup finds what is installed, says what each pack needs in this repo, and does the setup the owner says yes to.

## Operating contract

- **Per project, never global.** Every write goes into the current repo. Never edit `~/.claude/settings.json`, `~/.codex` or any other user-level config, and never install a hook globally.
- **One question round, then act.** Show the plan for every installed pack in one list with a recommended answer each. Write nothing before the owner answers.
- **Every change can be undone.** Each item in the plan names its undo command or the files to delete. Report both at the end.
- **No secrets in the repo.** Keys go in the environment or an ignored `secrets/` folder. Never print a key.
- **Facts from the pack guides only.** `references/packs/<pack>.md` is the source for what a pack needs. When a guide says nothing about a skill, say so; do not guess.

## Flow

1. **Find what is installed.** Run `npx @djordje-stojanovic/sigmaskills status --project . --json` and `--global --json`. Map each skill to its pack with `npx @djordje-stojanovic/sigmaskills list --packs`. A skill the installer did not install (a plugin, a hand copy) counts when the owner names it.
2. **Read the guides.** For each pack with at least one installed skill, read `references/packs/<pack>.md`. Check what is already in place: files, labels (`gh label list`), tools on `PATH`, environment variables by name.
3. **Ask once.** One numbered list, pack by pack: what is missing, the step that fixes it, its undo, and a recommended yes or no. Mark the steps that need the owner (a login, a key, a purchase): the agent never does those.
4. **Do the yes items.** Run each step, then check it worked. Commit repo files on a branch when the repo uses PRs.
5. **Report.** A table: pack, what is now set up, how it was checked, how to undo it, and what is left for the owner.

## Git guard

An optional Claude Code hook for this repo only: it blocks force push, `reset --hard`, `clean -f` and whole-tree `checkout .` or `restore .`, and allows branch deletes. Offer it with the Matt Pocock pack or when the owner asks for git safety. On, off and check: `references/git-guard.md`.

## Adding a pack

A new pack in the installer needs `references/packs/<pack-id>.md`, and a new Sigma skill needs a `### <id>` section in `references/packs/sigma.md`. `test/sigmasetup.test.js` fails until both exist.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
