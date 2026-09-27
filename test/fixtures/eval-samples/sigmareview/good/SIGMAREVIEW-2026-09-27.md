# SigmaReview — snake-lite

> `local/snake-lite` at `abc1234` on `2026-09-27`. Authority: B, ran the tests. Runtime baseline: established.

## Verdict

The game mostly works, but the snake survives past two walls.

| Decision | Result |
|---|---|
| Condition | Mixed, one broken rule |
| Release posture | Ship with conditions: fix SIG-001 |
| Confirmed findings | 1: 0/0/1/0; M1 1 |
| Needs measurement | 0 |
| Highest-leverage fix | SIG-001, it breaks the main rule |
| Coverage limit | none |

## System and promises

One logic module and one terminal loop.

## Fix plan

| Wave | Findings | Action | Depends on | Done when |
|---:|---|---|---|---|
| 1 | SIG-001 | Use `>=` | — | wall test passes |

## Findings index

| ID | Priority | Evidence | Category | Title | Location | Effort |
|---|---|---|---|---|---|---|
| SIG-001 | P2 | M1 | Correctness | Snake survives past the wall | `src/logic.js:21` | XS |

## Findings

### SIG-001 — Snake survives one cell past the right wall

| Field | Value |
|---|---|
| Priority | P2 |
| Evidence | M1 Measured |
| Confidence | 95% |
| Category | Correctness |
| Effort | XS |
| Location | `src/logic.js:21` |

**Broken promise:** the README says the snake dies when it leaves the board.

**What happens:** `step` compares with `>`, so x = 10 is allowed.

**Impact:** every player.

**Fix:** compare with `>=`.

**Proof test:** move to x = 10 and assert `over`.

**Depends on:** none.

**Done when:** the proof test and `npm test` pass.

## Coverage

| Pass | Result | Findings | Limit |
|---:|---|---|---|
| 1 | Reviewed | SIG-001 | none |
