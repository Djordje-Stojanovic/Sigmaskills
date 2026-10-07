---
name: storgestudio-arena-create
description: Builds a fast blind-pairs arena so the user ranks any options by Elo per metric: models, settings, voices, captions, thumbnails, outfits. Grills first, then ships a local page and a board. Use to rank, compare or pick the best of many options by taste. Do not use for 2-3 options (just ask), for measurable checks (script them), or to judge one draft against a reference.
---

# Arena Create

An arena shows the user two options side by side, names hidden, sides random. They pick per metric. A Bradley-Terry fit turns the picks into an Elo board per metric. This skill grills the user, builds the arena from a bundled kit, hands over the link, and reads the board back.

Read [`references/arena-guide.md`](references/arena-guide.md) before step 1: every ranking rule, why it exists, and 14 lessons. The code is the kit in [`kit/`](kit/README.md). Copy it; never rewrite it. Screenshots of the finished look are in `kit/screenshots/`.

Needs Python 3 (standard library only) and a browser. The server listens on 127.0.0.1 only.

## 1. Grill (before anything is made)

Run a grilling round: numbered questions, your recommended answer under each (use `/grilling` if it is installed). Look up every fact yourself; only decisions go to the user. Cover, in order:

1. **What is ranked, and what happens to the winner?** (a new default, a caption, a model kept, files deleted.) One sentence each.
2. **The players:** which options, and where each comes from (the user, research with links, your own idea: say which). Recommend 6-12, at most 20. Keep today's default as a baseline, plus a strong outside reference if one exists.
3. **The groups:** what the options answer (prompts, scenes, briefs, script lines). Recommend 3-6 hard ones that can fail (names, lettering, dates, specific details), at least one written by the user.
4. **Takes per player:** 1 for fixed text, 2-3 where chance plays a role (seeds, voice takes).
5. **The metrics:** recommend 1-4 for the job (table below). One main metric may carry weight 2. The user may answer only some per pick.
6. **Skips and limits:** an option that cannot do a group (a cloud model that refuses) sits it out with no loss. Time and cost budget.
7. **Cost columns:** what to measure per item (seconds, GiB, money, words) for the board.

| Job | Metrics that worked |
|---|---|
| Image models | Picture, Prompt (weight 2), Text, Likeness or Style |
| Video models | Picture, Motion, Sound, Prompt (weight 2) |
| Voices (TTS) | Natural, Likeness to the reference, Pronunciation, Emotion |
| Captions, titles, hooks | Click (weight 2), Clear in 1 s, On brand |
| Thumbnails | Click, Readable when small, On brand |
| Outfits, logos, looks | Overall, Fits the brief |

Stop when no open question is left and the user confirms. Write the decisions into the project notes (or the ticket) under `## Arena`.

## 2. Build

1. Make a folder inside the project (for example `arena/`). Copy `kit/template/` there. Delete `picks.jsonl`, `codes.json` and `results.*` if present.
2. Make the options (render, write, generate, collect). Name each file `<player>__<group>[__<take>].<ext>` in `media/`, with a same-name `.json` sidecar holding the cost numbers. Text options go in `options.tsv` (`player<TAB>group<TAB>text`). Group long renders by model file.
3. Run `python make_items.py media/` (or `options.tsv`). Edit `arena.json`: `title`, `question`, `metrics` (`id`, `label`, `hint`, `weight`), `groups` (`label`, `prompt`: the exact text the options answer), `players` (plain labels, shown only on the board), `skip`, `settings.top_k` (how many places the user cares about).
4. Run `python selftest.py` (must print PASS), then `python server.py --open` (first free port 3410-3499; `--port N` fixes one). Open the page yourself: every item loads, the sides look equal, the keys work.

## 3. Hand over and watch

Tell the user in one short message: the link, how many options and groups, the keys (`← ↓ →`, `Q W E`, `A S D`, `Z X C`: A better, same, B better; `↵` next, `B` both bad, `⌫` undo, `F`/`G` full size), and "you decide when it is enough". While they rank, answer questions from `results.md` with tables: Elo, range, games, W-L-T, the cost columns, per metric. Say "tie" where ranges overlap. Never pick for the user, never edit `picks.jsonl`, never restart a server you did not start.

## 4. Close

When the user says enough: the winners go where step 1 said, the losing files are deleted with the user's yes, and each new lesson goes into the project notes. The arena folder stays as the evidence.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
