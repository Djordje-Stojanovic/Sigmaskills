# Maintainer guide

This guide is for people who change this repository. Users of the skills need only the [README](../README.md) and the [installer guide](installer.md). Agents working here must also follow [AGENTS.md](../AGENTS.md).

## Repository layout

```text
Sigmaskills/
├── AGENTS.md                 Agent working contract
├── CONTEXT.md                Project words (Skill Pack, Agent Host, …)
├── README.md · CHANGELOG.md · LICENSE · package.json · manifest.json
├── bin/ · src/               The user CLI (Sigma Installer)
├── scripts/                  Test runner, skill evals, release, and registry automation (not published)
├── registry/                 Agent Host registry and Release baselines
├── docs/                     Guides, decision records, audits
│   └── agents/               Issue tracker, triage, and domain notes for agents
├── test/                     npm test
├── .github/                  Issue forms · PR template · CI
├── .agents/skills/           Vendored dev skills for people who work here (not shipped)
├── skills-lock.json          Pins those dev skills; see below
├── sigmareview/              SKILL.md · agents/ · references/
├── sigmaimprove/             SKILL.md · agents/ · references/
├── sigmabrief/               SKILL.md · agents/ · references/
├── sigmaship/                SKILL.md · agents/ · references/
├── sigmawrite/               SKILL.md · agents/
└── sigmarefactor/            SKILL.md · agents/ · references/
```

Each top-level folder with a `SKILL.md` is one installable skill. The folder name, the frontmatter `name`, and the `--skill` id are the same.

### Dev skills and `skills-lock.json`

`.agents/skills/` holds 25 dev skills vendored from `mattpocock/skills`. They help maintainers and agents work in this repository. They are not part of the Skill Pack, and the npm package does not ship them.

`skills-lock.json` pins them. It also does a second job: `npx skills add Djordje-Stojanovic/Sigmaskills --all` (the `vercel-labs/skills` CLI) skips skills that the lock lists. Without the lock, that command would offer these 25 dev skills to users. Do not delete the lock or remove entries from it.

## Tests and CI

The tests use Node.js only, with no dependencies:

```bash
npm test
```

They cover the installer, the package contents, and the repository itself: the skill registry, `SKILL.md` frontmatter, `agents/openai.yaml`, README and installer-guide install lines, the README length, the CHANGELOG, issue templates, and agent docs.

`npm test` also checks each skill's output contract against good and bad sample outputs, and checks that near-miss prompts reach the right skill. To run the skills themselves on a small fixture game, use `node scripts/eval-skills.js [skill...]`. It calls Claude Code, costs money, and stays out of CI. The [skill evals guide](evals.md) has the method and the latest results.

CI runs the same suite on Windows, macOS, and Linux with Node.js 22 and 24. `package.json` requires Node.js 22 or newer (`engines.node`), so CI has no older job. It runs on every pull request and every push to `main`. The jobs use real junctions and symbolic links, copy fallback, different shells, and an isolated temporary file system. CI runs with a read-only token and pins every action to a full commit SHA. Dependabot opens one weekly pull request to bump the pinned actions (`.github/dependabot.yml`). The release, registry-sync, and rehearsal jobs run on Node.js 24.21.0. Its bundled npm (11.19) supports trusted publishing, so no job installs npm on its own. Keep the rehearsal on the same Node.js as `release.yml`.

### Adding, renaming, or removing a skill

Change these together in one pull request:

