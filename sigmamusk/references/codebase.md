# One codebase: cut the largest files

Reduce code with the user. Behavior, tests, public interfaces and user data stay intact. Steps 1 and 2 of the skill are the thinking; these five steps are the work. Nothing is edited before step 4.

## 1. Scan

- Read the repo's `AGENTS.md`, `CLAUDE.md`, `README` and, where it exists, `ENGINEERING.md` before you touch code. Record the working-tree status: the user's uncommitted changes are not targets.
- Count the physical lines of every maintained source file: `git ls-files --cached --others --exclude-standard`, without docs (`*.md`, `*.mdx`, `*.rst`), lock files and generated or vendored folders. Say what you left out. `laloc -p <root> -m 0` does the count when the command exists; check its list against git's, because it skips folders such as `bin` and `packages`.
- Rank by lines, then by path. Take the first five. A file you could not read makes the ranking incomplete: say so.

**Done when:** the report names the five files, their counts, the counting command and every exclusion.

## 2. Read

Read each of the five from start to end, with its callers, imports, exports, command paths and tests. For each file say what it is for, why it is large, what repeats, what is coupled and what the tests protect.

## 3. Agree

Offer concrete choices per file: delete proven waste, simplify logic, extract one focused module, split responsibilities, add a test first, or leave it. For each choice give the expected line change, the lines only moved, the effect on public interfaces, the risk and the check. A smaller file is not the goal when it makes the design worse. Keep talking until the user has picked the files and one plan. No edit before that.

## 4. Cut

- Run the tests first and record the result. A red baseline goes to the user before anything else.
- One behavior-preserving change at a time. Public names, command output, stored data, error handling and user customizations stay unless the user approved a change.
- Add a test only where no test can prove the agreed behavior. Never weaken or delete a test to save lines.

## 5. Verify

Run the full checks once, after the last cut. Count again with the same command: lines removed, lines only moved, the new top five. Read the whole diff for lost files, changed interfaces, formatting-only compression and unrelated edits. Commit, push or open a PR only when the user or the surrounding task says so. Report the test commands, their results, what you did not check and the command that repeats the scan.
