# Review

By default the builder reviews its own work: SigmaShip trades the second pair of eyes for speed, and keeps quality by reading and running the change. A second agent reviews only when the user asks for one.

## Self-review

Do it on your own diff, after the full checks are green:

1. Did the ticket ask for this? Go through `git diff --stat origin/<base>...HEAD` file by file. Revert a change that no criterion needs.
2. Spec: for each acceptance criterion, confirm the code meets it and a test proves it.
3. Risky files (list below): read each one in full, not only the hunks. Look at correctness and edge cases, error handling, security, money, data loss, deploy config, tests that would miss a real failure, and the repository's documented standards.
4. Run it: the app, page, command or skill itself, the way a user meets it. Look at the result.
5. Rate findings P0–P2 as in step 6 of the template below; fix each with a test first, commit `fix(#<issue>): <what>`, push. Record one ledger row: round `self`, status, counts, commits.

## When the user asks for a reviewer

"with review", "reviewer: <model>" or "SigmaShip reviewer: <model>" turn on review rounds. Start a fresh sub-agent of your harness (one model up from the builder when it has one), or the named model by any route that reaches it (see the last section). Give it the handoff below; it must stand alone. The reviewer fixes findings on the branch without waiting for approval and reports in the `CLEAN | FIXED | BLOCKED` form. Round 2 reviews the fix commits, sent to the same reviewer by a follow-up message when the harness has one. At most 2 rounds: a round 2 that still finds P0–P2 problems means the ticket or design is wrong, so stop and ask the user.

## Handoff template

```text
Review and fix PR <pr-url> (branch <branch>) for issue <issue-url>. Round <n> of at most 2.

Intent (the ticket's goal and acceptance criteria, copied from the issue; not what the code does):
<intent>

Diff summary (`git diff --stat origin/<base>...HEAD`):
<the stat>

Writer's lines (the Skipped and Risk lines of the builder's reply footer, or the PR ledger's rulings and follow-ups):
Skipped: <what the builder did not do or did not check>
Risk: <what the builder says could break>

Risky files (read every line): <list, see "Risky files" below>
All other files: <the rest of the stat>

Setup:
1. Check out the branch in a new worktree, or use the existing one at <path>. Install the dependencies. Do not read the whole diff first. Leave out of the diff the paths the repo names as the owner's content: no model passes or fails his words.

Review, in this order:
2. Did the ticket ask for this? Go through the stat file by file. A change that no criterion needs is a finding: revert it, do not defend it.
3. Spec: for each acceptance criterion, confirm that the code meets it and that a test proves it. List every gap. Treat the writer's Skipped line as a claim to test, not as an excuse.
4. Risky files: read each one in full, not only the changed hunks. Look at correctness and edge cases, error handling, security (authorization, input handling, secrets printed or logged), money, data loss, deploy config, tests that would miss a real failure, and this repository's documented standards. You may add a file to the risky list. Never remove one.
5. All other files: read a hunk (`git diff origin/<base>...HEAD -- <path>`) only when the stat is larger than the intent explains, the Risk line names the file, or step 2 raised a doubt. Do not open whole files.
6. Rate each finding P0 (exploitable now, data loss, or the system is unusable), P1 (a primary journey is broken, insecure, or breaks its budget), P2 (material but bounded), or P3 (small, with a demonstrated cost). A failed acceptance criterion or an unasked change is at least P2. Keep only findings with a concrete location and trigger.

Fix:
7. For each P0–P2 finding: write a test that fails, fix it, and commit as fix(#<issue>): <what>. Keep the fix inside the ticket. After the last fix, run the full checks once (<test / type check / lint commands>) and push.
8. List P3 findings in your report only. Do not change unrelated code.

Report back in exactly this form:
Status: CLEAN | FIXED | BLOCKED
P0–P2 found: <n> (fixed: <n>) · P3 noted: <n>
Findings: <one line each: ID, priority, path:line, what, commit>
Read in full: <the risky files>
Checks: <commands and results>
```

## Risky files

A file is risky when its path or its changed lines touch money (payment, billing, price), security (auth, token, secret, key, password, credential, permission), migrations (schema, stored data) or deploy config (Dockerfile, compose, CI workflow, installer, release script, lockfile). The builder lists them from the diff:

```bash
git diff --name-only origin/<base>...HEAD | grep -Ei 'pay|bill|price|auth|token|secret|key|passw|cred|perm|migrat|schema|docker|compose|workflow|install|release|lock'
git diff -i -G'pay|bill|price|auth|token|secret|passw|cred|migrat|schema|docker|compose' --name-only origin/<base>...HEAD -- . ':!*.md' ':!tests'
```

Prose in `.md` files and test files do not count by themselves. When in doubt, list the file: one miss costs more than a few extra lines read.

## Round rules

- **Clean** means zero P0–P2 findings. A round that found and fixed P0–P2 findings is not clean; round 2 reviews the fixes.
- Record each round in the ledger's *Review rounds* table: round, status, counts, commits.
- `BLOCKED`: read the reason, fix what you can, ask the user about the rest.

## Reaching a named reviewer

When the harness cannot run the model the user named, any route that reaches it works; log which one did. Routes that work: a harness that runs several providers from one place (T3 Code does; read its own docs for the command), the model's own CLI run headless in the branch worktree with closed input, or its API with the handoff as the prompt. When none reaches it, say so in one line and use a fresh sub-agent of your harness.
