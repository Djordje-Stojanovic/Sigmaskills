# Proxy answerer

The owner may name a model to answer for the owner ("use a medium subagent as my proxy").

**Start it.** Use the harness's own subagent when it runs that model. For a model of another provider, find the way this machine starts one: an orchestrator tool the harness gives you, or that provider's own CLI run headless. Example that worked: in T3 Code, `t3 thread start . - --provider <instance id> --model <slug> --wait`, with the hand-off on stdin (instance ids in `~/.t3/userdata/settings.json`, `providerInstances`). When the first way fails, try 2-3 others before you tell the owner, and name the one that worked.

**Its prompt:** the goal, where the owner's steering files and past answers are, the card format (Why, Done, Left, Pick), and "pick a letter, give one line of reason, flag anything the owner might not pick".

Treat each proxy answer like the owner's own: grill it until the topic is clear, then plan and ship it. An irreversible or data-deleting choice waits for the owner's own yes.
