# SigmaRefactor, a better installer, and reliable five-skill delivery

## Summary

Deliver three connected improvements in one feature branch and one PR:

1. Add SigmaRefactor (`sigmarefactor`) for safe, user-guided refactoring.
2. Fix installer repetition and exit behavior, with a compact interface based on the installer used by Matt.
3. Strengthen package tests so all five skills install correctly and updates preserve user content.

Use [issue #3](https://github.com/Djordje-Stojanovic/Sigmaskills/issues/3) as the single implementation ticket. Save this specification as `plan.md` and link it from the issue and PR. Work on `feature/sigmarefactor-installer`.

## Part 1 — Add SigmaRefactor

Create a small skill with `SKILL.md`, agent metadata, and one scan reference. Use existing customization markers and package conventions. Keep normal skill discovery enabled.

The skill follows five steps:

1. **Scan.** Resolve the target repository and inspect its instructions and working-tree changes. Run `laloc -p <root> -m 0` with quoted exclusions for prose and lockfiles when available. Check results against the repository file inventory: the tool skips directories such as `packages` and `bin`, which can contain real source. Count omitted eligible files before selecting the top five.
2. **Read.** Read all five files completely, using ordered chunks when necessary. Inspect callers, interfaces, and relevant tests. Use all available files if fewer than five qualify. Report unreadable files or incomplete reads.
3. **Discuss and agree.** Explain each file's purpose, responsibilities, duplication, and test coverage in plain English. Recommend simplification, removal of proven waste, extraction into modules, or leaving the file unchanged. Discuss until the user has selected the scope and accepted a concrete plan.
4. **Implement.** Establish the test baseline, then make agreed changes in small steps. Preserve behavior, public interfaces, data, and user changes. Add behavior tests where existing coverage cannot protect the change.
5. **Verify and deliver.** Run relevant tests and repository checks, inspect the diff, and repeat the line count. Follow the user's agreed workflow for commits, pushes, and PRs. Report verification limits accurately.

Counting rules: rank physical lines, including comments and blanks, by descending count and then path. Include maintained source, tests, scripts, and configuration. Exclude generated files, dependencies, binary files, prose, and lockfiles. Show exclusions. If `laloc` is unavailable, disclose that fact and use Git's file inventory with native line counting; do not install or load an entire machine profile automatically.

Quality rules: fewer lines are useful, not a quota. Do not compress formatting or weaken tests. Report lines removed separately from lines moved into new modules.

Use SigmaWrite when available, with a short plain-English fallback for standalone installation. Use SigmaBrief only when the user requests a brief or delegation. The skill must work without other authoring skills installed.

Treat Thinkcenter_Setup as the source for understanding `laloc` and as a read-only trial repository. This ticket does not change its toolkit or refactor its files.

## Part 2 — Fix and simplify the installer

[Matt's repository](https://github.com/mattpocock/skills) uses Vercel's `skills` CLI. Study its [searchable picker](https://github.com/vercel-labs/skills/blob/main/src/prompts/search-multiselect.ts) for compact rows, focused details, and terminal row accounting. Retain Sigma's installation engine and preservation rules.

- Replace the default animated reveal with a small Sigma heading and clear stage progress. Keep the warm palette. Record the revised visual decision in the existing ADR.
- Show five short skill rows. Show the focused description in a bounded detail area.
- Show a searchable destination list with at most eight visible items. Adjust it to actual terminal height, including wrapped text and footer rows.
- Keep `.agents/skills` as the only default destination. Detection labels hosts; it does not select them.
- Preserve selections during search, help, and resize. Keep the active row and navigation hints visible.
- Give static and plain terminals paged, line-based prompts. Print a page once and update it only after a meaningful command. Reduced motion disables animation without forcing repeated full-list output.
- Show a readable confirmation containing exact paths, methods, and existing overwrite or backup decisions. Finish with one result summary.

Fix input lifecycle cleanup: release listeners and timers, restore raw mode and cursor state, and pause input the installer resumed. Apply cleanup on success, cancellation, EOF, interruption, and errors. Verify the suspected exit defect with a reproduction before treating it as confirmed.

Preserve CLI flags, JSON contracts, global-install confirmations, link fallback, backups, adoption, and customization behavior.

## Part 3 — Make the shipped package prove it works

Extend existing tests rather than introduce a new framework.

- Register SigmaRefactor in the manifest, package files, expected skill registry, documentation, and changelog.
- Make tarball tests compare every declared skill's complete file tree with the installed package, including references, metadata, and helper files.
- Install all five skills from the packed artifact in temporary projects. Check status, repeated installation, update, and preservation of customization bytes.
- Add a child-process regression that leaves stdin open after confirmation and requires the executable to exit within a bounded timeout.
- Identify simulated terminal tests accurately. Add a real-terminal Windows smoke check for the reported failure.

Public additions are limited to the `sigmarefactor` skill ID, invocation examples, and revised interactive presentation. No new service, dependency manager, or release automation.

## Validation and delivery

Acceptance checklist:

- [ ] Scan cases cover omitted source directories, tied counts, fewer than five files, missing `laloc`, and unreadable files.
- [ ] Skill trials cover discussion-only use, approved execution, existing test failures, and a file that should remain unchanged.
- [ ] Installer cases cover search, selection, help, narrow and short terminals, resize, plain output, cancellation, success, and failure.
- [ ] Success prints once, returns to the shell, and installs only selected destinations.
- [ ] Package tests prove all five skills and supporting files ship.
- [ ] Run `npm test`, registry validation, skill validation, and the Windows/Linux/macOS CI matrix.

Implementation order: reproduce installer failures, fix interface and lifecycle, add SigmaRefactor, then complete package verification.

Preserve issue #3's original request and attach this full specification. Commit and push the feature branch, open one draft PR, complete implementation, self-review the full diff, fix findings, rerun affected checks, and mark ready when validation passes.

The user's follow-up authorizes merging the verified PR, closing resolved issues, deleting the feature branch, and synchronizing local `main` with GitHub. Do not publish an npm release.

The handoff must contain the PR link, completed work, test evidence, and exact local trial commands. Use this prompt:

> Use $sigmarefactor to inspect this repository's five largest source files. Explain your recommendations and wait for us to agree before editing.

Use clear technical English inspired by ASD-STE100; do not claim certified compliance.
