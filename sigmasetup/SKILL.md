---
name: sigmasetup
description: 'Use when asked for sigmasetup, to set up a repo after the Sigma installer, or to sync house files (ENGINEERING.md, DESIGN.md, AGENTS.md sections) from your masters. Do not use to install skills.'
---

# SigmaSetup

The installer puts skills on the machine. A repo still needs its own setup before they work well: tracker files, labels, tools, keys in the environment, a git guard, Ponytail. It also needs current **house files**: the copies of your master rule files (an `ENGINEERING.md`, a `DESIGN.md`, a shared section of `AGENTS.md`) that drift as the masters change. SigmaSetup finds what this repo lacks, asks once, sets up what you say yes to, and reports every change with its undo.

## Operating contract

- **Per repo.** Every write lands in the current repo; hooks go in its `.claude/`. User-level config (`~/.claude/settings.json`, `~/.codex`) stays as it is.
- **Report, then ask once, then act.** One list covers house-file drift and every pack, each item with a recommended yes or no. Write nothing before the owner answers.
- **Every change has an undo.** Each item names its undo command or the files to delete. The final report repeats them.
- **Keys by name only.** Keys go in the environment or an ignored `secrets/` folder. Never print a key.
- **The guides are the source.** `references/packs/<pack>.md` says what a pack needs; where a guide is silent, write "not stated".

## Flow

1. **House files.** Run `node <sigmasetup>/scripts/house.mjs check .` (`<sigmasetup>` is the folder this skill is installed in). It prints one row per house file: current, drift or missing, and the repo-only lines a section merge keeps. When it says there is no house source, ask the owner once where the masters live, and show how to save the answer: [house-files.md](references/house-files.md). Done when every house file has a row, or the owner says this repo has none.
2. **Packs.** Run `npx @djordje-stojanovic/sigmaskills status --project . --json` and `--global --json`; map each skill to its pack with `npx @djordje-stojanovic/sigmaskills list --packs`. For each pack with an installed skill, read `references/packs/<pack>.md` and check what is in place: files, labels (`gh label list`), tools on `PATH`, environment variables by name. A skill the installer did not install (a plugin, a hand copy) counts when the owner names it. Done when every item of every guide is marked present or missing.
3. **Ask once.** One numbered list: the house-file rows first (one item for the whole sync, and one per section with repo-only lines: keep them, or `--exact`), then pack by pack what is missing, the step that fixes it, its undo, and a recommended answer. Mark the owner's own steps: a login, a key, a purchase.
4. **Do the yes items.** House files: `node <sigmasetup>/scripts/house.mjs apply .` writes them all in one go and prints its undo command. A `seed` row means the repo lacks that file: write it from the named template with this repo's facts. Then each pack step. Check every step worked; run `house.mjs check .` again, it exits 0. Commit on a branch when the repo uses PRs.
5. **Report.** A table with the columns Item, Set up, Checked and Undo, one row per change, then what is left for the owner.

## Ponytail

Offer it for every repo where agents write code: `npx @djordje-stojanovic/sigmaskills ponytail --project .` turns on [Ponytail](https://github.com/DietrichGebert/ponytail) (the smallest code that works) for this repo in Claude Code, Codex and Pi. Check: `ponytail --check --project .`. Undo: `ponytail --remove --project .`.

## Git guard

An optional Claude Code hook for this repo only: it blocks force push, `reset --hard`, `clean -f`, `stash clear` and anything that throws away uncommitted changes (`checkout .`, `checkout -f`, `restore .`), and allows branch deletes. Offer it with the Matt Pocock pack or when the owner asks for git safety. On, off and check: [git-guard.md](references/git-guard.md).

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
