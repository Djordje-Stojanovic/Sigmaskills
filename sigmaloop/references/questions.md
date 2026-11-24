# The question round

One message, numbered, at most 10. Each line: the question, then `Recommended: <answer>` with a few words of why, drawn from step 1. The user can reply "all recommended" or change single numbers. Ask only what the repo cannot answer; state a fact the repo gives instead of asking it.

## The ten

1. **Speed metric.** What counts as one accepted unit, and what rate do we watch? Recommended: accepted units per hour and per million tokens; drafted work counts zero until accepted.
2. **Crew shape.** Solo, N slots, or N lanes. Recommended: solo for fewer than 5 independent units or a host that cannot start agents; else as many slots as CPU and the queue allow, with a parallel-process cap from the machine's cores. A repo rule wins.
3. **Roles and tiers.** Planner, builder, reviewer, clerk, each with a tier (cheap, mid, top) and model ids in fallback order. Also how many reviewers run at once. Recommended: the repo's model file if it has one; else cheap builders and clerk, a mid reviewer from another provider than the builder, one per finished ticket with no cap, the top tier only for planning; effort from the repo's rule, else high, lowered where the role's check still passes. Ids from the host's own list, never from memory.
4. **Machine, harness and start.** Which machine runs the work and its checks: this one, another of the user's, or rented compute. Ask even when the request names one: sentence order is no ranking. Ask which harness runs it only when SKILL.md step 2 could not tell. Then: its run-to-done command (`/goal` where it exists), a clock wake, or a plain instruction; live or headless. Recommended: the harness's own run-to-done in the session the user is in, no wake task, no cron.
5. **Stop line.** The one command whose printed output proves done, and/or a time and zone. Recommended: the tracker's own status command plus a time cap.
6. **Scope and order.** The ranked list (id, line, size). Recommended: value first, then unblocking power; blocked and user-live items last. Show the first 10 and a count.
7. **What may be deleted.** Records, checks, gates and scaffolding the run may cut. Recommended: records no machine reads, checks that never caught anything, a gate that never passed; nothing in user content.
8. **Limits.** The owner's orders (his sentence and its date for each), mechanical guards (the fault each prevents) and scope notes (what no ticket covers; a note, not a ban). Recommended: user-live items, other agents' work, production data, irreversible deletes of data.
9. **Pre-authorised actions and budgets.** Commit, push, PR, merge, deploy, delete merged branches and worktrees, close tickets; and each spend limit (what, amount, period, the command that prints used). Recommended: no meter, no budget; all but deploy; deploy only when the repo names a deploy step.
10. **Landing and failure limits.** What done means for one unit, review passes, fix tries before a park, and the stuck time. Recommended: one feature branch with one PR for all tickets (a PR per ticket, or one shared checkout, when asked), unit tests pass, 3 review passes (5 for security, data loss or publishing) then the builder fixes and lands, parked after 3 failed fix tries, the builder ticks its own box with evidence; stuck after 30 minutes with no commit or output.

## After the reply

- Take the recommended answer for any blank and log it as `Ruling: <what> - <why> - <cost if wrong>`.
- A pre-authorisation the user did not give is not given: write "ask" for it.
- A reply that contradicts the repo wins; log the conflict as a ruling.
