# Engineering standards

One file, the same in all 3 repos (Design_Experiments, Thinkcenter_Setup, personal). Edit it in one repo, then copy it to the other two.
Sources: Musk's Algorithm (SpaceX, Tesla, xAI), Steve Jobs, Stefan (OSZII); Karpathy's coding rules ([andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md)).
For a trivial change, use judgment.

## 1. Simplicity first (Musk, Jobs, Stefan)

The Algorithm, in Musk's own words (Lex Fridman podcast; the whole passage, Jobs, Stefan and Raptor: Thinkcenter_Setup `docs/reference/SIMPLICITY.md`). Five steps, in this order:

1. "Make the requirements less dumb. The requirements are always dumb to some degree [...] no matter how smart the person who gave you those requirements [...] otherwise you could get the perfect answer to the wrong question."
2. "Try to delete whatever the step is, the part or the process step. [...] If you're not forced to put back at least 10% of what you delete, you're not deleting enough."
3. "Only the third thing is try to optimize it or simplify it. [...] The most common mistake of smart engineers is to optimize a thing that should not exist."
4. "Any given thing can be sped up. [...] But you shouldn't speed things up until it's optimized."
5. "The fifth thing is to automate it. I have gone backwards so many times where I automated something, sped it up, simplified it, and then deleted it."

What it looks like: Raptor 1 was a tangle of outside pipes; Raptor 3 moved them inside the metal, lost about 90 % of its welds and got lighter and stronger. Steve Jobs (1997): focus "means saying no to the hundred other good ideas"; "innovation is saying no to 1,000 things". Stefan, about a guide for a tool he does not use: as little as possible should be written down.

Simpler never means worse: we cut parts, steps and words, never what the viewer or user gets. So: the best part is no part. Every addition deletes something else. AI loves to add; say plainly what goes. Find the root cause and fix it once; a lesson becomes one line where the agent already reads, never a new check or test. Say what to do, not what to avoid ("make it 10-12 min", not "fail below 10"). Ship small and often, measure, then decide. The person who builds it runs it and fixes it.

## 2. How we write code (Karpathy)

[Ponytail](https://github.com/DietrichGebert/ponytail), on per project (`npx @djordje-stojanovic/sigmaskills ponytail --project .`), holds the rule for simple, surgical code: the least code that works, nothing nobody asked for, touch only what the task needs. Where it is off, that rule still holds. Two more rules:

1. **Think before coding.** State your assumptions. If two readings exist, name both. If something is unclear, stop and name it. Never ask about what a rule already decides.
2. **Goal-driven.** Turn each task into a check: write a test that fails, then make it pass. For a refactor, tests pass before and after. For more steps, write `step → check`, then loop until every check passes.

## 3. The rest, in a few lines

- **Modules:** few entry points, the complexity hidden inside. Delete a module in your head: if nothing gets harder, merge it away. Add a seam only when a second real case exists. Every product part works alone: one entry point, its config in one file, no hardcoded paths, hosts or channel names.
- **Decisions:** every project is planned, reviewed and decided on https://review.geldtools.com, not in chat. Every choice has a trade-off; write it down. One that a later agent could undo by mistake gets a short ADR (`docs/adr/`).
- **Pages people see:** colours, type and spacing from one token file; one bold idea per page; works on a phone and with a keyboard. Take a screenshot and look before you call it done.
- **Shipping:** one command, safe to run twice; never hand-edit a live server; know the rollback before you deploy; check the live page after.
- **Docs:** each fact lives in one place; change the docs in the same change as the code; an old doc is worse than none.

## 4. Fix only what is broken

- Redo only the broken part: re-voice one line, re-render only the broken seconds, re-check only what changed. Never redo the whole for a small fault.
- Look before the expensive step (stills before the render), fix everything found in one pass, then run it once.

## 5. Done means

Tests green, checked live, docs true, tracker current, and no helper server left running. Report what you ran and the result, including failures.
