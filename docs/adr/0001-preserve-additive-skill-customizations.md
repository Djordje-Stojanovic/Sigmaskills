# Preserve additive customizations in a reserved skill block

SigmaSkills will ship a `## Personal instructions` section containing one `<sigmaskills-custom>...</sigmaskills-custom>` block at the end of every `SKILL.md` and preserve the block contents byte-for-byte during updates. This keeps personal instructions visible and editable in the installed skill while preventing users from replacing or deleting official instructions; we rejected unrestricted three-way editing and a separate sidecar as less predictable or less discoverable for this product.

## Consequences

The installer must reject missing, duplicated, reversed, or malformed markers instead of guessing. Every skill and every update path must test empty, populated, and malformed blocks rigorously.