- `KNOWN_SKILLS` in [`test/repo-invariants.test.js`](../test/repo-invariants.test.js);
- `manifest.json` and the `files` list in `package.json`;
- the README skills table and run examples;
- the per-skill install lines in [installer.md](installer.md#other-install-methods);
- the CHANGELOG.

If one is missing, CI fails on purpose.

### Registry scripts

- `npm run registry:sync` rebuilds `registry/agent-hosts.json` from the pinned `vercel-labs/skills` revision. Flags: `--fetch` (download the pinned revision), `--dry-run`, `--allow-review` (write even when the diff needs owner review).
- `npm run registry:validate` checks the snapshot against `registry/schema.json` and the safety rules. `npm test` runs the same checks.

## Releases

Releases run from a repository checkout, never from the published package. The npm package ships only the user CLI. Release and registry automation live in `scripts/`.

1. `npm run release -- --dry-run` previews the next Release.
2. `npm run release -- --write-identities` writes the version identities. Commit them and merge.
3. `npm run release -- --expected-commit <sha> --expected-version <version> --expected-digest <sha256>` dispatches `release.yml`.

CI rehearses these steps on every pull request, together with the trusted `validate` and publish steps (`node scripts/release-rehearsal.js`). The rehearsal uses a real `npm pack` and stubs the network, dispatch, and publish.

### Preview

`--dry-run` calculates the next semantic version and the full change set from the accepted source commit. It prints one publication preview:

- the commit and the version;
- the required tests;
- the tarball contents and its SHA-256 digest;
- each Skill Revision;
- the git tag, the GitHub Release, the npm package, and the `latest` dist-tag.

Before 1.0.0, a breaking change raises the minor version, as SemVer allows for 0.y.z versions.

### Identities

`--write-identities` writes matching identities to `package.json`, `manifest.json`, and `CHANGELOG.md`, and adds the outgoing Release's skill hashes (read from its local `v<version>` tag) to `registry/skill-baselines.json`. The owner then commits these files. The baselines let the installer recognize untouched copies of that Release later.

### Dispatch and publish

Ordinary merges never publish. `--yes`, CI, and informal text cannot dispatch a Release. Dispatch needs `--expected-commit`, `--expected-version`, and `--expected-digest`, and all three must match the rebuilt preview.

The trusted `release.yml` workflow then checks everything again on its own:

- It checks out the approved commit, runs the tests again, and rebuilds the tarball.
- It verifies the commit, version, and digest before the publish job.
- Validation runs with `contents: read` only.
- Only the final job gets `id-token: write`, `contents: write`, and the protected `release` environment.
- Every action is pinned by commit SHA.
- Every job has a 30-minute timeout.

Publishing fails closed, with setup guidance, when the npm name is not reserved, the trusted publisher or environment protection is missing, or a version, tag, or GitHub Release conflicts. A matching npm provenance or an existing GitHub Release at the same commit is skipped. It is never overwritten or duplicated.

## Agent Host registry automation

The `registry-sync.yml` workflow keeps `registry/agent-hosts.json` in step with the pinned `vercel-labs/skills` revision.

### What it may change

- It fetches one pinned `vercel-labs/skills` revision as data.
- It runs converter code only from the exact default-branch SHA in `EXPECTED_HEAD`.
- Generated changes are limited to `registry/agent-hosts.json`, `registry/source.json`, and `test/fixtures/vercel-skills/src/agents.ts`.
- New hosts must pass safe-root, traversal, collision, overlap, control-character, and platform checks.
- It cannot change skills, CLI behavior, unrelated issues or pull requests, human branches, or major or minor Releases. It never overwrites an existing npm version.

### When it may merge and publish

A generated pull request auto-merges only when all of these hold:

- it comes from the trusted workflow;
- its diff exactly matches the allowlist;
- its head SHA is the validated one;
- `main` is current and protected;
- all required checks pass.

Validated host additions and description-only edits can then publish a patch Release. They use the same idempotent, trusted publication step as owner Releases. Changes to a path, ID, alias, detection rule, platform, membership, removal, unknown field, or any failed validation stay blocked for owner review.

`main` is not protected today, so auto-merge never runs. The owner reviews and merges every registry sync pull request by hand, like any other pull request. Turn auto-merge on only after `main` has branch protection with required checks.

### Versions and branches

Version calculation serializes concurrent runs. It reconciles npm and GitHub before the patch. The generated branch is deleted only after a verified merge and matching npm and GitHub results.

If a generated branch is left over from an earlier run, the workflow replaces it. If a matching generated pull request is already open, the workflow reuses it instead of failing the push.

### Setup

Configure an npm trusted publisher for `registry-sync.yml` in addition to `release.yml`.
