# SigmaRefactor, installer stability, and five-skill delivery

This plan implements issue [#3](https://github.com/Djordje-Stojanovic/Sigmaskills/issues/3) in three connected parts.

## 1. SigmaRefactor

Add the `sigmarefactor` skill with `SKILL.md`, `agents/openai.yaml`, and `references/scan.md`.

The skill has five user-visible stages:

1. Resolve the target repository, read its instructions, record existing changes, run `laloc` when available, and reconcile its output with a complete maintained-file inventory.
2. Read the five largest eligible files from start to end, then inspect callers, interfaces, and relevant tests.
3. Explain each file and propose removal, simplification, extraction, splitting, tests, or no change. Wait until the user agrees to a concrete scope.
4. Establish a test baseline and implement the agreed behavior-preserving changes in small steps.
5. Run focused and full checks, repeat the scan, inspect the diff, and report removed lines separately from moved lines.

The scan ranks physical lines by descending count and then normalized path. It excludes generated output, dependencies, binaries, prose, and lockfiles. It reports files omitted by `laloc` because of skipped directories such as `bin` and `packages`, missing commands, and unreadable files. It never installs or sources a complete Thinkcenter_Setup profile. Thinkcenter_Setup is read-only reference material.

The skill uses SigmaWrite's clear style when present and remains usable without SigmaWrite or SigmaBrief. It never edits during the discussion stage and never reduces code by weakening tests or compressing formatting.

## 2. Installer stability and presentation

Keep Sigma's existing install, adoption, backup, customization, link, global-scope, JSON, and CLI contracts.

- Keep the warm Emberforge palette, but use a compact reveal with a clear stage label.
- Render short skill rows and a bounded two-line detail area for the focused skill.
- Window destination rows to terminal height and account for wrapped rows and footer space.
- Keep `.agents/skills` selected by default. Detection marks hosts and never selects them.
- Keep search, help, selection, resize, and keyboard-only controls stable.
- In static and plain output, suppress unchanged redraws so an ignored key does not print the same page again.
- Release listeners and timers, restore raw mode and cursor state, and pause input resumed by the installer on success, cancellation, EOF, interruption, and errors.

The regression test keeps child stdin open after confirmation and requires the interactive process to exit within two seconds. Existing simulated terminal tests continue to cover layout and keyboard behavior. The revised visual choice is recorded in the Emberforge ADR.

## 3. Package proof

Register `sigmarefactor` in the manifest, package allowlist, repository invariants, README, and changelog. The tarball test derives the expected file tree from every manifest skill, checks every declared file is packed, installs all five skills from the artifact, and verifies the installed command and universal destination behavior. Existing update tests continue to prove customization bytes survive updates.

## Acceptance checks

- `npm test` passes, including skill validation, registry validation, installer tests, tarball tests, and the open-stdin exit regression.
- The interactive installer prints one unchanged static page, exits after a confirmed child-process install, and leaves unselected host directories untouched.
- The package catalog reports five skills and the tarball contains every file under each declared skill directory.
- SigmaRefactor covers `laloc` available and unavailable cases, skipped source directories, tied counts, fewer than five files, unreadable files, discussion-only runs, approved runs, pre-existing test failures, and files that should remain unchanged.
- No change touches Thinkcenter_Setup, adds a runtime dependency, publishes an npm release, or merges the pull request.
