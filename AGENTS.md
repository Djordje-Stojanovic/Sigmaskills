# AGENTS.md

Instructions for coding agents working in **Sigmaskills**. Keep this file short. Prefer clarity over ceremony.

This repo ships portable [Agent Skills](https://agentskills.io/) — markdown skill packages, not an application runtime.

---

## How to work here (Karpathy-shaped)

Bias toward caution over speed. For trivial edits, use judgment.

**Think before coding.** State assumptions. If several readings exist, say so — do not pick silently. If something is unclear, stop and ask.

**Simplicity first.** Minimum change that solves the ask. Nothing speculative. No abstractions for one-use code. No “flexibility” that nobody requested. If you wrote 200 lines and 50 would do, rewrite.

**Surgical changes.** Touch only what you must. Do not “improve” adjacent files, comments, or formatting. Match existing style. Every changed line should trace to the user request.

**Goal-driven.** Define success checks, then loop until they pass. For multi-step work:

```text
1. [Step] → verify: [check]
2. [Step] → verify: [check]
```

Run `npm test` before you claim done when you touched skills, docs, tests, or templates.

---

## Writing voice (SigmaWrite)

Write user-facing English in the spirit of ASD-STE100 Simplified Technical English: clear shared meaning, living voice, still precise. Not certified STE; no controlled dictionary.

Write amazing high-quality technical English that never gets too long. A sharp person from a completely unrelated field — even without your jargon — should still grasp your meaning. Stay technical when the topic is. Be fun to read without baby-talk or buzzword cosplay.

Prefer clear who-does-what over foggy abstractions. Prefer one clean idea per sentence when something is hard. Prefer stable names for the same concept; don’t synonym-hop for style. Prefer simple words; when a real technical term is needed, keep it and make its meaning obvious once. Prefer light noun stacks over packed noun piles. Prefer simple time (now / then / next). Prefer enough detail to act or understand; cut empty filler.

**Never:** invent nonsense words or fake-technical coinages; hide meaning in abstract gibberish; talk down to the reader; rename real code, paths, APIs, or identifiers to “sound simpler.”

Do not paste hard numbered writing laws into skills or docs (no fixed word-count ceilings). Soft steers only. Full skill: [`sigmawrite/SKILL.md`](sigmawrite/SKILL.md).

---

## Adding, renaming, or removing a skill

Folder name = frontmatter `name` = `--skill` id = invocation token (`$id` / `/skill:id`).

In the **same change**, update all of:

1. The skill folder (`SKILL.md`, and usually `agents/openai.yaml`; `references/` when the skill needs them)
2. [`README.md`](README.md) — Available / Install / Run / Output contracts
3. [`CHANGELOG.md`](CHANGELOG.md) — under `[Unreleased]`
4. **`KNOWN_SKILLS` in [`test/repo-invariants.test.js`](test/repo-invariants.test.js)**

If you skip the test registry, **CI fails on purpose**. That is intentional.

Then run:

```bash
npm test
```

---

## Repo map

| Path | Role |
|------|------|
| `sigmareview/` · `sigmaperformance/` · `sigmabrief/` · `sigmawrite/` | Installable skills |
| `test/repo-invariants.test.js` | Structural guards (`KNOWN_SKILLS`) |
| `.github/` | Issue forms, PR template, CI |
| `CHANGELOG.md` | Release history |
| `AGENTS.md` | Working contract for coding agents in this repo |

Do not inject host system prompts into other products from this repo. Skills stay portable packages. Users may copy SigmaWrite’s paste block into their own host instructions.

---

**These guidelines are working if:** diffs stay small, `npm test` stays green, new skills appear in README + CHANGELOG + `KNOWN_SKILLS` together, and explanations stay clear without jargon soup.
