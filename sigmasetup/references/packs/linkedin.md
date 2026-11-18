# LinkedIn pack setup

Source: [sergebulaev/linkedin-skills](https://github.com/sergebulaev/linkedin-skills), pinned to one commit. License: MIT.

- The skills call a Python library in the repo's top-level `lib/` (`apify_client.py`, `url_parser.py`, `publora_client.py`) and read its `references/`. The installer copies only the skills, so reading and publishing need a clone: `git clone https://github.com/sergebulaev/linkedin-skills.git`, then `pip install -r requirements.txt` inside it, and work from there. Without it, the skills fall back to text the owner pastes.
- Keys, in the environment: `APIFY_TOKEN` reads posts, comments and engagers (the Apify MCP connector works without a token on disk). Optional AI-text detectors: `GPTZERO_API_KEY`, `ORIGINALITY_API_KEY`, `COPYLEAKS_API_KEY`, `SAPLING_API_KEY`, `ZEROGPT_API_KEY`. Publishing uses a Publora account.
