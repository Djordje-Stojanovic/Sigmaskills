# Sources and what was merged

SigmaHuman is one skill made from every humanizer-like skill the Sigmaskills owner had, with blader/humanizer as the core.

| Source | Licence | What SigmaHuman takes |
|---|---|---|
| [blader/humanizer](https://github.com/blader/humanizer) v3.1.0, commit 8c307f3 (Siqi Chen) | MIT, text in [LICENSE-humanizer.txt](LICENSE-humanizer.txt) | The 26 patterns in [patterns.md](patterns.md), unchanged; the "why AI text sounds the way it does" section, the method (mark, draft, check, final), the voice rule, the return modes and "when not to act", lightly edited in SKILL.md |
| blader/humanizer v2.5.1, as kept in an Open WebUI skill copy | MIT (same author) | Section G of patterns.md (synonym cycling, false ranges, forced metaphors, a question answered at once, reassurance kickers and opener tics) and the voice-sample checklist in SKILL.md "Voice" |
| Wikipedia, ["Signs of AI writing"](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), WikiProject AI Cleanup | CC BY-SA 4.0 (the patterns paraphrase it; no text copied) | The source of the patterns |
| SigmaTaste prose lens | MIT (this repo) | The prose lens still judges; SigmaHuman does the rewrite |
| A blind test on a 14-minute narrated video script (2026-10-19, two judges) | n/a | The Ear lane. The skill applied once by an agent beat a fine-tuned 12B humanizer model and the model-then-skill mix under both judges, and lost no fact. The model cut sentences to about half their length (13.9 to 7.0 words on average), which judges heard as choppy: hence "keep the sentence-length band" and the band line in `scripts/factcheck.py` |

## What is new in SigmaHuman

- Two modes: Rewrite (text in, text out) and Write (a brief in, text out).
- Seven lanes in [lanes.md](lanes.md): Ear, Book, Song, Chat, Docs, Post, Brief.
- The pipeline pass return mode: one pass over a set of files, taken as written.
- `scripts/factcheck.py`: numbers by value (digits and number words), quotes, inline code, links, names and the sentence-length band, before against after. Standard library Python.

## Not taken

- Getting past AI detectors. The upstream README says detectors still flag most of its output, and the 2026-10-19 test found the detectors failed their own control texts. SigmaHuman writes for human readers.
- The upstream plugin manifests (`.claude-plugin/`, `.cursor-plugin/`): the Sigmaskills installer and `npx skills` install this skill on every agent host.

## Upstream updates

The vendored copy is `upstream/humanizer-SKILL.md`; its commit and version are in `upstream/UPSTREAM.json`. `python scripts/upstream.py check` (offline, also run by `npm test`) proves patterns.md A-F equals it. `status` compares with GitHub; `sync [--ref <commit or tag>]` rewrites A-F, `LICENSE-humanizer.txt` and the version lines in SKILL.md, patterns.md and this file, then lists what upstream changed in its method, voice and "when not to act" sections, which our SKILL.md folds in by hand. Our layer (lanes, section G, the write mode, `factcheck.py`) is never overwritten.
