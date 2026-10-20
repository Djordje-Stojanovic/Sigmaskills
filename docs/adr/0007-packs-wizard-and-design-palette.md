# Add packs, a full-screen wizard, and the DESIGN.md palette

**Status:** Accepted, 2026-10-20 (owner, ticket 83 P13.64). Supersedes the visual part of [0005](0005-use-the-emberforge-visual-language.md) and lifts the command freeze of [0006](0006-freeze-installer-commands.md) for the features below.

## Context

The owner compared the Sigma Installer with the install flow of Matt Pocock's skills (the `vercel-labs/skills` CLI that his README points to) and found ours lower in quality. The gaps were real:

- a flat list of 13 skills, no groups, no presets;
- it could install only the bundled Sigma skills, so "everything I use" needed three other tools;
- Agent Hosts were a 53-row alphabetical list; there was no `--agent claude`;
- the summary was a plain list of paths;
- the colors were the warm Emberforge palette, not the DESIGN.md palette that every other surface of ours uses.

0006 froze commands because the installer was large and nobody used `purge` or `restore`. It still is large, so the new code stays in new modules and does not touch the transaction engine.

## Decision

1. **Packs.** A pack is a named group of skills. `registry/packs.json` is a snapshot (ids and one-line descriptions) of five outside packs, so the picker needs no network. `src/packs.js` joins it with the bundled Sigma skills and with the owner's `~/.sigmaskills/packs.json`. A source is a `git` repository or a `dir` folder.
2. **One new engine for outside skills.** `src/pack-install.js` copies a skill to `.agents/skills/<id>`, links or copies it into host folders, and records ownership in `packs.json` in the existing private state folder. It does not use the Sigma transaction engine: outside skills have no Skill Revision, customization block, or baseline. It protects the same things (never touch an unowned folder, keep edited copies, back up before replacing) with a smaller mechanism.
3. **No new commands.** Presets are `--preset`; hosts are `--agent`; `update`, `uninstall`, `status`, and `list --packs` extend the commands that exist. `--all` keeps its meaning.
4. **A wizard for color terminals.** `src/wizard.js` shows What, Where, Review, then progress and a summary. Plain, static, CI, JSON, and piped sessions keep the line-by-line installer (`--classic` forces it). Both end in the same install functions, so a flag run and a wizard run write the same bytes.
5. **One palette.** `SIGMA_PALETTE` in `src/terminal.js` is the DESIGN.md palette (canvas `#09090b`, emerald `#34d399`, zinc ink, amber, red, sky) for both installers. The Emberforge palette is gone.

## Options considered

- **Delegate outside packs to `npx skills add`.** Least code, but a second UI, a second state file, and no control over presets or the summary. Rejected.
- **Vendor the outside skills into this repository.** Always offline, but it copies other people's work, goes stale, and breaks `npx skills add Djordje-Stojanovic/Sigmaskills`, which would then offer them. Rejected.
- **Put all of it in the Sigma transaction engine.** One mechanism, but the engine needs a revision and baseline per skill. Rejected for outside skills.

## Consequences

- Outside packs need `git` and the network at install time; the picker does not.
- The snapshot can go stale. `node scripts/packs-snapshot.js <clones>` rebuilds it, and `update` still installs whatever the repository holds today (a skill the snapshot lacks is not offered until the snapshot is rebuilt).
- `purge` and `restore` do not cover pack skills. `uninstall --all` does.
- Two engines now write skills. They share `links.js`, the lock, and the state folder, and the tests cover each.
