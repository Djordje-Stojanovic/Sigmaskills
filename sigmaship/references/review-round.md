# Review rounds

A review round gives the finished branch to an agent that has never seen the work. A fresh context catches what the builder's context hides. Write the handoff from the template below. SigmaBrief can help as a skeleton when it is installed, but its brief rules do not apply here: the reviewer fixes findings on the branch without waiting for approval, and reports in the `CLEAN | FIXED | BLOCKED` form below. That form wins. The handoff must stand alone.

## Handoff template

```text
Review and fix PR <pr-url> (branch <branch>) for issue <issue-url>. Round <n> of at most 3.

Setup:
1. Check out the branch in a new worktree, or use the existing one at <path>. Install and run: <test / type check / lint commands>.

Review, in this order:
2. Spec: read <issue-url> and <spec link>. For each acceptance criterion, confirm that the code meets it and that a test proves it. List every gap.
3. Defects in the diff (git diff origin/<base>...HEAD), using the SigmaReview lenses: correctness and edge cases, error handling, security (authorization, input handling, secrets), performance on the hot path, tests that would miss a real failure, and this repository's documented standards.
4. Rate each finding P0 (exploitable now, data loss, or the system is unusable), P1 (a primary journey is broken, insecure, or breaks its budget), P2 (material but bounded), or P3 (small, with a demonstrated cost). A failed acceptance criterion is at least P2. Keep only findings with a concrete location and trigger.

Fix:
5. For each P0–P2 finding: write a test that fails, fix it, run the full suite, commit as fix(#<issue>): <what>, and push. Keep the fix inside the ticket.
6. List P3 findings in your report only. Do not change unrelated code.

Report back in exactly this form:
Status: CLEAN | FIXED | BLOCKED
P0–P2 found: <n> (fixed: <n>) · P3 noted: <n>
Findings: <one line each: ID, priority, path:line, what, commit>
Checks: <commands and results>
```

## Round rules

- **Clean** means the round found zero P0–P2 findings. A round that found and fixed P0–P2 findings is not clean: run another round, because every fix can hide a new problem.
- After each round, record it in the PR ledger's *Review rounds* table: round, status, counts, and commits.
- Before the next round, check CI on the new head. A red CI is the builder's to fix before the next handoff.
- Three rounds that still find P0–P2 problems mean the ticket or the design is wrong. Stop and ask the user.
- `BLOCKED` from a reviewer: read the reason, fix what you can, and ask the user about the rest.
