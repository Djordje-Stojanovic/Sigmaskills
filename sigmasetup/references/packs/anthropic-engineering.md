# Anthropic Engineering pack setup

Source: [anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) (`engineering/skills`), pinned to one commit. License: Apache-2.0.

- The skills name tools by category (`~~source control`, `~~project tracker`, `~~monitoring`, `~~chat`, `~~incident management`, `~~CI/CD`), not by product. They work without any; each connected tool makes them better.
- Optional MCP servers, from the plugin's `.mcp.json`: GitHub, Linear, Asana, Atlassian, Notion, Slack, Datadog, PagerDuty and others. The installer copies only the skills, so add a server only when the owner uses that product: `claude mcp add --transport http <name> <url> --scope project` writes `.mcp.json` in the repo. Undo: `claude mcp remove <name> --scope project`. Each server signs in with the owner's own account.
- Keys: none stated for the skills.
