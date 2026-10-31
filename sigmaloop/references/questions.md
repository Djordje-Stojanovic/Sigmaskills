# The question round

One message. Numbered, at most 10. Each line: the question, then `Recommended: <answer>` with a few words of why. Fill the recommendations from what you read in step 1. The user can reply "all recommended" or change single numbers.

Ask only what the repo cannot answer. If it answers one fully (a stop line in the ticket, a rule in `AGENTS.md`), merge that question into another and state the fact as given.

## The ten

1. **Host, and live or headless.** Claude Code `/loop` or `/goal`, Codex `/goal`, Antigravity `agy` `/goal`, pi with lapi, T3 Code, or other (plain instruction); and whether a person leaves a session open or a script starts it. Recommended: the host the user is already in, live; else Claude Code `/loop` when the work waits on CI, renders, or deploys, and `/goal` (Codex or `agy`) when it is back-to-back work with a checkable end state. Headless: Claude Code or `agy` `-p "/goal …"`, or a Codex `Stop` hook.
2. **End time and zone.** Date, clock time, time zone; also the longest the loop may run. Recommended: the deadline in the ticket or plan, else the next morning at a time the user named earlier, else 8 hours from now. State the zone you use. Claude Code expires a recurring loop after 7 days, so flag any run longer than that.
3. **Scope and order.** The ranked list from step 1 (id, one line, size). Recommended: top down by value, then by unblocking power; blocked and user-live items last or off. Show the first 10 and the count of the rest.
4. **Crew and model mix.** Maximum agents at once, and the mix by job. Recommended: follow the repo's rule if `AGENTS.md` or memory names one; else 4 agents, model by difficulty (small for research and harvests, mid for code and drafts, top for reviews and the hardest items), each review one model up, at most 2 review rounds; a free slot takes the most valuable eligible item for its model, never a fixed lane. If the host has no sub-agents (pi, some T3 providers), say "solo, one item at a time".
5. **Where it runs, and who else works.** Machine, checkout, and every other agent or person writing in the same repo. Recommended: the current machine; each parallel agent in its own worktree off the base branch; a no-touch list for anything another agent owns.
6. **Off-limits.** Items, files, systems, and actions the loop must never touch (user-live decisions, production data, other lanes, secrets). Recommended: everything marked "needs the user" or owned by another agent in step 1, plus any irreversible delete of data.
7. **Pre-authorised actions.** Which of these the loop may do without asking: commit, push, open PR, merge, deploy, delete merged branches and worktrees, close tickets. Recommended: commit, push, PR, merge after the loop's own check, delete merged branches and worktrees; deploy only if the repo has a named deploy step and the user listed it. Nothing destructive outside that.
8. **Landing.** What "done" means for one item. Recommended: code and tests first; docs and tracker updated; PR merged and branch and worktree gone; deploy proof when the repo deploys; the tick has a date and evidence (number, path, PR). Name the repo's own commands (test, lint, deploy).
9. **Stop line.** What ends the loop: the time, or "every item ticked", whichever comes first. Claude Code `/goal` and T3 Code run to done: also the one command whose printed output proves it (its exact text). And the finish block: what to report, what to clean up. Recommended: at the stop time start nothing new, let running agents finish the step, write state into each item, clean up, report short. An item left open gets a dated line: done, left, why, next step.
10. **Extras.** Anything else: where to write the handoff log, what to do when fewer than three items are workable, a Codex token budget, model names for the mix. Recommended: log into the ticket's handoff section (or the loop file if none); when the queue runs short, search the repo for the next bug, speed gain, or quality fix and add it as a new item.

## After the reply

- Take the recommended answer for any blank and add it to the loop file as `Ruling: <what> — <why> — <cost if wrong>`.
- A pre-authorisation the user did not give is not given. Write "ask" for it in the loop file.
- If a reply contradicts the repo (for example, merge allowed but the repo wants review), take the user's word and log the conflict as a ruling.
