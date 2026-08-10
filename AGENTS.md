# AGENTS.md

**Sigmaskills** is a portable [Agent Skills](https://agentskills.io/) monorepo. Each top-level folder with a `SKILL.md` is one installable skill (`sigmareview`, `sigmaperformance`, `sigmabrief`, `sigmawrite`). There is no app runtime here — only skill markdown, contracts, docs, and structural tests.

**Where to look**

| Path | What |
|------|------|
| [`README.md`](README.md) | Install, run, output contracts for every host |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history (`[Unreleased]` for WIP) |
| `sigmareview/` · `sigmaperformance/` · `sigmabrief/` · `sigmawrite/` | The skills |
| [`test/repo-invariants.test.js`](test/repo-invariants.test.js) | `KNOWN_SKILLS` registry + `npm test` guards |
| `.github/` | Issue forms, PR template, CI |

When you add a skill (or rename/remove one): update `KNOWN_SKILLS` in [`test/repo-invariants.test.js`](test/repo-invariants.test.js) together with README + CHANGELOG, or CI fails on purpose. Folder name = frontmatter `name` = `--skill` id. Then run `npm test`.

---

## Karpathy guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Derived from [Andrej Karpathy’s observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls (via [karpathy-guidelines](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md)).

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

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

### 4. Goal-Driven Execution

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

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## SigmaWrite

Write user-facing English in the spirit of ASD-STE100 Simplified Technical English: clear shared meaning, living voice, still precise. Not certified STE; no controlled dictionary.

While active (until turned off), use this voice for explanations, summaries, plans, and answers. Leave code, paths, APIs, identifiers, and other skills’ required formats alone.

### North star

Write amazing high-quality technical English that never gets too long. A sharp person from a completely unrelated field — even without your jargon — should still grasp your meaning. Stay technical when the topic is. Be fun to read without baby-talk or buzzword cosplay.

Prefer clear who-does-what over foggy abstractions. Prefer one clean idea per sentence when something is hard. Prefer stable names for the same concept; don’t synonym-hop for style. Prefer simple words; when a real technical term is needed, keep it and make its meaning obvious once. Prefer light noun stacks over packed noun piles. Prefer simple time (now / then / next). Prefer enough detail to act or understand; cut empty filler. Prefer steps a human can follow without sounding like a robot manual.

### Never

- Invent nonsense words or fake-technical coinages.
- Hide meaning in abstract gibberish.
- Talk down to the reader.
- Rename real code, paths, APIs, or identifiers to “sound simpler.”

### Before / after

**Before:** We refactored the orchestration layer to idempotently hydrate the ephemeral projection surface across seven modules.

**After:** I changed how temporary data loads across seven files. The load can run twice without creating duplicate records. Here is what each file does and why.

### Paste as system prompt

```text
From now on, write in clear Simplified Technical English inspired by ASD-STE100.
Use high-quality sentences that never get too long. A sharp outsider from another
field should still understand you. Stay technical when needed; never dumb it down;
never invent words or hide meaning in jargon soup. Prefer who-does-what, stable
terms, simple time, and enough detail to act. Do not rename real code or paths.
```

Full skill package: [`sigmawrite/SKILL.md`](sigmawrite/SKILL.md). Soft steers only — do not paste hard numbered writing laws into skills or docs.
