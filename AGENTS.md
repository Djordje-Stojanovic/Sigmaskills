# AGENTS.md

You work in **Sigmaskills**, a portable [Agent Skills](https://agentskills.io/) monorepo. Each top-level folder with a `SKILL.md` is one installable skill (`sigmareview`, `sigmaperformance`, `sigmabrief`, `sigmawrite`). There is no app runtime here — only skill markdown, contracts, docs, and structural tests.

**Where to look**

| Path | What |
|------|------|
| [`README.md`](README.md) | Install, run, output contracts for every host |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history (`[Unreleased]` for WIP) |
| `sigmareview/` · `sigmaperformance/` · `sigmabrief/` · `sigmawrite/` | The skills |
| [`test/repo-invariants.test.js`](test/repo-invariants.test.js) | `KNOWN_SKILLS` registry + `npm test` guards |
| `.github/` | Issue forms, PR template, CI |

When you add a skill (or rename/remove one): update `KNOWN_SKILLS` in [`test/repo-invariants.test.js`](test/repo-invariants.test.js) together with README + CHANGELOG, or CI fails on purpose. Folder name = frontmatter `name` = `--skill` id. Then run `npm test`.

Follow every rule below. They are mandatory for this repo.

---

## How you work

Bias toward caution over speed. For trivial tasks, use judgment.

### Think before coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### Simplicity first

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### Surgical changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### Goal-driven execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

You are doing this right when: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## How you write

Write user-facing English in the spirit of ASD-STE100 Simplified Technical English: clear shared meaning, living voice, still precise. Not certified STE; no controlled dictionary.

Use this voice for explanations, summaries, plans, and answers in this repo. Leave code, paths, APIs, identifiers, and other skills’ required formats alone.

Write amazing high-quality technical English that never gets too long. A sharp person from a completely unrelated field — even without your jargon — should still grasp your meaning. Stay technical when the topic is. Be fun to read without baby-talk or buzzword cosplay.

Prefer clear who-does-what over foggy abstractions. Prefer one clean idea per sentence when something is hard. Prefer stable names for the same concept; don’t synonym-hop for style. Prefer simple words; when a real technical term is needed, keep it and make its meaning obvious once. Prefer light noun stacks over packed noun piles. Prefer simple time (now / then / next). Prefer enough detail to act or understand; cut empty filler. Prefer steps a human can follow without sounding like a robot manual.

**Never:**
- Invent nonsense words or fake-technical coinages.
- Hide meaning in abstract gibberish.
- Talk down to the reader.
- Rename real code, paths, APIs, or identifiers to “sound simpler.”

**Bad:** We refactored the orchestration layer to idempotently hydrate the ephemeral projection surface across seven modules.

**Good:** I changed how temporary data loads across seven files. The load can run twice without creating duplicate records. Here is what each file does and why.

Soft steers only — do not paste hard numbered writing laws into skills or docs. Canonical package if you need the pasteable system-prompt block: [`sigmawrite/SKILL.md`](sigmawrite/SKILL.md).
