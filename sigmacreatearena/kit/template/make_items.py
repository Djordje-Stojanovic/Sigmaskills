"""Fill arena.json "items" from a media folder or a text list. Keeps title, metrics, groups and settings.

Media folder: one file per item, named  <player>__<group>[__<take>].<ext>   e.g.  q-int8__P3__s43.png
  - player = the option being ranked (a model, a setup, a caption writer, an outfit); its takes pool into one rating
  - group  = what the options answer (a prompt, a scene, a script line); pairs only meet inside one group
  - a sidecar <same name>.json is copied into "meta" (numbers like seconds, peak_gib, cost show on the board)
Text list (.tsv or .jsonl):  player <TAB> group <TAB> text   or  {"player":..,"group":..,"text":..,"meta":{..}}

  python make_items.py media/            scan a folder (relative paths kept, so the arena folder stays portable)
  python make_items.py options.tsv       text items (captions, titles, hooks, lines)
  python make_items.py media/ --append   add to the existing items instead of replacing them
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".mp4", ".webm", ".mov", ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".html", ".txt", ".md"}


def from_folder(d):
    out = []
    for root, _, files in os.walk(d):
        for f in sorted(files):
            stem, ext = os.path.splitext(f)
            if ext.lower() not in MEDIA:
                continue
            parts = stem.split("__")
            if len(parts) < 2:
                print(f"skip {f}: name it <player>__<group>[__<take>]{ext}"); continue
            path = os.path.relpath(os.path.join(root, f), HERE).replace("\\", "/")
            it = {"id": stem, "player": parts[0], "group": parts[1], "src": path}
            side = os.path.join(root, stem + ".json")
            if os.path.isfile(side):
                try:
                    it["meta"] = json.load(open(side, encoding="utf-8"))
                except Exception as e:
                    print(f"sidecar {side} unreadable: {e}")
            out.append(it)
    return out


def from_list(p):
    out = []
    with open(p, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            if p.endswith(".jsonl"):
                r = json.loads(line)
            else:
                pl, g, *t = line.split("\t")
                r = {"player": pl, "group": g, "text": "\t".join(t).replace("\\n", "\n")}
            r.setdefault("id", f"{r['player']}__{r['group']}__{n}")
            out.append(r)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    new = from_folder(src) if os.path.isdir(src) else from_list(src)
    cp = os.path.join(HERE, "arena.json")
    c = json.load(open(cp, encoding="utf-8")) if os.path.isfile(cp) else {"title": "Arena", "metrics": [{"id": "overall", "label": "Overall"}], "groups": {}}
    items = (c.get("items") or []) + new if "--append" in sys.argv else new
    seen = set(); items = [i for i in items if not (i["id"] in seen or seen.add(i["id"]))]
    c["items"] = items
    for g in sorted({i["group"] for i in items}):
        c.setdefault("groups", {}).setdefault(g, {"label": g, "prompt": ""})
    groups = {}
    for i in items:
        groups.setdefault(i["group"], set()).add(i["player"])
    json.dump(c, open(cp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{len(items)} items, {len({i['player'] for i in items})} players, {len(groups)} groups -> arena.json")
    for g, ps in sorted(groups.items()):
        if len(ps) < 2:
            print(f"WARN group {g}: only {len(ps)} player, it can never make a pair")
