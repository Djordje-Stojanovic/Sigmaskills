# The grill: 8 questions

One numbered message, all 8 questions, each with a recommended answer the owner accepts with "yes". Word every question so "yes" takes the recommendation. Base each recommendation on what you saw in the source in step 1, not on a generic default, and give a few words of why. Facts you can look up are never questions: the source's size, its stack, its keys and its hardcoded paths are yours to find.

Format (the `/grilling` round format):

```
❓ **Q1** - **What you want**: <question, with the options>

➡️ <recommended answer, and why in a few words>

---
```

## Q1. What do you want from the copy?

Options: **run it as it is** (same job, own copy) · **adapt it** for a new purpose (name the purpose) · **learn it** (the copy is a sandbox) · **strip it into a template** for new projects · **contribute back** upstream.

Recommend from the owner's words and the source: a tool he uses daily → adapt; an unknown GitHub project → learn it; his own repo copied for an experiment → run it as it is in a sandbox.

## Q2. Why, and what does done look like?

The outcome in one sentence, and the first real thing the copy must do (one film rendered, one page deployed, one test green, one example running). This sets what the copy keeps and what the course stresses.

Recommend: the most valuable real example the study found, run end to end in the copy.

## Q3. Where are the resources?

- The source: GitHub `owner/repo` (and branch or tag) or a local path.
- What comes along and what stays: heavy or private folders to leave out (`--exclude`), data, assets and models to bring, sibling repos it needs.
- Outside folders the copy uses: output folders, caches, databases, shared config. For each: **remap into the copy** (the copy owns it) or **share** (read-only config such as a keys file).

Recommend: leave out installed dependencies, build output and the source's own past work (dated project folders, renders, logs) but keep templates and examples; remap every outside folder the copy writes to; share only read-only config.

## Q4. How deep is the research?

How many sources `/sigmaresearch` reads in full for the study: **0** (the source only) · **20** · **50** · **100** · another number.

Recommend: 100 for a public project the owner has not used; 20 for a well-known project with good docs; 0 for a copy of his own repo, whose docs are the source of truth.

## Q5. Which skill bundle goes into the copy?

A multi-select. Show every bundle from [bundles.md](bundles.md) with one line each:

- **The source's own skills** (for example only StorgeStudio skills): keep the skills the repo ships, drop the rest.
- **All Sigma** skills.
- **All Matt Pocock** skills.
- **All Three.js** skills.
- **HyperFrames + Sigma**.
- **None**: an empty skills folder.

Recommend: the source's own skills plus all Sigma for an agent-heavy repo; all Sigma alone for a plain code repo; add Three.js or HyperFrames when the stack uses them.

## Q6. Where does it go, and how?

- **How:** **fork** on the owner's GitHub account plus a local clone (to push and open pull requests upstream) · **clone** (a local copy, upstream kept as a read-only remote) · **copy** (a local folder, no link back) · **template** (a copy with a fresh git history).
- **Where:** an absolute path outside the source, on a disk with room for the copy and its dependencies. The folder must be new or empty.
- **Name:** the folder and, for a fork, the repo name.

Recommend: fork for a public repo he wants to change and share; clone for one he only adapts; copy for a local folder; template for a starter. Path: the source's own scratch or temp location if its docs name one (for example `D:\AI\Temp\<name>`), else a sibling folder `<source>-<name>`.

## Q7. Which access will you need?

List what the study found: logins (GitHub, npm, a cloud account), API keys and tokens, local services (a database, a GPU box), paid tools. For each: where it goes in the copy, and whether the owner types it now or later. He types every secret himself.

Recommend: point the copy at the keys file he already has (by path, values never copied); new keys only where the copy needs its own account.

## Q8. How do you learn best?

Options (pick any): **diagrams first** · **real worked examples** · **hands-on tasks** · **a short video-like walkthrough** (animated steps) · **a 3D map** (Three.js, for spatial or game repos) · **reference tables**. And the length: 10, 15 or 20 minutes.

Recommend: diagrams first, three real examples and three hands-on tasks, 15 minutes; a 3D map only when the repo itself is spatial (a game, a 3D tool, a scene graph).

## After the reply

Write every answer to `grill.md`, one line each: `Q<n>: <answer>`, and `Ruling: <answer>` for each you took on the owner's behalf. Branches that opened (a new key, a sibling repo, a second destination) get one short follow-up round; otherwise go straight to step 2.
