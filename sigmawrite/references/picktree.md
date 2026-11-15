# Pick tree

A pick tree puts a decision over many nested things with a size or a count in front of the owner: disks, models, projects, files to delete. He opens the rows he cares about, picks one choice per row, adds a word where he wants, and his picks come back as plain lines. A tree carries no deletion: you act on his picks afterwards.

## The data

One JSON file:

    {"title": "Models on the Spark", "fmt": "bytes", "root": "/home/me/models", "total": 64424509440,
     "choices": ["keep", "delete"], "rest": "files under 1 GB each",
     "rows": [{"n": "llama/", "s": 42949672960, "rec": "keep",
               "k": [{"n": "q4.gguf", "s": 21474836480, "c": {"used by": "chat lane", "last read": "2 days ago"}}]},
              {"n": "old-tts/", "s": 21474836480, "rec": "delete", "c": {"used by": "NOTHING NAMES IT"}}]}

- A row: `n` name, `s` size, `k` its rows, `c` short columns, `rec` your pick (one of `choices`, shown as "my pick"). Leave `rec` out where he decides alone.
- `fmt`: `"bytes"` shows sizes as GB; any other value shows the number with `unit` (`"fmt": "count", "unit": "files"`).
- `total` is the size of the whole tree, for the share bars of the top rows.
- A folder's rows need not add up to it: the page adds a last row, named by `rest`, for the part they leave out.
- Sort each level largest first; the page keeps your order.

## Show it

Where his review page runs (a run folder with `cards/` and `media/` that the page build reads; on the dev box `/work/temp/ultraplan2`), one command makes it an entry:

    python3 <skill>/scripts/picktree.py tree.json --review /work/temp/ultraplan2 --id DISK-MODELS --title "Models on the Spark" --body "<p>Measured today. Your target: 183 GB free.</p>" --project Homelab

The page rebuilds within a minute. Give him the page's link with `#DISK-MODELS` at the end. His picks land in `/work/temp/ultraplan2/answers/DISK-MODELS.json`, field `pick`.

Anywhere else, one self-contained HTML file (no server, no network), in the same look:

    python3 <skill>/scripts/picktree.py tree.json -o picks.html

He opens it, picks, and presses Copy my picks. He pastes back:

    PICKTREE REPLY: Models on the Spark
    delete: /home/me/models/old-tts (20 GB) “too big”
    General: keep everything else until Friday

Each line is `<choice>: <full path> (<size>) “<his word>”`; a row with only a word says `note:`. Act on each line exactly as written.
