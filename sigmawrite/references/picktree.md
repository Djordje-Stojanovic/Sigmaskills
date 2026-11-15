# Pick tree

A pick tree lets the owner decide over many nested things that have a size or a count: disks, models, projects, files to delete. He opens the rows he cares about. He picks a choice for a row and can add a word to it. His picks come back as plain lines. A pick tree deletes nothing. You act on his picks afterwards.

## The data

One JSON file:

    {"title": "Models on the Spark", "fmt": "bytes", "root": "/home/me/models", "total": 64424509440,
     "choices": ["keep", "delete"], "rest": "files under 1 GB each",
     "rows": [{"n": "llama/", "s": 42949672960, "rec": "keep",
               "k": [{"n": "q4.gguf", "s": 21474836480, "c": {"used by": "chat lane", "last read": "2 days ago"}}]},
              {"n": "old-tts/", "s": 21474836480, "rec": "delete", "c": {"used by": "NOTHING NAMES IT"}}]}

- `title`: the page title. The picks he makes in his browser are saved under this title. Give each tree its own title.
- `root`: the folder the top rows sit in. A row's full path is `root` plus the names down to that row.
- `choices`: the words he picks from, for example `keep` and `delete`.
- `rows`: the top rows. Each row has:
  - `n`: the name. A folder name ends with `/`. Two rows in one folder need different names.
  - `s`: the size, in bytes when `fmt` is `"bytes"`, or a count.
  - `k`: the rows inside a folder. Leave it out for a file.
  - `c`: short columns, as label and text, shown under the name (for example `"used by"`).
  - `rec`: your pick, one of `choices`. The page shows it as "my pick". Leave it out where he decides alone.
- `fmt`: `"bytes"` (the default) shows sizes as GB. Any other value shows the count, with `unit` after it: `"fmt": "count", "unit": "files"`.
- `total`: the size of the whole tree. The top rows show their share of it.
- `rest`: the name of the last row that a folder gets when its rows do not add up to its size. The row appears only when the gap is 0.05 GB or more (1 or more for a count).
- `note` (optional): one line under the title.
- Sort each level largest first. The page keeps your order.

When any row has a `rec`, the page shows a "Take my picks" button. He presses it to take all of your picks at once.

## Show it on his review page

Where his review page runs (a run folder with `cards/` and `media/`; on the dev box, `/work/temp/ultraplan2`), one command adds a tree entry:

    python3 <skill>/scripts/picktree.py tree.json --review /work/temp/ultraplan2 --id DISK-MODELS --title "Models on the Spark" --body "<p>Measured today.</p>" --project Homelab

- `--id` names the entry. Use letters, digits, dot, dash or underscore, up to 80 characters. It is also a file name.
- `--body` is HTML. It shows above the tree.
- `--project` is a project name on the page, for example `Homelab`.

The review page rebuilds when its cards change. Give him the page link with `#DISK-MODELS` at the end.

His picks go to `/work/temp/ultraplan2/answers/DISK-MODELS.json`. The `pick` field holds the same lines as the copied text below, without the header. A comment on the whole tree goes to `comment`.

## Anywhere else

One self-contained HTML file. It needs no server and no network:

    python3 <skill>/scripts/picktree.py tree.json -o picks.html

He opens it, picks, and presses Copy my picks. If the browser blocks the clipboard, the page shows the text in a box for him to copy by hand. He pastes back:

    PICKTREE REPLY: Models on the Spark
    delete: /home/me/models/old-tts (20 GB) “too big”
    General: keep everything else until Friday

Each line reads `<choice>: <full path> (<size>) “<his word>”`. A row with only a word says `note:`. The `General:` line holds his comment on the whole tree. Act on each line exactly as written.
