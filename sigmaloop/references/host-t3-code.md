# T3 Code: `schedule_task`

Marks: **ran** (run by the author, Windows 11), **doc**, **source**. See [hosts.md](hosts.md) for the table and the plain instruction.

T3 Code controls other agents (Codex, Claude Code, Cursor, Grok, OpenCode, Antigravity) and runs no loop of its own ([README](https://github.com/pingdotgg/t3code)). It does have a scheduler. Facts (source: `apps/server/src/mcp/toolkits/orchestrator/tools.ts`, `apps/server/src/scheduledTasks/`, `packages/contracts/src/scheduledTask.ts`; [permission modes](https://github.com/pingdotgg/t3code/blob/main/docs/user/permission-modes.md)). Not run: live run pending. A T3 database seen by the author held one task made by an agent through this MCP tool: every 30 minutes, bound to its thread, Full access, 43 runs, last status succeeded (ran: a read of the database).

- The `schedule_task` tool makes persistent work that runs when no turn is active: `{type:'interval', everyMs}` (minimum 60,000), `{type:'fixed_time', timeOfDay:'09:00', weekdays:[…]}`, or `{type:'webhook'}` (source). By default each run posts into the calling thread (`bindToCurrentThread`); the message is sent in queue mode (source). Related tools: `list_scheduled_tasks`, `update_scheduled_task` (`enabled=false` pauses), `delete_scheduled_task` (source). The owner can also make one in Settings, Scheduled tasks.
- Only Full access runs without prompts; any other mode waits for the owner, and a question to the owner pauses the run (doc).
- Whether a provider's own `/loop` or `/goal` works in the composer is not documented. Do not assume it.
- If the tool is missing in the thread, connect the T3 MCP URL (`docs/user/outside-agents.md`) or use the plain instruction.

Prompt skeleton:

```text
Work unattended until <time, zone>. You are the orchestrator. Rules and order live in <loop file path>.
Now call schedule_task: schedule {type:'interval', everyMs:<900000>}, bindToCurrentThread true, prompt: "Re-read <loop file path>. Read the clock. Before <time, zone>: do the next item in Priority. At or after it: do the Finish block, then call update_scheduled_task with enabled=false for this task." Then start item 1.
ORDER: <loop file> "Priority", top down. First: <items 1-3>.
CREW: <mix, or solo>.
LANDING: <one line>.
AUTHORISED: <list>. Do not stop to ask; take the safer option and log it.
```

Tell the user: set the thread to Full access; the T3 server must keep running (README: `t3 service install` keeps it in the background); delete the task in Settings when done.
