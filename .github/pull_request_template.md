## What changed?

One or two sentences. Pretend you forgot this is an Agent Skills repo (skills, prompts, contracts, install docs, and the Sigma Installer CLI).

## How do you know it works?

Checks you ran (or will run). Tick when done.

- [ ] Skill / docs still match the stated output contract (or docs-only change is accurate)
- [ ] Install or invoke path still makes sense (`npx skills add`, Codex, or manual copy) if that surface moved
- [ ] `npm test` passes (installer, package, and skill structure)
- [ ] CHANGELOG `[Unreleased]` has an entry, if users or maintainers would notice the change

## Before you merge

- [ ] You actually checked it — not "probably fine"
- [ ] No secrets, tokens, or passwords in this diff
- [ ] Change stays in the skill, prompt, template, or installer CLI lane (no unrelated product app)
