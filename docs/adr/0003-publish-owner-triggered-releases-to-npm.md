# Publish owner-triggered Releases to npm

Ordinary merges to `main` will not publish SigmaSkills. When the owner explicitly requests a Release, the release agent will calculate and preview the version and complete contents, then—after one explicit confirmation—create the matching Git tag and GitHub Release and publish the same integrity-proven package to npm under the `latest` tag.

## Consequences

The repository version, npm version, Git tag, GitHub Release, bundled skills, and per-skill revision manifest must agree before publication. Routine releases require no manual file edits or local `npm publish`, but initial npm trusted-publisher configuration remains a one-time human setup.
