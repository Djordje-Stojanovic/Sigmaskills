# PR ledger, landing, and cleanup

## PR ledger

Title: `<issue title> (#<issue>)`. Body:

```markdown
Closes #<issue>
Spec: <link or "in the issue"> · Map: <parent issue or "none">

## Acceptance
- [ ] <criterion 1> — evidence: <test name / command>
- [ ] <criterion 2> — evidence: …

## Rulings
- <decision> — <reason> — <cost if wrong>

## Follow-ups (not in this PR)
- <thing noticed, with location>

## Known reds (not mine)
- <failing test> — also red on origin/<base> — <lane or ticket that owns it>

## Review rounds
| Round | Status | P0–P2 found / fixed | P3 | Commits |
|---|---|---|---|---|
```

For tickets that must land together, add one `Closes #<n>` line each. Otherwise one ticket per PR.

## Land

Check in order; fix any failure and check again:

1. The last review round is clean, and the ledger shows it.
2. The branch is current with the base: `git fetch origin && git merge-base --is-ancestor origin/<base> HEAD`. If behind, merge the base in (never rebase a pushed branch), run the full checks, and push.
3. CI is green on the head commit, and no review thread is open.

Merge with the repository's convention: squash when it has none (one short-lived branch, one logical change). Use the host's merge so branch protection applies: `gh pr merge <n> --squash --match-head-commit <sha>` (the flag refuses the merge if someone pushed after your check; add `--auto` while required checks still run). The squash subject is the PR title with `(#<n>)`. Never force-push, merge red, or use `--admin` to skip a rule. Never delete a branch you did not create.

Skip `--delete-branch` while the worktree holds the branch: the local delete fails. Clean up after the merge, as below.

Then:

1. Confirm the issue is closed. If `Closes` did not close it, close it with a comment that links the PR.
2. Tick the ticket on the parent map, or comment there with the PR link.
3. Tick it in your tracker (a file, a board): date, PR number, one line of evidence. An item leaves the open list only when the PR is merged and its branch and worktree are gone.
4. File each *Follow-up* as a new issue when the user wants them tracked, and link it from the PR.

## Clean up

Run from the main checkout, not from inside the worktree. The lines show POSIX shell; use the machine's own shell (PowerShell on Windows). In a shared main checkout, never check out, reset, or force.

```text
git worktree remove <worktree-path>   # add --force only for untracked build output
git worktree prune
git branch -D <branch>                # only after the PR shows merged; a squash merge makes -d refuse
git push origin --delete <branch> 2>/dev/null || true   # already gone if the host deleted it
git fetch --prune origin
git merge --ff-only origin/<base>     # no checkout, no pull
```

`--ff-only` refuses safely when another agent's uncommitted files would be overwritten. Report the refusal and leave those files alone. If the host made the worktree with a native tool, remove it with that tool.

## Deploy and prove

If the repository has a deploy, install, or sync step, run it from the updated main checkout (`<deploy command>`), then one command that shows the new behavior live (a version string, a changed endpoint). A deploy with no proof is not done. If published guides changed, run the docs sync (`<docs sync command>`) and check the page.

## Verify

Each line must print the expected result. Report the output.

```text
test "$(git rev-parse <base>)" = "$(git rev-parse origin/<base>)" && echo "main in sync"
test -z "$(git status --porcelain)" && echo "tree clean"
git worktree list                      # no entry for the ship worktree
git branch --list <branch>             # empty
git ls-remote --heads origin <branch>  # empty
```

In a shared checkout, "tree clean" may fail on another agent's files: name them as theirs, do not clean them. Also check the issue (`closed`) and the PR (`merged`) through the host.
