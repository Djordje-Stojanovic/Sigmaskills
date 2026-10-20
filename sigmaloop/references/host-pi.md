# pi: lapi plan loop, stock pi

Marks: **ran** (run by the author, Windows 11), **doc**, **source**. See [hosts.md](hosts.md) for the table and the plain instruction.

Facts for lapi (source: the Plan and Code prompts, `qwen-general-sampling.ts` and `lapi-lib.ts` of the lapi extension, a pi setup with Plan and Code modes; [pi docs](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent/docs)). `pi -p "/skill:sigmaloop …"` loads the skill and answers from `hosts.md` (ran, Windows and Linux). The plan loop needs the interactive session: `pi -p "/code"` only switches the session to Code mode and exits; a following `pi -p -c` ran one turn, ticked one box, and exited without starting the next (ran). Over `--mode rpc` the agent ticked two of three boxes in one run and stopped (ran). Live run of the TUI loop pending.

- Stock pi has no loop and no scheduler (doc). lapi adds one: in Code mode, when the dated plan file under `.pi/plans/` has open `- [ ]` boxes inside `<!-- lapi-workflow -->` … `<!-- /lapi-workflow -->`, lapi starts the next turn each time the agent goes idle (source). Boxes outside the fence are not a loop; no fence means no loop (source).
- The loop starts from Plan mode. In chat the plan is one `[LAPI_PLAN]` … `[/LAPI_PLAN]` block with nothing after it. The dated file holds the same block, then the fence (Plan may write only there). `/code`, or `/code-fresh` for a new session, starts Code mode (source).
- It stops when every box is ticked, or the agent writes `[LAPI_PLAN_DONE]` (source). A turn with no write, edit, or bash waits for the owner (source). Controls: `Esc` pauses, `/plan pause`, `/plan resume`, `/plan clear`, `/plan-stop` (source).
- No clock: the loop ends when the boxes end. For a clock stop line, make the first boxes the ranked items, and end with a box that reads the clock and, before the stop line, adds new boxes above itself.
- Plan mode is read-only except `.pi/plans/` (source). Sigma skills are opt-in in the Plan picker (`/skills`).

Prompt skeleton:

```text
Plan mode. Use the answers in <loop file path>; ask nothing new. Write the plan: Mission (outcome, stop line <time, zone>), Boundaries, Invariants, Order (<loop file> "Priority"), Landing (<one line>), Authorised (<list>). Put the loop in the dated file under .pi/plans/:
<!-- lapi-workflow -->
- [ ] Re-read <loop file path>. Do item <1> to its Landing; tick it in the tracker with evidence.
- [ ] (one box per ranked item, the first <N>)
- [ ] Read the clock. Before <time, zone>: add the next items as new boxes above this one. At or after it: do the Finish block, then write [LAPI_PLAN_DONE].
<!-- /lapi-workflow -->
Then stop and wait: the owner starts the run with /code.
```

Tell the user: approve with `/code`; `Esc` pauses; keep the terminal open or use a multiplexer.

## Stock pi: plain instruction

pi has no scheduler; the session is the loop (doc). An extension can request one more turn with `agent_before_settle` and `continue: true` (doc, `docs/extensions.md`). A driver can send `follow_up` messages over RPC (doc, `docs/rpc-commands.md`). Without one, use the plain instruction and tell the user nothing restarts it.
