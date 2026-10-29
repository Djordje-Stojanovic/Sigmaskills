---
name: sigmasetup
description: 'Use when asked for sigmasetup or to set up installed skills in a repo after the Sigma installer. Per-project setup for each pack, with the owner. Do not use to install skills or for global setup.'
---

# SigmaSetup

The installer puts skills on the machine. Most packs still need a little per-project setup before they work well: a tracker file, labels, a tool, a key in the environment, a git guard. SigmaSetup finds what is installed, says what each pack needs in this repo, and does the setup the owner says yes to.

## Operating contract

- **Per project.** Every write lands in the current repo, hooks in its `.claude/`. User-level config (`~/.claude/settings.json`, `~/.codex`) stays as it is.
- **One question round, then act.** Show the plan for every installed pack in one list with a recommended answer each. Write nothing before the owner answers.
- **Every change can be undone.** Each item in the plan names its undo command or the files to delete. Report both at the end.
- **No secrets in the repo.** Keys go in the environment or an ignored `secrets/` folder. Never print a key.
- **The pack guides are the source.** `references/packs/<pack>.md` says what a pack needs; where a guide is silent, write "not stated".

## Flow

1. **Find what is installed.** Run `npx @djordje-stojanovic/sigmaskills status --project . --json` and `--global --json`. Map each skill to its pack with `npx @djordje-stojanovic/sigmaskills list --packs`. A skill the installer did not install (a plugin, a hand copy) counts when the owner names it. Done when every installed skill has a pack.
2. **Read the guides.** For each pack with at least one installed skill, read `references/packs/<pack>.md`. Check what is already in place: files, labels (`gh label list`), tools on `PATH`, environment variables by name. Done when every item in every guide is marked present or missing.
3. **Ask once.** One numbered list, pack by pack: what is missing, the step that fixes it, its undo, and a recommended yes or no. Mark the steps that are the owner's own: a login, a key, a purchase.
4. **Do the yes items.** Run each step, then check it worked. Commit repo files on a branch when the repo uses PRs.
5. **Report.** A table with the columns Pack, Set up, Checked and Undo, one row per change, then what is left for the owner.

## Git guard

An optional Claude Code hook for this repo only: it blocks force push, `reset --hard`, `clean -f` and whole-tree `checkout .` or `restore .`, and allows branch deletes. Offer it with the Matt Pocock pack or when the owner asks for git safety. On, off and check: `references/git-guard.md`.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
