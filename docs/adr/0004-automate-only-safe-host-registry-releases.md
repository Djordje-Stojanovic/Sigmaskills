# Automate only safe Agent Host registry Releases

SigmaSkills will synchronize Agent Host definitions from `vercel-labs/skills`. Additions and description-only changes may pass strict validation, merge automatically, publish a patch Release to npm, and clean up their generated branch; changes to existing destination paths and host removals require owner review because they can redirect or remove user files.

## Status

Accepted, with auto-merge not in use (2026-09-29). `main` is not protected, so the automatic merge never runs. The owner reviews and merges registry sync pull requests by hand. The rules below stay in force if the owner turns on branch protection with required checks later.

Updated 2026-09-30: the daily schedule is removed. The sync now runs on demand as the first step of each Release, so no registry pull request waits between Releases.

## Consequences

This is the only exception to owner-triggered Releases. Automation has no authority over skills, CLI behavior, unrelated pull requests or issues, existing feature branches, major or minor Releases, or failed and ambiguous registry changes.
