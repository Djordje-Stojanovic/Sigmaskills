# Automate only safe Agent Host registry Releases

SigmaSkills will synchronize Agent Host definitions from `vercel-labs/skills`. Additions and description-only changes may pass strict validation, merge automatically, publish a patch Release to npm, and clean up their generated branch; changes to existing destination paths and host removals require owner review because they can redirect or remove user files.

## Consequences

This is the only exception to owner-triggered Releases. Automation has no authority over skills, CLI behavior, unrelated pull requests or issues, existing feature branches, major or minor Releases, or failed and ambiguous registry changes.
