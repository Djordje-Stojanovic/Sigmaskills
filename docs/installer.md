# Installer guide

This guide covers the Sigma Installer (`npx @djordje-stojanovic/sigmaskills`) and the other ways to install SigmaSkills. For a first install, the [README quick start](../README.md#quick-start) is enough.

The Sigma Installer needs Node.js 22 or newer.

Run `npx @djordje-stojanovic/sigmaskills --help` for the full flag list of the Release you run.

Some short forms are hidden from `--help` on purpose. They work, and scripts may use them: `-g` (for `--global`), `--cwd` (for `--project`), `--list` (for the `list` command), and the `check` command (for `verify`).

## Contents

- [Scopes](#scopes)
- [Interactive install](#interactive-install)
- [Install from the command line](#install-from-the-command-line)
- [Existing copies](#existing-copies)
- [Global Installation](#global-installation)
- [Private state folder](#private-state-folder)
- [status](#status)
- [update](#update)
- [restore](#restore)
- [uninstall](#uninstall)
- [purge](#purge)
- [list and verify](#list-and-verify)
- [Other install methods](#other-install-methods)

## Scopes

The installer works in one scope at a time:

- **Project Installation** belongs to one project. It is the default. `--project <path>` selects another project root.
- **Global Installation** is available to every project of one operating-system user. It always needs an explicit choice. See [Global Installation](#global-installation).

## Interactive install

Run the installer with no command:

```bash
npx @djordje-stojanovic/sigmaskills
```

The installer reads the Skill Pack from `manifest.json` and the Agent Host registry that ships with it. It opens straight to the skill picker, under a small Sigma heading in the warm LAPI palette. Each skill shows its short description (`short_description` in `agents/openai.yaml`) on at most two lines.

Next, you choose destinations. Only the universal `.agents/skills/` folder is selected by default. The installer lists the Agent Hosts that read that folder. Host folders such as `.claude/skills` stay unselected until you choose them, even for detected hosts. Search finds every supported Agent Host, detected or not. A destination page shows at most eight rows and fits the terminal height. The first Escape on this page clears the search; a second Escape cancels.

If you chose a host folder, the next page is the Link/Copy page. **Link** (the default) keeps one canonical copy in `.agents/skills` and links the host folder to it. **Copy** writes a full copy into each host folder. If you chose only `.agents/skills`, this page does not appear.

The last page is the confirmation plan. It shows every full destination path and method. Long paths wrap onto more pages. Escape, EOF, Ctrl+C, or a "no" at the confirmation exits without writing. When the installer stops, it restores the cursor, raw mode, input, and listeners.

### Plain mode

The installer uses plain, line-based prompts with `--static`, `--no-color`, `--json`, `NO_COLOR`, `TERM=dumb`, `CI`, redirected output, or a session that is not a TTY. Enter one command per line:

| Input | Effect |
|-------|--------|
| a row number | Toggle that row |
| `/claude` | Search destinations for "claude" |
| `/` | Clear the search |
| `next`, `prev` | Change page (arrow keys do the same in interactive mode) |
| `a` | Select all skills, or clear all when every skill is already selected |
| `g` | Switch to Global Installation (shows the scope warning) |
| `?` | Help |
| `esc` | Cancel |
| Enter | Continue |
| `y`, then Enter | Confirm the installation |

Other display flags: `--no-color` turns color off, `--static` stops screen repainting, and `--narrow` uses the narrow-terminal layout. Reduced motion keeps the same picker without the opening animation.

## Install from the command line

Name one or more skill ids, or pass `--all`. `add` is an alias for `install`.

```bash
npx @djordje-stojanovic/sigmaskills install sigmawrite --project .
npx @djordje-stojanovic/sigmaskills install sigmawrite sigmareview sigmaship --project .
npx @djordje-stojanovic/sigmaskills install --all --project .
npx @djordje-stojanovic/sigmaskills install sigmawrite --project . --destination .claude/skills
npx @djordje-stojanovic/sigmaskills install sigmawrite --project . --destination .claude/skills --copy
npx @djordje-stojanovic/sigmaskills install sigmawrite --global --dry-run
npx @djordje-stojanovic/sigmaskills install sigmawrite --global --yes
```

What happens:

- The canonical copy of each skill goes to `.agents/skills/<id>`.
- `--destination <dir>` adds a host folder. You can repeat it.
- Host folders link to the canonical copy. Windows uses directory junctions; macOS and Linux use symbolic links. `--link` asks for links explicitly.
- `--copy` writes an independent managed copy at every selected destination instead.
- If a link fails, the installer reports the exact cause and offers a copy. It never changes the method silently.
- `--dry-run` shows the plan and writes nothing.
- `--json` prints the plan as JSON.

Several skills install in one transaction. The installer plans every skill first. If one skill fails, none stay installed. It writes `skills-lock.json` once. If `skills-lock.json` already exists and belongs to another tool (it has no Sigma `schemaVersion`), the installer leaves that file byte-identical, prints a notice, and skips the lock update. This holds for `install`, `uninstall`, and `restore`. The skill work itself still succeeds. With `--json`, several skills print `{ "schemaVersion": 1, "plans": [...] }`, and one skill prints one plan.

The installer checks input before it plans anything:

- An unknown skill id stops with `unknown skill '<id>'`.
- A flag that needs a value stops with the flag name when the value is missing or starts with `-`. For a value that really starts with `-`, write `--flag=value`.
- `--all` cannot be combined with skill ids.

## Existing copies

A skill folder can already exist, for example from `npx skills add`, the Codex installer, or a manual copy. The installer classifies it before it writes:

- **Current official copy or valid link:** the installer records it as managed. It does not rewrite the skill files.
- **Untouched copy of an earlier Release:** it matches a baseline in `registry/skill-baselines.json`. It shows as `legacy` with high provenance. It upgrades with no flag, after a private backup. `--adopt-legacy skip|export` still overrides that.
- **Managed copy that changed since the installer wrote it:** the installer shows a file diff with high confidence. You choose with `--adopt-changed`.
- **Sigma-looking copy with no matching baseline:** for example, an edited copy from another installer. The installer shows a file diff with low confidence. You choose with `--adopt-unverified`.
- **Malformed customization markers:** the install stops until you choose with `--adopt-malformed`.

The choices mean:

- `replace` takes a private backup first, then installs the official copy.
- `skip` leaves the folder as it is.
- `export` writes a collision-safe copy, in `--export-dir` when you give one.

The installer never guesses extra content in a pre-marker copy into the customization block.

## Global Installation

Project Installation stays the default. In the interactive installer, press `g` to switch to Global Installation. A scope warning appears at once. The final confirmation then repeats every selected Agent Host, resolved path, method, overwrite or delete effect, and backup action. A cancel at either prompt leaves user-level state unchanged.

Without the interactive installer, a global write needs both `--global` and `--yes`. CI, a TTY, `--json`, and Agent Host detection never count as that permission. `--global --dry-run` shows the full impact and writes nothing.

The installer stops on a global state file with an unknown, newer schema. Supported migrations keep ownership, hashes, methods, and backup references. Existing copies go through the same checks as in Project Installation.

## Private state folder

The installer keeps its private files in `.agents/.sigmaskills/`. For Global Installation, the folder is `~/.agents/.sigmaskills/`. It holds `state.json`, the `.sigma.lock` file, backups, journals, and staging.

The folder contains its own `.gitignore` with `*`. So `git add -A` stages only `.agents/skills/**` and `skills-lock.json`. The installer never edits your root `.gitignore`.

`--state-dir <dir>` or `SIGMA_STATE_DIR` chooses an exact folder instead. The installer never migrates that folder.

### Locks

Only one write command runs at a time in a scope. The `.sigma.lock` file enforces this:

- A lock expires after 24 hours.
- An incomplete lock record gets a five-second grace period.
- A short-lived `.sigma.lock.guard` folder serializes lock takeover and release.

A guard folder normally lives for milliseconds. If a crash leaves one, a command that finds it older than one minute stops with a `lock-guard-stale` error that names the folder. The installer never deletes it for you. Stop all SigmaSkills processes, remove that folder, and retry.

### Projects from 0.3.0 and older

Older projects keep these files directly in `.agents/`. `status` and every `--dry-run` read them there and write nothing. The next `install`, `update`, `uninstall`, `restore`, or `purge` moves them into `.agents/.sigmaskills/` in one step. A crash leaves either the old layout or the new one, never a mix.

If an interrupted `uninstall` or `purge` journal is still in the old layout, the installer stops. Finish that run with 0.3.0 first: `npx @djordje-stojanovic/sigmaskills@0.3.0 uninstall --all --yes`. 0.4.0 already uses the new layout, so it cannot finish that run.

## status

```bash
npx @djordje-stojanovic/sigmaskills status
npx @djordje-stojanovic/sigmaskills status --global --json
```

`status` is read-only. It reports Project Installation by default, or Global Installation with `--global`. The human and `--json` output name:

- the scope;
- the installed and the running Release;
- each Skill Revision;
- Agent Hosts, methods, exact paths, and ownership.

It checks live per-file hashes and links. A valid Skill Customization is drift, not damage. Drift still exits `0`; a command failure exits `1`.

`status` never migrates, repairs, or writes anything. It does not rewrite `skills-lock.json`, and it does not use the network.

## update

`update` moves whole skills to the Release of the CLI you run. Preview first:

```bash
npx @djordje-stojanovic/sigmaskills update --dry-run
npx @djordje-stojanovic/sigmaskills update --yes
npx @djordje-stojanovic/sigmaskills update --skill sigmareview --skill sigmaship
```

The preview:

- groups changed and unchanged skills and leaves out empty groups;
- shows the changelog sections newer than the installed Release, up to the running one;
- labels the running Release as newer, same, or older than the installed one;
- asks for a choice only for a skill with local or concurrent edits.

To apply, pass `--yes` for every changed skill, or `--skill <id>` (repeatable) for chosen skills. `--yes` works only when no skill is blocked. `--json` keeps its field names.

A skill that left the Skill Pack stays untouched. `update` lists it under *Retired skills* and names the `uninstall` command that removes it.

### Your customizations

Each `SKILL.md` has a Skill Customization block between markers. `update` copies the bytes in that block onto the new official `SKILL.md` exactly. The canonical `.agents/skills/<id>` copy owns the customization. Links and matching managed copies follow it.

The front-matter `description` is part of the customization too. If you change it, for example to fit a host's skill-list limit, `status` reports drift, not damage, and `update` keeps your text on the new `SKILL.md`. Two limits apply. If the new Release changes the official description, `update` cannot tell your edit from the old official text, so it asks for `--outside-edit` first. To get the official description back, run `install <id> --adopt-changed replace`.

### Edits outside the customization block

`update` classifies them as local-only or concurrent with an upstream change. The preview names each case and the overwrite or delete effect. You must choose `--outside-edit replace|skip|export` before `update` writes:

- `replace` takes a complete, integrity-checked private backup, then updates.
- `skip` leaves that skill and its state untouched. Other skills continue.
- `export` copies the old folder to a planned path. It refuses a path that already exists.

### Malformed markers

A missing, duplicated, reversed, or nested marker blocks the automatic update for that skill. `update` never guesses a customization boundary. The preview shows the marker shape. When exactly one mechanical repair exists, it shows the repair bytes and the resulting changes. You must choose `--malformed-markers skip|repair|replace`:

- `skip` leaves that skill unchanged. Other skills continue.
- `repair` writes only the approved, exact repair.
- `replace` takes a complete private backup, then installs a clean official copy.

When a skill has malformed markers and outside edits, `update` keeps all content until you pass both flags.

### Safety

- A cancel, an invalid repair, an editor failure, a backup failure, or a transaction failure writes nothing partial.
- The latest valid backup stays until the new folder and its backup record commit. If cleanup fails, two backups can stay, and the state records the cleanup debt.
- `update` stops without writing on an unknown, newer state schema, a missing Skill Revision, a broken link, or copies that disagree.
- `update` uses the same transaction as `install` and refreshes state only after the commit.

## restore

`restore` brings back the latest retained backup of one skill.

```bash
npx @djordje-stojanovic/sigmaskills restore --skill sigmareview --dry-run
npx @djordje-stojanovic/sigmaskills restore --skill sigmareview --yes
```

The preview shows the Release and Skill Revision when known, the creation date, the verified size, the scope, the canonical target, and the affected links or copies.

With `--yes`, the installer stages the backup and checks its integrity before any live write. After a successful restore, the replaced folder becomes the new backup. Restoring identical content changes nothing and keeps the backups as they are. A removed skill can come back from its ownership record, without claiming unrelated paths.

`restore` stops and keeps the live folder and the backup intact when the backup is missing, truncated, tampered with, or from an incompatible schema. It also stops on low disk space, stale ownership, an unowned folder in the way, or a failed Windows fallback.

## uninstall

Every uninstall starts with an Uninstall Review. There is no way to skip it.

```bash
npx @djordje-stojanovic/sigmaskills uninstall --skill sigmareview --dry-run
npx @djordje-stojanovic/sigmaskills uninstall --all --dry-run
npx @djordje-stojanovic/sigmaskills uninstall --all --yes
```

`--skill <id>` reviews chosen skills. `--all` reviews every recorded Sigma skill in one scope. You cannot combine the two. The plan lists every skill, owned destination, canonical dependency, state change, and retained backup.

Each skill needs a choice:

| Skill is | Flag | Choices |
|----------|------|---------|
| Clean | `--clean` | `remove` (default with `--yes` or `--all`), `keep` |
| Changed, customized, or malformed | `--changed` | `backup` (default with `--all`), `keep`, `export`, `delete` |

What each choice does:

- `remove` deletes only Sigma-owned paths, checked again just before the delete.
- `backup` takes a snapshot of the current folder, then removes it. `restore` can bring it back.
- `export` copies the current folder to `--export-dir`, then removes the managed paths.
- `delete` removes the current content. An older retained backup stays.
- `keep` writes nothing. Shared state and canonical dependencies stay intact.

Rules during the run:

- Each path is checked again with `lstat`. A link is deleted itself, never its target.
- Canonical content stays until its recorded dependents are gone.
- With `--skill`, a missing path, stale state, an unowned replacement, a managed copy that differs, or a link to the wrong target stops the run. Ownership does not change.
- With `--all`, those cases skip that one skill. The rest continue, and the result lists it as skipped.
- If the run is interrupted or fails, a recovery journal (`uninstall-journal.json`) stays in the private state folder. The failed skill is restored, so no partial links remain.
- State and the lock update only after the file operations commit.

A project `uninstall --all` never writes Global Installation. A global `uninstall --all` never scans projects.

The human, dry-run, and JSON results list removed, retained, skipped, and failed skills. A failed skill makes the command exit `1`.

## purge

`purge` removes all Sigma-owned content in one scope: owned folders, links or junctions, copies, backups, staging, journals, and the relevant locks.

```bash
npx @djordje-stojanovic/sigmaskills purge --dry-run
npx @djordje-stojanovic/sigmaskills purge --confirm-purge "purge SigmaSkills"
```

`--dry-run` lists the exact plan. `purge` never guesses ownership from folder names.

To apply, type the phrase `purge SigmaSkills` when asked. Without a prompt, pass `--confirm-purge "purge SigmaSkills"`. `--yes`, CI, a non-TTY session, and `--json` do not count as confirmation.

Safety:

- A project purge never writes Global Installation. A global purge never scans projects.
- An unowned item in the way stops the command and stays untouched.
- A delete across file systems writes a journal first. Owned folders go to quarantine before the ownership record is removed.
- An interrupted purge leaves quarantined state that can be recovered, never active partial links. Run it again with the same phrase to finish.

## list and verify

- `list` prints every skill in the Skill Pack with its Skill Revision and short description. `list --json` gives the full description and the file list.
- `verify` checks the manifest and every skill's files and prints each Skill Revision.

## Other install methods

These methods copy skills without the Sigma Installer. They have no `status`, `update`, `restore`, or `uninstall`. The Sigma Installer can adopt these copies later; see [Existing copies](#existing-copies).

Every [GitHub Release](https://github.com/Djordje-Stojanovic/Sigmaskills/releases) has a matching git tag. Every Release from 0.2.0 on is also on npm, except 0.2.1. 0.1.0 and 0.2.1 are GitHub Releases only. A skill that is in the repository but not yet in a Release is available only from the repository source.

### `npx skills`

The cross-agent [skills](https://github.com/vercel-labs/skills) CLI detects Codex, Claude Code, Cursor, OpenCode, Pi, and many more hosts.

```bash
# Everything, all detected agents, global
npx skills add Djordje-Stojanovic/Sigmaskills --all -g -y

# One skill at a time
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmareview -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmaimprove -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmabrief -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmaship -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmawrite -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmarefactor -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill easytalk -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill storgestudio-arena-create -g
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmaresearch -g

# Pin to specific hosts
npx skills add Djordje-Stojanovic/Sigmaskills --skill sigmawrite -g -a cursor -a claude-code -a codex -a opencode -a pi

# List what this repository ships, without installing
npx skills add Djordje-Stojanovic/Sigmaskills --list

# The full GitHub URL also works
npx skills add https://github.com/Djordje-Stojanovic/Sigmaskills --skill sigmabrief -g
```

### Codex

```text
$skill-installer install sigmareview from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmaimprove from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmabrief from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmaship from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmawrite from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmarefactor from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install easytalk from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install storgestudio-arena-create from https://github.com/Djordje-Stojanovic/Sigmaskills
$skill-installer install sigmaresearch from https://github.com/Djordje-Stojanovic/Sigmaskills
```

### Manual copy

Use this when a host only watches a skills folder: Pi, custom TUIs, or air-gapped machines.

**POSIX**

```bash
git clone https://github.com/Djordje-Stojanovic/Sigmaskills.git
mkdir -p ~/.agents/skills
cp -R Sigmaskills/sigmareview ~/.agents/skills/sigmareview
cp -R Sigmaskills/sigmaimprove ~/.agents/skills/sigmaimprove
cp -R Sigmaskills/sigmabrief ~/.agents/skills/sigmabrief
cp -R Sigmaskills/sigmaship ~/.agents/skills/sigmaship
cp -R Sigmaskills/sigmawrite ~/.agents/skills/sigmawrite
cp -R Sigmaskills/sigmarefactor ~/.agents/skills/sigmarefactor
cp -R Sigmaskills/easytalk ~/.agents/skills/easytalk
cp -R Sigmaskills/storgestudio-arena-create ~/.agents/skills/storgestudio-arena-create
cp -R Sigmaskills/sigmaresearch ~/.agents/skills/sigmaresearch
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/Djordje-Stojanovic/Sigmaskills.git
New-Item -ItemType Directory -Force -Path "$HOME\.agents\skills" | Out-Null
Copy-Item -Recurse Sigmaskills\sigmareview   "$HOME\.agents\skills\sigmareview"
Copy-Item -Recurse Sigmaskills\sigmaimprove  "$HOME\.agents\skills\sigmaimprove"
Copy-Item -Recurse Sigmaskills\sigmabrief    "$HOME\.agents\skills\sigmabrief"
Copy-Item -Recurse Sigmaskills\sigmaship     "$HOME\.agents\skills\sigmaship"
Copy-Item -Recurse Sigmaskills\sigmawrite    "$HOME\.agents\skills\sigmawrite"
Copy-Item -Recurse Sigmaskills\sigmarefactor "$HOME\.agents\skills\sigmarefactor"
Copy-Item -Recurse Sigmaskills\easytalk      "$HOME\.agents\skills\easytalk"
Copy-Item -Recurse Sigmaskills\storgestudio-arena-create "$HOME\.agents\skills\storgestudio-arena-create"
Copy-Item -Recurse Sigmaskills\sigmaresearch "$HOME\.agents\skills\sigmaresearch"
```

Point other hosts at the same folders, or copy again:

| Host family | Typical skills path |
|-------------|---------------------|
| Universal (Codex-style hosts, Pi) | `~/.agents/skills/<id>/` |
| Cursor | `~/.cursor/skills/<id>/` or project `.agents/skills/` |
| Claude Code | `~/.claude/skills/<id>/` |
| OpenCode | `~/.config/opencode/skills/<id>/` |
| Codex | `~/.codex/skills/<id>/` |
