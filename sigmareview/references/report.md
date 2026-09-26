# SigmaReview report and pull request

Create one file at the repository root: `SIGMAREVIEW-YYYY-MM-DD.md`. If that file already exists on the base branch, update it; do not add a second report. The report must still make sense after the conversation is gone. It is the verdict, the evidence, and the fix backlog in one.

## Report structure

Use this order. Leave out a section only when this contract allows it, and never leave an empty heading.

```markdown
# SigmaReview — <repository name>

> `<owner/repo>` at `<short SHA>` on `<YYYY-MM-DD>`. Authority: <A/B/custom, in words>. Runtime baseline: <established / not established>.

## Verdict

<Two to four paragraphs. What the system is, whether it keeps its promises, the dominant risks, and the recommended decision. Lead with the conclusion.>

| Decision | Result |
|---|---|
| Condition | <Strong / Mixed / Weak / Critical, with one reason> |
| Release posture | <Ship / Ship with conditions / Hold, with the gate> |
| Confirmed findings | <total: P0/P1/P2/P3; M1/M2> |
| Needs measurement | <M3 count> |
| Highest-leverage fix | <SIG-### and why> |
| Coverage limit | <plain words> |

## System and promises

<A compact map of components, primary journeys, and the promises tested against. Use a table when it clarifies ownership.>

## Fix plan

| Order | Findings | Action | Depends on | Done when | Status |
|---:|---|---|---|---|---|
| 1 | SIG-001 | <action> | — | <objective signal> | open |

<Status values: open, fix, defer, reject, fixed. Update them during the discussion and fix phase.>

## Findings

<Order P0 → P3, then by fix dependency. Use the finding template below for every confirmed (M1/M2) finding.>

## Needs measurement

<M3 items, capped at the five most valuable. Each item gives the mechanism, the location, and the exact measurement that would promote or kill it. Leave this section out if there are none.>

## Coverage

| Pass | Result | Findings | Limit |
|---:|---|---|---|
| 1 | Reviewed / Partial / N/A | <IDs or none> | <limit or none> |

<Then: what was deep-read, sampled, or excluded, with counts; what was run, with commands and results; and what could not be verified, with how it could change the verdict.>

## Strengths to keep

<Only strengths that should shape the fixes. Keep it brief.>

## Ideas for SigmaImprove

<Optional. At most three one-line pointers to strong improvement ideas noticed during the review that are not defects. Leave this section out if there are none.>
```

## Finding template

```markdown
### SIG-### — <specific causal title>

| Field | Value |
|---|---|
| Priority | P0 / P1 / P2 / P3 |
| Evidence | M1 Measured / M2 Proven |
| Confidence | <80–100%> |
| Category | Correctness / Data / Concurrency / Reliability / Security / Privacy / Performance / Architecture / Testing / Build / Dependency / Operations / Accessibility / Rendering / Domain |
| Effort | XS / S / M / L / XL |
| Location | `path:line`, plus related `path:line` |

**Broken promise:** <the goal, contract, budget, or invariant that fails>.

**What happens:** <mechanism and trigger, as a short causal chain from location to observable result>. <For M1: the command, the measurement, and the result.>

**Impact:** <who is hurt, how much, how often, and why this priority>.

**Fix:** <exact actions and locations; compatibility or migration notes; a small sketch only when it helps>.

**Proof test:** <setup, action, and assertion that fail before the fix and pass after>.

**Depends on:** <IDs or none>.
```

Rules:

- IDs run from `SIG-001` in report order. Priority is urgency; confidence is evidence strength. Do not mix them up.
- Effort: XS under 2 hours, S under a day, M 1–3 days, L up to 2 weeks, XL multi-stage.
- Cite current line numbers at the reviewed commit. Link external facts to primary sources next to the claim.
- No rejected candidates, generic best-practice lists, praise padding, decorative scores, or large code excerpts.
- Never print a full secret. Write `<redacted credential>`.

## Pull request

Branch `sigmareview/YYYY-MM-DD` from the reviewed commit. The first commit adds only the report: `docs: add SigmaReview (YYYY-MM-DD)`. If direct push fails and a fork is possible, use the fork. Do not change labels, reviewers, settings, or other files in this commit.

Title: `SigmaReview (YYYY-MM-DD): <n> findings`

Body:

```markdown
## SigmaReview

<Two or three sentences: condition, dominant risk, release posture.>

| Priority | Count |
|---|---:|
| P0 | <n> |
| P1 | <n> |
| P2 | <n> |
| P3 | <n> |

Top fixes:

1. **SIG-### — <title>:** <one sentence>.
2. **SIG-### — <title>:** <one sentence>.
3. **SIG-### — <title>:** <one sentence>.

Authority: <in words>. Coverage limit: <limit or none>.

Full evidence and the fix plan: [`SIGMAREVIEW-YYYY-MM-DD.md`](./SIGMAREVIEW-YYYY-MM-DD.md).
```

During the fix phase, each fix is its own commit, `fix(SIG-###): <what changed>`, with its proof test. Update the report's status column and the PR body counts as fixes land. If publication is impossible, keep the local branch and commit, and state the exact blocker and the smallest command that would publish it.
