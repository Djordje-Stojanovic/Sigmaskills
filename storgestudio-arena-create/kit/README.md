# Arena kit

A blind-pairs ranking page for anything: models, settings, captions, thumbnails, voices, outfits. The full guide (rules, why, lessons) is [`../references/arena-guide.md`](../references/arena-guide.md); the skill is `storgestudio-arena-create`.

```powershell
# 1. copy the template into the project (never edit the template for one project)
Copy-Item -Recurse <skill>\kit\template <project>\arena
cd <project>\arena; Remove-Item picks.jsonl, codes.json, results.* -ErrorAction SilentlyContinue
# 2. items: media/<player>__<group>[__<take>].<ext> (+ .json sidecar), or a TSV: player<TAB>group<TAB>text
python make_items.py media\        # or: python make_items.py options.tsv
# 3. edit arena.json: title, question, metrics, groups (prompt text), players (labels), skip, settings
python selftest.py                 # engine check, ~5 s, PASS
python server.py --open            # first free port 3410-3499
```

| File | What |
|---|---|
| `template/arena.py` | Ranking engine: Bradley-Terry + bootstrap, per-metric boards, pair picker, consistency checks, out rule |
| `template/server.py` | Stdlib server: blind codes, media with Range, picks.jsonl, undo, results.md |
| `template/index.html` | The page: rank, board, keys; image, video, audio, text and HTML options |
| `template/make_items.py` | Fills `arena.json` items from a folder or a text list |
| `template/selftest.py` | Simulated judge (65 % consistent): the engine must find the true order |
| `template/arena.json` | Example: a 6-style caption arena with 3 metrics (runs as is) |
| `screenshots/` | How it looks: `image-board.png`, `caption-rank.png` |
