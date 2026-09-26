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

## Review rounds
| Round | Status | P0–P2 found / fixed | P3 | Commits |
|---|---|---|---|---|
```

For several tickets that must land together, add one `Closes #<n>` line per ticket. Otherwise ship one ticket per PR.

## Land

Check the preconditions, in order. Fix any that fail, and check again:

1. The last review round is clean, and the ledger shows it.
2. The branch is current with the base: `git fetch origin && git merge-base --is-ancestor origin/<base> HEAD`. If it is behind, merge the base in (never rebase a pushed branch), run the full checks, and push.
3. CI is green on the head commit, and no review thread is unresolved.

Merge with the repository's convention: squash when the repository has none. Use the host's merge (for example `gh pr merge <n> --squash --delete-branch`, or the GitHub tool), so the branch protection rules apply. Never force-push, never merge red, and never delete a branch you did not create.

Then:

1. Confirm the issue is closed. If `Closes` did not close it, close it with a comment that links the PR.
2. If a parent map exists, tick this ticket there, or comment on the map with the PR link.
3. File every *Follow-up* from the ledger as a new issue when the user wants them tracked, and link each one from the PR.

## Clean up

Run these from the main checkout, not from inside the worktree:

```bash
git worktree remove <worktree-path>   # add --force only for untracked build output
git worktree prune
git branch -D <branch>                # only after the PR shows merged; a squash merge makes -d refuse
git push origin --delete <branch> 2>/dev/null || true   # already gone if the merge deleted it
git checkout <base>
git pull --ff-only origin <base>
git fetch --prune origin
```

If the host created the worktree with a native tool, remove it with that tool instead.

## Verify

Each line must print the expected result. Report the output.

```bash
test "$(git rev-parse <base>)" = "$(git rev-parse origin/<base>)" && echo "main in sync"
test -z "$(git status --porcelain)" && echo "tree clean"
git worktree list                      # no entry for the ship worktree
git branch --list <branch>             # empty
git ls-remote --heads origin <branch>  # empty
```

Also check the issue state (`closed`) and the PR state (`merged`) through the host.
