# SigmaReview report and pull-request contract

Create one file at the repository root named `SIGMAREVIEW-FINDINGS-YYYY-MM-DD.md`. Replace the date with the review date. If the exact file already exists on the base branch, update that file for the new review rather than creating auxiliary reports.

The report is simultaneously an executive audit, a technical diagnosis, and an implementation backlog. It must remain useful after the reviewing conversation disappears.

## Contents

1. Report structure
2. Detailed finding template
3. Writing and presentation rules
4. Pull-request contract

## Report structure

Use this exact top-level order. Omit a subsection only when the contract explicitly permits it; never leave empty placeholders.

```markdown
# SigmaReview — <repository name>

> Full-repository engineering audit of `<owner/repo>` at `<short SHA>` on `<YYYY-MM-DD>`.
> Review mode: source-led, single-agent, one-shot. No project code or dependency installation executed.

## Executive verdict

<Two to five dense paragraphs: what the system is, whether it is sound, the dominant risks, and the recommended decision. Lead with the conclusion. Distinguish confirmed defects from modernization opportunities.>

### Decision summary

| Decision | Result |
|---|---|
| Overall engineering condition | <Excellent / Strong / Mixed / Weak / Critical, justified> |
| Release/deployment posture | <Ship / Ship with conditions / Hold, with one-line gate> |
| Confirmed findings | <total: P0/P1/P2/P3 counts> |
| Highest-risk area | <area and why> |
| Highest-leverage fix | <finding ID and why> |
| Review coverage | <plain-English scope and material boundary> |

## System at a glance

<Compact architecture and product model. Include a component/data-flow table when it clarifies ownership or boundaries.>

## Priority action plan

| Order | Finding(s) | Action | Why first | Depends on | Completion signal |
|---:|---|---|---|---|---|
| 1 | <IDs> | <action> | <risk/leverage> | <IDs or None> | <objective pass condition> |

<Order the work as a realistic remediation program. Combine findings only when they share an implementation step.>

## Findings index

| ID | Priority | Confidence | Category | Title | Primary location | Effort |
|---|---|---:|---|---|---|---|
| SIG-001 | P1 | 96% | Correctness | <specific failure> | `path:line` | M |

## Detailed findings

<Order P0 → P3, then by remediation dependency and category. Use the finding template below exactly.>

## Engineering upgrade matrix

<Include only verified upgrades, architectural improvements, or modernization work that is not already a defect. Omit this section if none survive the evidence gate.>

| ID | Type | Current state | Recommended state | Evidence/rationale | Compatibility and migration | Priority |
|---|---|---|---|---|---|---|
| UPG-001 | Dependency / Platform / Architecture / DX | <current> | <target> | <primary-source or repository evidence> | <breaking risk and sequence> | P2 |

## Verification strategy

<Turn the accepted findings into the smallest effective test and validation program. Include regression tests, integration/contract tests, static checks, and operational checks. Tie each item to finding IDs. Do not restate generic testing doctrine.>

## Coverage ledger

### Repository accounting

| Area | Paths/files | Review depth | Status | Notes |
|---|---|---|---|---|
| Runtime source | <paths/count> | Deep semantic | Reviewed | <notes> |

### Ten-pass ledger

| Pass | Discipline | Result | Findings | Material limitation |
|---:|---|---|---|---|
| 1 | System map, intent, coverage | Reviewed / N/A / Partial | <IDs or None> | <specific limitation or None> |

### Excluded or non-semantic material

<List generated, vendored, minified, binary, lock, fixture, and asset areas with counts and the exact treatment. Omit only if truly none exist.>

## Unverified boundaries

<State facts the source-led, non-executing review could not establish: runtime-only behavior, unavailable private dependencies, production configuration, inaccessible CI artifacts, huge generated surfaces, or context limits. Explain how each boundary could change the verdict and the smallest validation needed. If none are material, say `No material unverified boundary changed the verdict.`>

## Validated strengths

<Only strengths that reduce risk, constrain remediation, or deserve preservation. Keep this brief and evidence-based.>

## Final assessment

<One decisive closing paragraph: the actual condition, what must happen next, and what success looks like. Do not add an invitation or generic sign-off.>
```

## Detailed finding template

Use this structure for every `SIG-*` finding:

