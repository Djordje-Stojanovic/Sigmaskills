# Arena kit

A blind-pairs ranking page for anything: models, settings, captions, thumbnails, voices, outfits. The full guide (rules, why, lessons) is [`../references/arena-guide.md`](../references/arena-guide.md); the skill is `storgestudio-arena-create`.

```powershell
# 1. copy the template into the project (never edit the template for one project)
Copy-Item -Recurse <skill>\kit\template <project>\arena
cd <project>\arena; Remove-Item picks.jsonl, codes.json, results.* -ErrorAction SilentlyContinue
# 2. items: media/<player>__<group>[__<take>].<ext> (+ .json sidecar), or a TSV: player<TAB>group<TAB>text
python make_items.py media\        # or: python make_items.py options.tsv
# 3. edit arena.json: title, question, metrics, groups (prompt text, refs), players (labels), anchors, skip, settings
python selftest.py                 # engine, anchors and refs check, ~20 s, PASS
python server.py --open            # first free port 3410-3499
```

| File | What |
|---|---|
| `template/arena.py` | Ranking engine: Bradley-Terry + bootstrap, per-metric boards, pair picker, consistency checks, out rule |
| `template/server.py` | Stdlib server: blind codes, media with Range, picks.jsonl, undo, results.md |
| `template/index.html` | The page: rank, board, keys; image, video, audio, text and HTML options; group refs |
| `template/make_items.py` | Fills `arena.json` items from a folder or a text list |
| `template/selftest.py` | Simulated judge (65 % consistent): the engine must find the true order; anchors and refs checks |
| `template/arena.json` | Example: a 6-style caption arena with 3 metrics (runs as is) |
| `screenshots/` | How it looks: `image-rank.png` (with refs; fictional example faces), `image-board.png`, `caption-rank.png` |

**Refs** (optional): a group's `"refs": ["refs/a.jpg", {"src": "refs/b.wav", "label": "voice"}]` shows reference media in the prompt bar. Click one = full size, `←`/`→` = next, `R` = all in a grid; `F`/`G` show them in a column beside the option. Without refs the page works as before.

**Anchors** (optional): `"anchors": ["gpt", "baseline"]` = reference players. They get a rating, but never a top-K place: the top-K boost and the "out" cut count non-anchors only. After `settings.anchor_games` games (default 8) their pairs get ×0.1 weight.

**Keys:** per metric row `Q W E`, `A S D`, `Y X C` (`Z X C` on QWERTY), `U I O`, `J K L` = A better · same · B better. The page reads the key position (`e.code`), so QWERTZ and QWERTY both work. Arrows do not vote. `↵` next, `B` both bad, `⌫` undo, `F`/`G` full size, `N` note. A metric with `"weight": 2` counts ×2 in Overall.
