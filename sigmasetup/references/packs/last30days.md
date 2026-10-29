# Last 30 Days pack setup

Source: [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill).

- Machine: `node` and Python 3.12+ (`uv` is the fallback).
- One-time, run by the owner: `scripts/last30days.py setup` (add `--allow-browser-cookies` only on the owner's yes). It installs `yt-dlp` and a few source CLIs and writes `~/.config/last30days/.env`. That is user-level config by the skill's own design; say so before running it.
- Per project, optional: `.claude/last30days.env`.
- Keys are all optional; the main one is `SCRAPECREATORS_API_KEY`. Others: `OPENAI_API_KEY`, `XAI_API_KEY`, `X_BEARER_TOKEN`, `OPENROUTER_API_KEY`, `PERPLEXITY_API_KEY`, `PARALLEL_API_KEY`, `BRAVE_API_KEY`, `APIFY_API_TOKEN`, `BSKY_HANDLE`, `BSKY_APP_PASSWORD`. The owner enters them.
- Saves reports to `~/Documents/Last30Days` by default.
- Removal leaves the `.env`, keychain entries and installed CLIs; list them for the owner.
