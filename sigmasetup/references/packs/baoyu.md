# Baoyu pack setup

Source: [Djordje-Stojanovic/baoyu-skills](https://github.com/Djordje-Stojanovic/baoyu-skills), an English fork of [JimLiu/baoyu-skills](https://github.com/JimLiu/baoyu-skills), pinned to one commit. License: MIT.

- Machine: Bun runs the scripts (`bun`, else `npx -y bun`; install with `brew install oven-sh/bun/bun` or `npm install -g bun`).
- Image skills need a provider before the first run. `baoyu-image-gen` asks once and saves the answer in `.baoyu-skills/baoyu-image-gen/EXTEND.md` (this project) or under `~/.config/baoyu-skills/`. Offer the project path, and add `.baoyu-skills/` to `.gitignore` when it holds account settings. Undo: delete the folder.
- Keys, in the environment, only for the provider the owner picks: `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `REPLICATE_API_TOKEN`, `AZURE_OPENAI_API_KEY`, `DASHSCOPE_API_KEY`, `ARK_API_KEY`, `MINIMAX_API_KEY`, or `JIMENG_ACCESS_KEY_ID` with `JIMENG_SECRET_ACCESS_KEY`.
- The posting skills (`baoyu-post-to-x`, `baoyu-post-to-weibo`, `baoyu-post-to-wechat`) sign in through the owner's browser; WeChat also needs `WECHAT_APP_ID` and `WECHAT_APP_SECRET`. They publish, so run them on the owner's word.
