---
name: sigmacorrect
description: 'Use when asked for sigmacorrect, or when the owner corrects an agent for the same mistake a second time. Turns the correction into structure, a type, a check or a test, docs last. Do not use for a one-time bug (SigmaReview).'
---

# SigmaCorrect

A correction the owner gives twice must never be needed a third time. A sentence in a doc does not do that: the next agent skips it. SigmaCorrect changes the repo so the mistake fails before it ships. Example: "STOP hardcoding" becomes a check that fails on a hardcoded value, with an error that names where the value lives.

## 1. Find the repeat

Read the owner's words (the chat, his log, issue comments), reverts and fix commits (`git log --grep`), review comments, and the lesson lines in `AGENTS.md` and `CLAUDE.md`. A mistake counts once he corrected it twice. Write each one as one line: his words, and the two places it happened (commit, file, chat date). One counted once is not yet a repeat: leave it.

## 2. Pick the highest level that works

Try each in this order and take the first that makes the mistake impossible:

1. **Delete the wrong way.** One source of truth instead of two lists; one function to do the job; the old copy an agent would copy is gone.
2. **Make it fail to build.** A type, a required argument, a private module the wrong import cannot reach.
3. **A check that fails.** A lint, a grep or a script in the repo's own test command. Its error names the fix: the file, function or setting to use. When old code already breaks the rule, fail only on new lines.
4. **A test** of what the user sees, when the mistake is behaviour, not shape.
5. **A line in `AGENTS.md`**, last, only for a judgment call no machine can check.

## 3. Prove it

Replay the real past mistake in a scratch branch or a temporary copy of the file. The check must fail on it, with its error naming the fix, and pass on today's code. Paste both outputs. A check that never failed on the real mistake proves nothing.

## 4. Ship and record

One change per mistake, through the repo's own flow (SigmaShip when it has a ticket). The check runs in the repo's test command, so nobody has to remember it.

Keep one table in `AGENTS.md`, one row per mistake: the owner's words, and what now enforces it (file and command). When the owner corrects a mistake whose row is already there, the enforcement is missing or too weak: fix it one level higher in the same change. When a check holds the rule, delete the prose line that said it.

## Report

One line per mistake: his words, the two places it happened, the level picked and why a higher one did not work, the failing and passing output, the PR.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
