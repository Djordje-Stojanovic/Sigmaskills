# Own the Sigma installer and synchronize the host registry

SigmaSkills will own its install, update, backup, restore, and uninstall behavior rather than delegate writes to or fork the generic `skills` CLI. It will synchronize and test Agent Host definitions from `vercel-labs/skills`; this is the smallest design that can enforce SigmaSkills' data-preservation rules while continuing to support new hosts as the ecosystem and Skill Pack grow.

## Consequences

The synchronization process must preserve upstream attribution, detect registry drift, and never silently publish changed destination paths. The installer must discover skills from package metadata rather than hard-code the current four-skill count.
