# tstack pack setup

Source: [t3dotgg/tstack](https://github.com/t3dotgg/tstack) by Theo Browne, pinned to one commit. License: MIT, copyright (c) 2026 Theo Browne (the `LICENSE` file in that repo).

- **GitHub CLI.** Most skills (`full-send`, `full-stop`, `file-pr`, `babysit-pr`, `modernize`, `takeover`, `leaving-pr-comments`, and `sol-loop` for PRs) need `gh`, signed in. Check with `gh auth status`. The owner signs in himself; the agent never types a token.
- **Python 3.** `babysit-pr` runs its `scripts/pr-wait` with `python3`. Check with `python3 --version`.
- **Reviewers on other models.** `council` and `sol-loop` ask reviewers on other providers' models. In T3 Code they use `delegate_task`. Elsewhere they need a host that can run those models. Without one, tell the owner that these two skills will not run here.
- **Model choices.** The upstream skills say to keep personal choices, such as which models sit on the council, in `CLAUDE.md` or `AGENTS.md`. Ask the owner before writing any of them there.
- **Merges.** `full-send` merges a PR after its checks pass, through branch protection. Its text says never to use `--admin`.
- Keys, MCP servers and other repo files: none stated.
