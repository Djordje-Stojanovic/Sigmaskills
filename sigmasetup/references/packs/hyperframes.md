# HyperFrames pack setup

Sources: [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) (`skills/`) and [nateherkai/hyperframes-student-kit](https://github.com/nateherkai/hyperframes-student-kit) (`.agents/skills/`).

## HyperFrames

- Machine: Node.js 22+, FFmpeg, Chrome (`npx hyperframes browser ensure` when missing).
- Once per project: `npx hyperframes init <dir>`; check with `npx hyperframes doctor` and `npx hyperframes media-use resolve --doctor`.
- Optional keys, in the shell or the project `.env` (ignored by git): `GEMINI_API_KEY`, `HEYGEN_API_KEY`, `FIGMA_TOKEN` for `/figma`. The `heygen` CLI logs in with `heygen auth login --oauth`; the owner does that.
- Writes a `.media/` cache in the project.

## Student kit

- Machine: Node 22+, Git, FFmpeg with ffprobe, Chrome or Chromium.
- Several skills (`cut-silences`, `cut-mistakes`, `short-form-edit`, `edit-video`) call scripts that live in the kit repo (`scripts/*.mjs`). Copying the skills alone is not enough: work inside a clone of the kit, then run `npm ci`, `npm run setup` (creates `.env`) and `npm test`.
- Keys in that `.env`: `ELEVENLABS_API_KEY` (default for transcription); optional `OPENAI_API_KEY`, `KIE_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`.
