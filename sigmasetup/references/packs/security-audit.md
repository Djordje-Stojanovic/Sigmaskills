# Security Audit pack setup

Source: [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) by Cloudflare, pinned to one commit. License: MIT.

- **Agent.** A model with tool use and parallel sub-agents. Without sub-agents, tell the owner the audit will not run as designed.
- **Node.js**, for the two validators (`validate-findings.cjs`, `validate-coverage-ledger.cjs`). They have no dependencies. Check with `node --version`.
- **Output.** The audit writes `findings.json` and `coverage-ledger.json`. Ask the owner where they go and whether git ignores them.
- Keys and MCP servers: none stated.
