# Research: Sigma Installer — Update, Uninstall, Backup, and Customization-Preservation Model

## Summary

The reference implementation to copy and improve on is **vercel-labs/skills** (the `npx skills` CLI): a canonical-copy + per-host symlink layout, two lockfiles (`~/.agents/.skill-lock.json` global, `skills-lock.json` committed in the project), content-hash-driven update detection, destructive full-folder replacement (`rm` + `mkdir`) on every install/update, and a lockfile that doubles as the uninstall manifest. Its main gap is that **local user edits inside an installed skill are silently destroyed on update** — no merge, no backup, no marker tracking.

Proven alternatives from package managers and config-managed tools (npm hidden lockfile + SRI integrity, kubectl `last-applied-configuration` three-way merge, Debian conffile preservation, Ansible timestamped backups + atomic writes, chezmoi interactive three-state merge, yadm sidecar alternates) converge on one minimal architecture: **store a per-file SHA-256 "base" manifest in the lock at install time, then on update compare three states (base vs on-disk "live" vs freshly-fetched "upstream") and resolve with overwrite-if-clean, keep-local-warn if only local changed, and snapshot-or-merge if both changed.** Marker blocks inside `SKILL.md` are spec-legal but unsafe as the primary customization mechanism (agent-visible content pollution, host frontmatter strictness); sidecar overlays and lockfile metadata are safer. Backups should be a single timestamped pre-update snapshot per skill (Ansible `backup: yes` semantics), atomic writes via stage-then-`rename()` (POSIX-guaranteed atomic), and uninstall should follow dpkg's remove-vs-purge split: keep config on remove, delete everything on purge.

---

## Findings

### 1. vercel-labs/skills architecture: canonical copy + symlinks, per-host and universal

