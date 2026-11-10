# The question round

One message. Numbered, at most 10. Each line: the question, then `Recommended: <answer>` with a few words of why. Fill the recommendations from what you read in step 1. The user can reply "all recommended" or change single numbers.

Question 1 is the crew shape, always first: every other answer (models, slots, wake, cost) follows from it.

For a T3 Code run, the round must settle five things: crew shape, host, model chain, wake, stop line (questions 1, 2, 3 and 10 carry them; see [host-t3-code.md](host-t3-code.md)).

Ask only what the repo cannot answer. If it answers one fully (a stop line in the ticket, a rule in `AGENTS.md`), merge that question into another and state the fact as given.

## The ten

1. **Crew shape, with its cost.** Offer three, each with what it costs in usage and what it buys: **Solo** (no subagents; one ticket at a time; cheapest, slowest). **Small crew** (for example 4 workers, 2 reviewers, 1 clerk; about as many live threads as tickets in flight; fast, mid cost). **Large crew** (8 or more workers; fastest, burns the weekly limit in hours, needs many independent tickets). One recommendation: small crew when step 1 found 5 or more independent open tickets; solo for fewer, or when the host cannot start agents (pi, some T3 providers); large only when the user names it. A repo rule in `AGENTS.md` or memory wins. Each role has one job that never changes during the run: worker, reviewer, clerk.
2. **Host, and live or headless.** Claude Code `/loop` or `/goal`, Codex `/goal`, Antigravity `agy` `/goal`, pi with lapi, T3 Code, or other (plain instruction); and whether a person leaves a session open or a script starts it. Recommended: the host the user is already in, live; `/goal` when one printed command proves the end (Claude Code, Codex, `agy`, T3 Code); `/loop` only when the work waits on a clock. Headless: Claude Code or `agy` `-p "/goal …"`, or a Codex `Stop` hook.
3. **Models and effort per role.** One model and effort for each role in question 1. Recommended: the repo's rule if `AGENTS.md` or memory names one; else a cheap model for bulk work, a mid model for workers, the top model for planning and reviews, effort from the repo's rule, else high, lowered where the role's check still passes. A reviewer comes from a different family than its writer. T3 Code: read `orchestrator_capabilities`, name each id from it (never from memory), list the chain in order of preference, and set a usage floor (for example, skip a model when its weekly limit is under 20%).
4. **End time and zone.** Date, clock time, time zone; also the longest the loop may run. Recommended: the deadline in the ticket or plan, else the next morning at a time the user named earlier, else 8 hours from now. State the zone you use. Claude Code expires a recurring loop after 7 days, so flag any run longer than that.
5. **Scope and order.** The ranked list from step 1 (id, one line, size). Recommended: top down by value, then by unblocking power; blocked and user-live items last or off. Show the first 10 and the count of the rest.
6. **Where it runs, and who else works.** Machine, checkout, and every other agent or person writing in the same repo. Recommended: the current machine; each worker in its own worktree off the base branch; a no-touch list for anything another agent owns.
7. **Off-limits.** Items, files, systems, and actions the loop must never touch (user-live decisions, production data, other lanes, secrets). Recommended: everything marked "needs the user" or owned by another agent in step 1, plus any irreversible delete of data.
8. **Pre-authorised actions.** Which of these the loop may do without asking: commit, push, open PR, merge, deploy, delete merged branches and worktrees, close tickets. Recommended: commit, push, PR, merge after the loop's own check, delete merged branches and worktrees; deploy only if the repo has a named deploy step and the user listed it. Nothing destructive outside that.
9. **Landing.** What "done" means for one item. Recommended: code and tests first; docs and tracker updated; the PR template filled from the first push; PR merged and branch and worktree gone; deploy proof when the repo deploys; the tick has a date and evidence (number, path, PR). Name the repo's own commands (test, lint, deploy).
10. **Stop line and extras.** What ends the loop: the time, or "every item ticked", whichever comes first. Claude Code and T3 Code `/goal`: also the one command whose printed output proves it (its exact text). Then the finish block: what to report, what to clean up. Recommended: at the stop time start nothing new, let running agents finish, write state into each item, run the sync proof (loop file, Finish), report short. Extras, only if asked: handoff path (recommended: the ticket's handoff section, else the loop file); a Codex token budget; when fewer than three items are workable, search the repo for the next bug, speed gain, or quality fix.

## After the reply

- Take the recommended answer for any blank and add it to the loop file as `Ruling: <what> — <why> — <cost if wrong>`.
- A pre-authorisation the user did not give is not given. Write "ask" for it in the loop file.
- If a reply contradicts the repo (for example, merge allowed but the repo wants review), take the user's word and log the conflict as a ruling.
