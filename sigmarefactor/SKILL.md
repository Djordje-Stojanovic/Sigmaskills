---
name: sigmarefactor
description: Guide safe, user-approved reduction of repository code size after a laloc scan. Use when the user wants large files reviewed and simplified without losing behavior. Do not use for an unattended rewrite, a line-count contest, or a performance audit.
---

# SigmaRefactor

Reduce unnecessary code with the user. Keep behavior, tests, public interfaces, and user data intact.

Read [scan.md](references/scan.md) before the first scan. It defines the file inventory, counting rules, and `laloc` limits.

## Workflow

### 1. Scan

- Resolve the repository root. Read its `AGENTS.md`, `CLAUDE.md`, `README`, and relevant project instructions before touching code.
- Record the working-tree status. Preserve existing user changes and do not treat them as refactoring targets without agreement.
- Run `laloc -p <root> -m 0` when the command is available. Quote every exclusion. Use the reference fallback when it is unavailable.
- Compare the result with the repository file inventory. `laloc` can skip maintained source directories. Count eligible files that its output missed.
- Rank eligible files by physical line count, descending, then by path. Select the first five, or all eligible files when fewer than five exist. State ties and exclusions.

Completion criterion: the report names the exact files, counts, counting method, and any files the scan could not read.

### 2. Read

- Read every selected file from start to end. Use ordered chunks for large files and confirm that no chunk is missing.
- Trace each file's callers, imports, exports, command paths, and relevant tests. Read the smallest surrounding context needed to understand those contracts.
- Describe each file's purpose, responsibilities, repeated logic, risky coupling, and current test protection.

Completion criterion: the user can see why each file is large and what behavior depends on it.

### 3. Discuss and agree

- Explain findings in clear technical English. Use SigmaWrite when it is available; otherwise keep the same plain style.
- Offer specific choices: remove proven waste, simplify logic, extract a focused module, split responsibilities, add tests first, or leave the file unchanged.
- Give the expected line change, moved lines, public-interface impact, risk, and verification for each choice. A smaller file is not required when it would make the design worse.
- Keep discussing until the user selects the files and accepts one concrete refactoring plan. Do not edit during this step.

Completion criterion: the agreed plan has explicit files, behavior to preserve, tests, and a stopping point.

### 4. Implement

- Run the relevant test commands before editing and record the baseline. If the baseline fails, show the failure and agree whether to continue.
- Make one behavior-preserving change at a time. Prefer existing seams and small modules with clear interfaces.
- Keep public names, command output, persisted data, error handling, and user customizations stable unless the user approved a change.
- Add behavior tests only where current tests cannot prove the agreed behavior. Do not weaken or delete tests to reduce lines.

Completion criterion: the agreed refactoring is present and every preserved behavior has a test or an existing verified contract.

### 5. Verify and deliver

- Run focused tests after each change, then the full repository checks. Re-run the same line-count method and show physical lines removed, lines moved to new files, and the final top-five list.
- Inspect the complete diff for lost files, accidental interface changes, formatting-only compression, and unrelated edits.
- Follow the user's chosen Git workflow. Commit and push only when requested or when the surrounding task already authorizes it; prepare a reviewable PR when requested.
- Report test commands, results, known limits, and the exact command the user can run to repeat the scan.

Completion criterion: verification is green or every remaining failure is named, and the user has a reviewable result.

## Boundaries

This skill may read `C:\Coding\Thinkcenter_Setup` to understand `laloc` and may use it as a read-only trial repository. It does not change that repository or load its full profile automatically.

Use SigmaBrief only when the user asks for an agent brief or delegation. Use SigmaWrite as a writing voice, not as a required dependency. The skill must work when both skills are absent.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