- One canonical copy per skill in `~/.agents/skills/<name>` (global) or `./.agents/skills/<name>` (project); every host's skills dir gets a **symlink** to it (`~/.claude/skills/<name>`, `~/.cursor/skills/<name>`, …). Symlink failure falls back to an independent copy (`--copy` mode forces copies). Windows uses junctions (`platform() === 'win32' ? 'junction'`). [src/installer.ts](https://github.com/vercel-labs/skills/blob/main/src/installer.ts) [README.md](https://github.com/vercel-labs/skills/blob/main/README.md)
- "Universal" agents read the canonical dir directly and get no symlink — one write serves all of them. Per-agent global dirs are optional (`globalSkillsDir === undefined` → host does not support global install). ~90 hosts are registered in `package.json` keywords/`src/agents.ts`. [src/installer.ts](https://github.com/vercel-labs/skills/blob/main/src/installer.ts), [package.json](https://github.com/vercel-labs/skills/blob/main/package.json)
- **Relevance for Sigma:** this exact model is already the repo's plan — README's host table (`~/.agents/skills/` universal, `~/.claude/skills/`, `~/.cursor/skills/`, `~/.codex/skills/`, `~/.config/opencode/skills/`, `~/.pi/agent/skills/`) and `CONTEXT.md` ("Sigma Installer … lets a person select skills from the Skill Pack"). [README.md](../README.md)

### 2. Lockfile design (vercel + npm): two locks, versioned schema, merge-friendly project lock

- **Global lock** `~/.agents/.skill-lock.json` (or `$XDG_STATE_HOME/skills/`): schema `version` (currently 3), `skills: {name → {source, sourceType, sourceUrl, ref, skillPath, skillFolderHash, installedAt, updatedAt, pluginName?, wellKnownDigest?}}`. Old-version locks are **wiped** ("backwards incompatible change") rather than migrated. [src/skill-lock.ts](https://github.com/vercel-labs/skills/blob/main/src/skill-lock.ts)
- **Project lock** `skills-lock.json` (committed to VCS): deliberately "minimal and timestamp-free to minimize merge conflicts. Two branches adding different skills produce non-overlapping JSON keys that git can auto-merge cleanly"; entries are written **alphabetically sorted**; `sourceType: 'local'` sources stored as portable relative paths. [src/local-lock.ts](https://github.com/vercel-labs/skills/blob/main/src/local-lock.ts)
- npm parallels: `package-lock.json` is "automatically generated for any operations where npm modifies either the `node_modules` tree, or `package.json`… intended to be committed into source repositories", and npm v7+ keeps a **hidden lockfile** `node_modules/.package-lock.json` describing the on-disk tree — used to skip rescanning and **invalidated by any external mutation** ("If another CLI mutates the tree in any way, this will be detected, and the hidden lockfile will be ignored", mtime-based). [npm package-lock docs](https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json/)
- **Decision inputs:** project lock should stay timestamp-free + sorted (vercel precedent, proven merge behavior); a global lock can carry timestamps; the hidden-lockfile idea (separate on-disk state manifest from the committed manifest) is worth adopting — it is precisely what enables uninstall and drift detection without trusting `package.json`.

### 3. Integrity hashes: three different purposes, three proven mechanisms

- **Change detection (upstream):** vercel uses the **GitHub Trees API tree SHA of the skill folder** (git SHA-1 of the tree object) for the global lock, and for the project lock a **deterministic SHA-256 over every file's relative path + content** (sorted by path so renames are detected). [src/skill-lock.ts](https://github.com/vercel-labs/skills/blob/main/src/skill-lock.ts), [src/local-lock.ts](https://github.com/vercel-labs/skills/blob/main/src/local-lock.ts). Local clones compute the same folder SHA via `git rev-parse HEAD:<folder>` so the two paths agree. [src/git.ts](https://github.com/vercel-labs/skills/blob/main/src/git.ts)
- **Authenticity (download):** npm stores SRI `integrity` (`sha512`/`sha1` "Standard Subresource Integrity string **for the artifact that was unpacked** in this location"; git deps store the commit sha). This is integrity of the fetched artifact, distinct from change detection. [npm package-lock docs](https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json/)
- **Fingerprinting (state):** Ansible template/copy modules return a `checksum` (SHA1) of the rendered file — used to decide "changed" without re-reading semantics. [Ansible template module](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/template_module.html)
- **Decision inputs:** lock should store (a) per-file SHA-256 of installed content = the **base**, (b) upstream folder hash = change signal, (c) for direct-download sources, an SRI-style hash of the fetched artifact where available. vercel's limitation to note: it hashes to *detect* upstream change, never to *preserve* local edits — see finding 4.

### 4. Overwrite handling: vercel replaces everything; Debian, npm, chezmoi preserve or prompt

- vercel's `cleanAndCreateDirectory` does `rm(path, {recursive, force})` then `mkdir` **on every install**, and `add` only *reports* "overwrites: <agents>" in the summary — there is no diff, merge, backup, or confirmation-before-clobber. A user edit inside an installed skill is silently destroyed on the next `update`. [src/installer.ts](https://github.com/vercel-labs/skills/blob/main/src/installer.ts), [src/add.ts](https://github.com/vercel-labs/skills/blob/main/src/add.ts)
- npm `ci` is equally destructive but *deliberately*: "If a `node_modules` is already present, it will be automatically removed before `npm ci` begins" — safe only because the lockfile fully describes the tree to restore, and `ci` "never write[s] to `package.json` or any of the package-locks". [npm ci docs](https://docs.npmjs.com/cli/v11/commands/npm-ci)
- **Debian policy is the counter-model and the one Sigma should follow:** "local changes must be preserved during a package upgrade, and configuration files must be preserved when the package is removed, and only deleted when the package is purged." dpkg implements this for conffiles by asking the user (keep theirs / install new / see diff) and keeping both sides as backup files (`.dpkg-old` / `.dpkg-dist`-style, listed as `.dpkg-{old,new,tmp}` in policy §6.8). [Debian Policy §10.7.3](https://www.debian.org/doc/debian-policy/ch-files.html), [§6.8](https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html)
- chezmoi: `apply --interactive` detects destination ≠ target and prompts **overwrite / diff / skip / merge**; the file is only replaced with the user's consent. [chezmoi merge guide](https://www.chezmoi.io/user-guide/tools/merge/)
- **Decision inputs:** full-replace is acceptable only when the tool provably owns the whole directory and the lock can rebuild it (npm ci model). Since users *do* edit installed skills (the whole point of this research), Sigma needs detection + a preservation path (findings 5–7).

### 5. Detecting upstream/local/base changes: the kubectl three-state model

- kubectl `apply` is the canonical proof that three-state diffing works with a small sidecar: it stores the exact applied config in the `kubectl.kubernetes.io/last-applied-configuration` annotation (the **base**), then on each apply computes a patch from three inputs — configuration file (latest), live object (current on-disk), last-applied annotation (base): fields in base but missing from config are **deleted**; fields in config differing from live are **set**; live fields untouched by config are **kept**. Manual edits survive; upstream removals are applied. [kubectl declarative configuration docs](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/declarative-config/)
- Mapping to Sigma: **base** = per-file hashes recorded in the lock at install; **live** = current disk state (re-hash at update time); **upstream** = freshly fetched folder. Three booleans fall out: `upstreamChanged` (upstream hash ≠ base), `localChanged` (live hash ≠ base), plus the clean case. This is cheap, deterministic, and needs no marker blocks.
- npm's hidden lockfile invalidation (finding 2) is the same idea for detecting *external* mutation of the tree.
- **Decision inputs:** detect, don't guess — re-hash every file at update time; treat mtime-only heuristics as unreliable (npm explicitly warns mtime can be fooled by content edits). [npm package-lock docs](https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json/)

### 6. Marker blocks inside SKILL.md: legal but not safe as the primary mechanism

- The spec permits anything in the body ("There are no format restrictions") but the whole file is loaded into agent context on activation ("the agent will load this entire file once it's decided to activate a skill"). [Agent Skills specification](https://agentskills.io/specification) (also [raw spec source](https://raw.githubusercontent.com/agentskills/agentskills/refs/heads/main/docs/specification.mdx))
- Consequences for in-body markers (`<!-- sigma:start -->…` or `# >>> managed by sigma`): (a) the marker text becomes **agent-visible content** — token cost, and if an agent ever *acts* on marker-adjacent text, a prompt-injection surface; (b) hosts differ in what they tolerate — vercel strips non-whitelisted **frontmatter** keys for Eve (`stripIgnoredEveFrontmatter` keeps only `description`, `license`, `metadata`) rather than adding anything, showing that some hosts are strict about metadata; (c) markers only help *this* installer find its own injected block — they don't help detect user edits anywhere else in the file, which is the real problem. [src/installer.ts](https://github.com/vercel-labs/skills/blob/main/src/installer.ts)
- Marker blocks *are* proven in this ecosystem, but only for files the tool fully owns and agents never read as instructions: vercel's own README uses `<!-- agent-list:start -->…<!-- agent-list:end -->` sections regenerated by `scripts/sync-agents.ts`. [README.md](https://github.com/vercel-labs/skills/blob/main/README.md), [scripts/sync-agents.ts](https://github.com/vercel-labs/skills/blob/main/scripts/sync-agents.ts)
- The spec's sanctioned extensibility point is the **frontmatter `metadata` map** ("Clients can use this to store additional properties not defined by the Agent Skills spec. We recommend making your key names reasonably unique") — but Eve's stripping shows host parsers can drop unknown keys, so it is fine for *read-only* provenance, not for round-tripping installer state. [Agent Skills specification](https://agentskills.io/specification)
- **Decision inputs:** never write installer state into SKILL.md body; keep the canonical copy byte-identical to upstream; put installer state in the lock file. If a managed-section marker is ever needed, restrict it to HTML comments in a file the tool fully owns (e.g., a generated `README.md` inside the installed dir, or the lock), never in SKILL.md.

### 7. Three-way merge vs sidecar overlays: overlay by default, merge on conflict

- **Three-way merge is available as a primitive:** `git merge-file <current> <base> <other>` "incorporates all changes that lead from base to other into current", writes conflict markers (`<<<<<<<`/`=======`/`>>>>>>>`), and exits with the number of conflicts (0 = clean). `--ours`/`--theirs`/`--union` give policy-driven auto-resolution. [git-merge-file docs](https://git-scm.com/docs/git-merge-file) — ships with git, which the installer already requires to fetch skills.
- chezmoi's interactive merge is the UX precedent: three states — **Destination** (the file on your system), **Source** (source of truth), **Target** (desired state after rendering) — with overwrite / diff / skip / merge choices. [chezmoi merge guide](https://www.chezmoi.io/user-guide/tools/merge/)
- **Sidecar overlays** avoid merging entirely: yadm keeps alternates as separate files selected by filename suffix (`example.txt##os.Darwin`) and, for formats with an include mechanism, a `.gitconfig.local` file included from the managed file — "the bulk of your configurations can go in a single file, and you just put the exceptions in OS-specific files". [yadm alternates](https://yadm.io/docs/alternates)
- For SKILL.md specifically: the format has no include directive, but the spec's **progressive disclosure** means agents load `references/` on demand — so a user-customization **sidecar overlay** (`<skill>/.sigma-local/` merged over the upstream tree at install, or a per-host overlay dir) preserves user additions without ever editing upstream files. That mirrors both yadm's philosophy and vercel's host-specific transforms (Eve rewrite happens only for the Eve copy).
- **Decision inputs:** default resolution = clean replace when only upstream changed; keep-local + warn when only local changed; when both changed: interactive → three-way merge via `git merge-file` (base from lock, ours = live, theirs = upstream) with a Debian-style prompt; non-interactive/CI → take upstream and snapshot the local version (finding 8). Use `--union`/`--ours` policy only for degenerate cases. Line-based merge of SKILL.md prose is imperfect (kubectl-style field-aware merge does not apply to markdown), so treat merge output as advisory with conflict markers surfaced to the user, never auto-committed.

### 8. Backup naming and retention: one timestamped snapshot per skill, Ansible-style

- Ansible `backup: yes` on template/copy modules: "Create a backup file **including the timestamp information** so you can get the original file back if you somehow clobbered it incorrectly." [Ansible template module](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/template_module.html) — a single timestamped copy, not a rotated archive; no retention policy beyond "the previous version".
- Debian keeps the *user's* modified conffile (not the new one) when it cannot auto-resolve, and deletes backup files on **purge** only. [Debian Policy §6.8](https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html)
- vercel/npm/chezmoi do **no** automatic backups (chezmoi relies on git history of the source state; npm has none for node_modules).
- **Decision inputs:** backup dir `<state>/backups/<skill>/<UTC-ISO-timestamp>/` holding the full pre-update skill tree; retention = keep the latest snapshot per skill, replaced when the next update commits successfully (one-generation rollback, matching Ansible); delete backups on uninstall-purge (matching dpkg). Do not build a log-rotation system — it is not asked for.

### 9. Atomic writes and rollback: stage, fsync, `rename()`, keep the old tree

- POSIX guarantees `rename()` atomicity: "That specification requires that the action of the function be atomic", and "a link named _new_ shall remain visible to other threads throughout the renaming operation and refer either to the file referred to by _new_ or _old_ before the operation began". [POSIX.1-2017 rename(3)](https://pubs.opengroup.org/onlinepubs/9699919799/functions/rename.html)
- Ansible: "By default this module uses atomic operations to prevent data corruption or inconsistent reads", with `unsafe_writes` as an explicit fallback for filesystems that can't do it (e.g., docker mounts), and a `validate` step (e.g., `visudo -cf %s`) run against a temp file before the swap. [Ansible template module](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/template_module.html)
- vercel writes files directly into the destination (`writeFile`) and does `rm`+`mkdir` — no staging, no rollback; a crash mid-copy leaves a half-installed skill. [src/installer.ts](https://github.com/vercel-labs/skills/blob/main/src/installer.ts)
- **Decision inputs for Sigma:** per skill: (1) fetch/stage the new tree into `<canonicalParent>/.sigma-staging/<skill>-<ts>` (same filesystem, so `rename` cannot hit `EXDEV`); (2) validate — parse SKILL.md frontmatter (`name` present, lowercase-hyphen, and equal to the target dir name per spec) — before commit; (3) snapshot the current tree to backups (finding 8); (4) `rename(staging → live)`; (5) on any failure, restore from the snapshot; (6) serialize concurrent runs with a lockfile (`.sigma.lock`) — the pattern every package manager uses, and which the update flow in vercel already implicitly relies on by re-spawning `add`.

### 10. Global-install confirmation: prompt before global writes; auto-yes only in CI/agent contexts

- `npx`/`npm exec` is the direct precedent: "To prevent security and user-experience problems from mistyping package names, **npx prompts before installing anything**. Suppress this prompt with the `-y` or `--yes` option"; and "When standard input is not a TTY or a CI environment is detected, `--yes` is assumed." [npm exec docs](https://docs.npmjs.com/cli/v11/commands/npm-exec)
- vercel's `add` shows an install summary before writing: per-skill canonical path, per-host targets, explicit `overwrites: <agents>` yellow warnings, and agent selection prompts; `-y`/`--yes` skips everything; and when run *inside* an AI agent (`detectAgent()`), the CLI auto-enables non-interactive mode. [src/add.ts](https://github.com/vercel-labs/skills/blob/main/src/add.ts), [src/remove.ts](https://github.com/vercel-labs/skills/blob/main/src/remove.ts)
- npm also offers `--dry-run` ("report what it would have done") on install/update/uninstall. [npm update docs](https://docs.npmjs.com/cli/v11/commands/npm-update)
- **Decision inputs:** global (`-g`) installs must confirm scope + host list + overwrite list before any write; `-y` for scripting; auto-yes when non-TTY/CI *or* when invoked by an agent (vercel precedent); a `--dry-run` that diffs base/live/upstream is cheap and very decision-relevant for an installer.

### 11. Uninstall manifests: the lock is the manifest; remove ≠ purge

- npm: `npm uninstall` "uninstalls a package, **completely removing everything npm installed on its behalf**" and updates `package.json` + lockfiles; the lockfile (incl. the hidden `node_modules/.package-lock.json`) is the manifest that makes this safe. [npm uninstall docs](https://docs.npmjs.com/cli/v11/commands/npm-uninstall), [npm package-lock docs](https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json/)
- Debian distinguishes **remove** (package files go, conffiles stay) from **purge** (conffiles and backups go). [Debian Policy §6.8](https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html)
- vercel `remove`: scans canonical + all host dirs, resolves names with **lock keys winning over on-disk folder names**, deletes per-host paths, and **only deletes the canonical copy and lock entry when no other host still links the skill** (explicitly fixing the "uninstall from one host broke others" bug, #287, and "stale lock entry while skill still installed" #1718). Stale lock entries are cleaned even when the folder is already gone. [src/remove.ts](https://github.com/vercel-labs/skills/blob/main/src/remove.ts)
- **Decision inputs:** the lock file is the single source of truth for what the installer owns; uninstall removes exactly the paths recorded in the lock (per-host links/copies), keeps the canonical copy while any host still uses it, then removes the lock entry; `--purge` additionally deletes backups and overlays (dpkg semantics). Upstream-deleted skills: vercel prompts to remove local copies on `update` and skips in non-interactive mode — adopt the same, non-destructively.

### 12. Update mechanics: vercel's update = reinstall, which is worth keeping

- vercel `update`: groups locked skills by source, fetches the upstream folder hash (GitHub Trees API, falling back to a depth-1 git clone; `GH_HOST` pinned to github.com so an enterprise host can't redirect an existing public install), compares with the recorded hash, and for each changed skill re-spawns `add <source> --skill <name> -g -y` (self-reinstall from lock-recorded source/ref/skillPath). Skills without a hash or path (local paths, generic git URLs, private repos without auth) are reported as "cannot be checked automatically". Project updates clone, discover, and re-`add` into the project. [src/update.ts](https://github.com/vercel-labs/skills/blob/main/src/update.ts)
- npm update: "update all the packages listed to the latest version… respecting the semver constraints"; global packages have no range so `wanted` = `latest`. [npm update docs](https://docs.npmjs.com/cli/v11/commands/npm-update)
- **Decision inputs:** "update = reinstall from the lock" is simple, correct, and proven — keep it, but insert the three-state check (finding 5) and the atomic commit (finding 9) between detection and replacement. Pinning the update source to the recorded URL/host is a real supply-chain control (vercel does it); Sigma should too.

---

## Recommended minimal architecture

Decisions are stated; each traces to a finding.

1. **Layout (F1, F11):** canonical copy per skill + per-host symlink (copy fallback), universal hosts read canonical directly. Host map: the one already documented in this repo's README (`.agents/skills`, `.claude/skills`, `.cursor/skills`, `.codex/skills`, `.config/opencode/skills`, `.pi/agent/skills`).
2. **Two lockfiles (F2, F3):** committed project lock `skills-lock.json` — versioned schema, timestamp-free, alphabetically sorted, git-merge-friendly; per entry: `{source, sourceUrl, ref, skillPath, hosts[], mode, files: {relPath → sha256}}` (per-file hashes = the base). Global lock in user state dir with the same entry shape plus `installedAt/updatedAt`. Record an SRI-style artifact hash for direct-download sources (F3). Version-bump schema; wipe-on-old-version only for the *global* lock, migrate-or-reinstall for the project lock.
3. **Update flow (F5, F12):** `update` = for each locked skill: fetch upstream folder hash (tree SHA via API or depth-1 clone, source URL pinned from the lock) → compute live hashes of the on-disk tree → compare **upstream vs base vs live**:
   - all equal → skip;
   - upstream only changed → stage + atomic replace, refresh base in lock;
   - live only changed → keep local, warn, tell the user how to restore upstream (`--force`) or export their copy;
   - both changed → interactive: Debian-style prompt (keep local / take upstream / three-way merge via `git merge-file` with conflict markers surfaced) ; non-interactive: take upstream + snapshot local (F7, F4).
4. **Customization preservation (F6, F7):** no marker blocks in SKILL.md; upstream files stay byte-identical in the canonical copy; user additions go to a **sidecar overlay** merged at install time (yadm `.local` pattern); host-specific rewrites (Eve-style frontmatter stripping) apply only to that host's copy; installer state lives only in the lock. Optionally stamp provenance in frontmatter `metadata` (read-only; hosts may strip it).
5. **Backups (F8):** before any replacement, copy the current skill tree to `<state>/backups/<skill>/<UTC-ISO-timestamp>/`; keep the newest snapshot per skill; delete on `--purge`.
6. **Atomic commit (F9):** stage to same-filesystem temp, validate frontmatter (name present, lowercase-hyphen, == dirname per spec), snapshot, `rename()` over the live dir, restore from snapshot on failure, `.sigma.lock` to serialize runs.
7. **Global install confirmation (F10):** prompt with scope + hosts + overwrite warnings before any global write; `-y`; auto-yes on non-TTY/CI/agent invocation; `--dry-run` diff available.
8. **Uninstall (F11):** lock = manifest; remove per-host links/copies; keep canonical while any host uses it; remove lock entry; `--purge` also deletes backups/overlays; upstream-deleted skills offered for removal on update (non-interactive: skip).
9. **Integrity (F3):** verify downloaded artifacts with SRI-style hashes where available; use content hashes for all change detection; never trust mtimes.

**Total surface:** one lock schema, one hash util, one staging/commit util, one diff+resolve policy, one prompt set — no merge engine dependency beyond `git merge-file`, no marker parsing, no backup rotation.

---

## Sources

**Kept (primary):**

- vercel-labs/skills (cloned HEAD; cited by path): `src/skill-lock.ts`, `src/local-lock.ts`, `src/update.ts`, `src/remove.ts`, `src/installer.ts`, `src/add.ts`, `src/git.ts`, `src/constants.ts`, `scripts/sync-agents.ts`, `package.json`, `skills/find-skills/SKILL.md`, README.md — the current state of the art for skill-CLI install/update/remove, lockfiles, hashing, host support. https://github.com/vercel-labs/skills
- Agent Skills specification — SKILL.md frontmatter rules, "no format restrictions" body, whole-file loading, `metadata` extensibility. https://agentskills.io/specification (source: https://raw.githubusercontent.com/agentskills/agentskills/refs/heads/main/docs/specification.mdx)
- npm docs: package-lock.json (hidden lockfile, integrity SRI), npm ci (removes node_modules, frozen), npm uninstall ("everything npm installed on its behalf"), npm update (semver semantics, dry-run), npm exec (npx prompts before installing; auto-`--yes` off-TTY). https://docs.npmjs.com/cli/v11/...
- kubectl declarative configuration — `last-applied-configuration` annotation, three-state patch calculation, prune/ApplySet ownership tracking. https://kubernetes.io/docs/tasks/manage-kubernetes-objects/declarative-config/
- Debian Policy §10.7.3 (conffiles: "local changes must be preserved during a package upgrade… only deleted when the package is purged") and §6.8 (remove vs purge, backup files `.dpkg-{old,new,tmp}`). https://www.debian.org/doc/debian-policy/ch-files.html, https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html
- Ansible template module — `backup: yes` (timestamped), atomic-by-default with `unsafe_writes` fallback, `validate` pre-commit step, `ansible_managed`, checksum return. https://docs.ansible.com/ansible/latest/collections/ansible/builtin/template_module.html
- chezmoi merge guide — three states (destination/source/target), overwrite/diff/skip/merge prompts. https://www.chezmoi.io/user-guide/tools/merge/
- yadm alternates — `##condition` suffix sidecars and `.gitconfig.local` include pattern. https://yadm.io/docs/alternates
- git-merge-file — three-way merge primitive, conflict markers, `--ours/--theirs/--union`, exit code = conflict count. https://git-scm.com/docs/git-merge-file
- POSIX.1-2017 `rename` — atomicity guarantee and visibility rule. https://pubs.opengroup.org/onlinepubs/9699919799/functions/rename.html

**Dropped:**

- StackOverflow threads on npm `integrity` behavior — commentary; the npm docs cover it authoritatively.
- Vercel product docs page on Agent Skills — marketing/reference mirror of the spec; the spec itself is primary.
- agentskills quickstart and Microsoft Learn skills pages — tutorial mirrors of the spec.

---

## Gaps

- **Frontmatter merge semantics:** the spec constrains `name`/`description` and hosts like Eve strip unknown keys; whether a merged SKILL.md keeps valid frontmatter after `git merge-file` (line-based) is untested against real hosts. Suggested next step: small fixture matrix (conflicting `description`, metadata edits) run through `git merge-file --union` and validated with `skills-ref validate`.
- **Windows atomicity:** `rename()` over an existing directory is not atomic across all Windows filesystems in practice (POSIX guarantee ≠ NTFS behavior); vercel's junction handling and Ansible's `unsafe_writes` note both flag this. Next step: verify rename-over-directory behavior on Windows and document the fallback (copy-swap or per-file rename).
- **Overlay merge semantics for `scripts/`/`assets/`:** the sidecar-overlay recommendation is validated for prose; binary/executable overlay precedence and mode preservation (vercel chmods copies to source mode) need a defined rule.
- **Lock migration policy:** vercel wipes global locks on schema bump; whether Sigma should migrate project locks in place (npm's "npm will always attempt to get whatever data it can out of a lockfile") needs a decision once the schema settles.

## Supervisor coordination

None needed — research complete, no blocked decisions.
