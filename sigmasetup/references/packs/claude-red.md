# Claude Red pack setup

Source: [SnailSploit/Claude-Red](https://github.com/SnailSploit/Claude-Red), pinned to one commit. License: MIT.

- Authorized tests. Ask the owner for the scope once: which systems, and who authorized the test. Write it to the repo's `AGENTS.md` (or a `SCOPE.md`) so every session reads it. Undo: delete those lines or the file.
- Tools: each skill names its own (`pwntools`, `frida-tools`, `ropgadget`, `pypykatz` and more). Install only what the engagement needs, in a virtual environment or a VM.
- Keys: the tokens the skills name (`GITHUB_TOKEN`, `VAULT_TOKEN`, cloud IDs) belong to the target under test. None is needed for setup.
