# SigmaPerformance report contract

## Contents

1. Report structure
2. Item contract
3. PR contract
4. Completion gate

## 1. Report structure

Create `SIGMAPERFORMANCE-REPORT-YYYY-MM-DD.md` with:

1. **Title and audit metadata:** repository/SHA/date; execution/stress/evidence/topology; runtime baseline status.
2. **Executive verdict:** actual condition, dominant constraint, primary journey, budget posture, and material coverage boundary.
3. **Decision summary:** M1/M2 counts by P0–P3; M3 count; unsuccessful experiments; highest-leverage action.
4. **Calibrated workload and environment contract.**
5. **System and end-to-end journey map.**
6. **Baseline and measurement methodology:** commands/tools/versions/hardware/OS/power/runtime/workload/concurrency/cache/warm-up/trials/distributions/uncertainty/failures/interference.
7. **Bottleneck map and priority action plan.**
8. **Confirmed findings index** containing only M1/M2.
9. **Detailed confirmed findings.**
10. **Measurement-required opportunities** containing capped M3 items separately.
11. **Measured experiments that did not improve performance**, only when qualified.
12. **Ordered SigmaOptimize handoff** in four waves.
13. **Verification and regression program.**
14. **Coverage ledger:** repository accounting, ten lenses, measurements, sampled/excluded/unverified areas, continuation map for huge repos.
15. **Unverified runtime boundaries and execution failures.**
16. **Performance-positive engineering strengths worth preserving.**
17. **Final assessment.**

Use restrained, excellent Markdown. Use tables for indexes/mappings and prose for causality. No decorative scoring, vague claims, megabyte dumps, unsupported percentiles, or generic advice.

## 2. Item contract

Every item uses a stable ID: `PERF-###` for M1/M2 and `OPP-###` for M3.

Include:

- title, evidence class, P0–P3 priority for confirmed items or opportunity urgency for M3, confidence, category, effort, fix risk, exact locations;
- affected workflow, operating range, workload, current behavior/baseline;
- mechanism with source execution path;
- runtime evidence and compact raw samples when useful;
- impact and priority rationale;
- semantic-equivalence invariants;
- optimization direction without pretending it is already successful;
- expected benefit: measured bottleneck magnitude / mechanically inferred / unknown;
- primary metric and secondary regression budgets;
- exact reproduction command or compact embedded harness;
- implementation constraints and dependencies;
- validation, acceptance/promotion gate, and rollback condition.

M1 must be reproducible. M2 contains no fabricated runtime magnitude. M3 names the measurement required for promotion and is not counted as confirmed.

For each unsuccessful experiment record candidate, rationale, valid measurement, result, rejection, and precise reconsideration condition.

## 3. PR contract

Body:

```markdown
## SigmaPerformance

Source/runtime performance audit of `<repo>` at `<SHA>`. Runtime source is unchanged.

### Verdict
<condition, dominant constraint, release/performance posture>

| Evidence | Count |
|---|---:|
| M1 measured findings | n |
| M2 mechanically proven findings | n |
| M3 measurement-required opportunities | n |
| Measured unsuccessful experiments | n |

Top priorities:
1. **PERF-### — title:** action and consequence.

- Execution mode: <mode>
- Runtime baseline: <established/not established>
- Agent topology: <single / primary-owned bounded>
- Measurement coverage: <scope>
- Material boundary: <boundary>

Complete evidence, optimization contracts, coverage and handoff: [`SIGMAPERFORMANCE-REPORT-YYYY-MM-DD.md`](./SIGMAPERFORMANCE-REPORT-YYYY-MM-DD.md).
```

If no confirmed findings exist, say so and name the highest-value missing measurement rather than inventing priorities.

## 4. Completion gate

Verify before publication:

- calibration is recorded and actual execution/topology stayed within it;
- all tracked areas and ten lenses are accounted for;
- every M1 is reproducible and every M2 mechanically conclusive;
- M3, failed experiments, boundaries, and strengths are separately counted;
- all claims preserve semantic invariants and disclose measurement limits;
- commands, versions, samples, counts, links, paths, priorities, and dependencies agree;
- no secret/sensitive identifier or unsupported external comparison appears;
- temporary artifacts and unsuccessful runtime changes are absent;
- report is the only repository diff;
- final writers: one; every accepted finding verified by primary; unauthorized nested delegation: zero.