```markdown
### SIG-### — <Specific causal title>

| Field | Value |
|---|---|
| Priority | **P0/P1/P2/P3** |
| Category | Correctness / Architecture / Data / Concurrency / Reliability / Security / Privacy / Performance / Testing / Dependency / Build / CI-CD / Operations / UX / Accessibility / Hardware / AI-ML / Documentation |
| Confidence | <80–100%> |
| Effort | XS / S / M / L / XL |
| Fix risk | Low / Medium / High |
| Primary location | `path/to/file.ext:line-line` |
| Related locations | `path:line`, `path:line` or None |

**What is wrong**

<State the defect precisely. No throat-clearing and no hypothetical language inconsistent with the confidence.>

**Evidence and execution path**

1. `<path:line>` — <what the code establishes>.
2. `<path:line>` — <how control/data/state proceeds>.
3. <trigger/input/deployment condition> → <incorrect behavior> → <observable result>.

<Include a short excerpt only if locations and explanation are insufficient. Redact sensitive values.>

**Impact**

<Who or what is affected, severity, blast radius, frequency/preconditions, and why the assigned priority is justified.>

**Root cause**

<The violated invariant, contract mismatch, missing boundary, or design error. Distinguish root cause from symptoms.>

**Remediation**

1. <Exact implementation action and location.>
2. <Required contract/schema/migration/error-handling change.>
3. <Compatibility, rollout, cleanup, or documentation action.>

When useful, include a small pseudocode or interface sketch. Do not fabricate a full patch.

**Verification**

- Regression test: <setup, action, assertion that fails before and passes after>.
- Broader check: <integration, property, fuzz, load, static, formal, migration, or operational validation>.
- Acceptance criteria: <objective completed state>.

**Dependencies and interactions**

<Prerequisite finding IDs, conflicts, coupled fixes, or `None`.>
```

## Writing and presentation rules

- Use IDs continuously from `SIG-001`, ordered by final report priority. Use `UPG-001` for non-defect upgrades.
- Use priority to express impact and urgency; use confidence to express evidence strength. Do not conflate them.
- Use effort as relative implementation size: XS (<2 hours), S (<1 day), M (1–3 days), L (up to 2 weeks), XL (multi-stage/architectural). Treat these as rough engineering sizes, not promises.
- Cite repository locations with paths and current reviewed line numbers. For cross-file findings, show the entire causal chain.
- Link current external facts near the claim using official sources. Do not add a bibliography detached from claims.
- Do not include rejected candidates, generic best-practice lists, praise padding, or recommendations unsupported by the repository.
- Avoid giant source excerpts. The report explains code; it does not mirror it.
- Keep the report visually calm: consistent headings, compact tables, precise prose, no decorative emoji, fake badges, ASCII borders, or arbitrary numeric grades.
- Never expose a full secret. Use forms such as `sk-…9f2c`, `AKIA…Q7PX`, or preferably `<redacted credential>` when even a fingerprint is unnecessary.
- Ensure the report works as a backlog: each finding must be independently assignable while preserving dependencies and remediation order.

## Pull-request contract

Use this title:

```text
docs: add SigmaReview full-repository audit (YYYY-MM-DD)
```

Use this body, populated from the final report:

```markdown
## SigmaReview

This pull request adds a source-led, full-repository engineering audit at `<short SHA>`. It changes no runtime code.

### Verdict

<Two or three precise sentences containing the overall condition, dominant risk, and release posture.>

### Findings

| Priority | Count |
|---|---:|
| P0 | <n> |
| P1 | <n> |
| P2 | <n> |
| P3 | <n> |

Highest-leverage actions:

1. **SIG-### — <title>:** <one-sentence action and consequence>.
2. **SIG-### — <title>:** <one-sentence action and consequence>.
3. **SIG-### — <title>:** <one-sentence action and consequence>.

### Scope

- Reviewed: <compact first-party scope>.
- Method: ten-pass correctness, architecture, data/concurrency, reliability, security, performance, verification, delivery, and domain audit.
- Runtime execution: none; no project dependencies were installed and no project code was executed.
- Material limitation: <limitation or `None that changed the verdict`>.

The complete evidence, remediation specifications, verification plan, and coverage ledger are in [`SIGMAREVIEW-FINDINGS-YYYY-MM-DD.md`](./SIGMAREVIEW-FINDINGS-YYYY-MM-DD.md).
```

If fewer than three accepted findings exist, list only those that exist. If there are zero accepted findings, replace `Highest-leverage actions` with one sentence stating that no candidate survived the evidence gate and name the highest-value verification gap, if any.
