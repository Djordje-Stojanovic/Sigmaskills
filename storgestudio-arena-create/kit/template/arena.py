"""The ranking engine of a blind-pairs arena (pure stdlib). Read ../../references/arena-guide.md for the why of every rule.

Bradley-Terry (the model behind LMArena's Elo board), fitted by the MM algorithm on pair counts:
  - a tie ("same") or "both bad" = half a win for each side
  - PRIOR: each player also drew once against an average player, so one lucky win cannot rule
  - bootstrap ranges (resampled picks) say how sure a rating is; overlapping ranges = not settled
  - one rating per player: the takes of one player (seeds, versions) pool into one player
  - one board per metric (only the picks that answered that metric) + Overall (weighted mean of the answered metrics)
Pairs are drawn LMArena-style: same group only, most informative first, never the same pair over and over.
"""
import json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
SCALE = 400 / math.log(10)  # Elo points: +400 = 10:1 odds, +100 = 64 %
AXIS = {"a": 1.0, "b": 0.0, "same": 0.5}


def load(name, default=None):
    try:
        with open(os.path.join(HERE, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(name, obj):
    tmp = os.path.join(HERE, name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False))
    os.replace(tmp, os.path.join(HERE, name))


def cfg():
    c = load("arena.json", {}) or {}
    c.setdefault("metrics", [{"id": "overall", "label": "Overall"}])
    c.setdefault("groups", {})
    c.setdefault("items", [])
    s = c.setdefault("settings", {})
    for k, v in {"prior": 1.0, "bootstrap": 100, "repeat_every": 14, "out_after_losses": 3, "top_k": 5, "min_games": 6}.items():
        s.setdefault(k, v)
    return c


def picks():
    """picks.jsonl: one JSON line per pick (append-only, survives a crash). Undone picks carry "undone": true."""
    out = []
    try:
        with open(os.path.join(HERE, "picks.jsonl"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except FileNotFoundError:
        pass
    undone = {p["undo"] for p in out if "undo" in p}
    return [p for p in out if "undo" not in p and p.get("id") not in undone]


def score(p, metric, weights):
    """Score for side a of one pick: one metric, or the weighted mean of every answered metric (None = not judged)."""
    ans = p.get("answers") or {}
    if p.get("bad"):
        return 0.5
    if metric != "__overall__":
        return AXIS.get(ans.get(metric))
    xs = [(AXIS[v], weights.get(m, 1.0)) for m, v in ans.items() if v in AXIS]
    return sum(v * w for v, w in xs) / sum(w for _, w in xs) if xs else None


def fit(games, players, prior):
    """games: list of (i, j, s) with s = score of i. Returns log-strengths (mean 0). MM algorithm with a prior draw."""
    k = len(players)
    if not k:
        return []
    W = [prior * 0.5] * k  # prior: half a win vs the average player (gamma 1)
    N = {}
    for i, j, s in games:
        W[i] += s; W[j] += 1 - s
        key = (i, j) if i < j else (j, i)
        N[key] = N.get(key, 0) + 1
    g = [1.0] * k
    for _ in range(200):
        den = [prior / (g[i] + 1.0) for i in range(k)]
        for (i, j), n in N.items():
            d = n / (g[i] + g[j]); den[i] += d; den[j] += d
        new = [max(W[i], 1e-6) / den[i] for i in range(k)]
        gm = math.exp(sum(math.log(x) for x in new) / k)
        new = [x / gm for x in new]
        if max(abs(math.log(new[i] / g[i])) for i in range(k)) < 1e-6:
            g = new; break
        g = new
    return [math.log(x) for x in g]


def board(c, ps, metric, rng=None, B=None):
    """One leaderboard: rows sorted by rating with lo/hi (95 % bootstrap), games, W-L-T, out flag."""
    rng = rng or random.Random(7)
    items = {it["id"]: it for it in c["items"]}
    weights = {m["id"]: float(m.get("weight", 1)) for m in c["metrics"]}
    players = sorted({it["player"] for it in c["items"]})
    idx = {p: i for i, p in enumerate(players)}
    games, wlt = [], {p: [0, 0, 0] for p in players}
    for p in ps:
        a, b = items.get(p.get("a")), items.get(p.get("b"))
        s = score(p, metric, weights)
        if not a or not b or s is None or a["player"] == b["player"]:
            continue
        games.append((idx[a["player"]], idx[b["player"]], s))
        ra, rb = wlt[a["player"]], wlt[b["player"]]
        if s > 0.5: ra[0] += 1; rb[1] += 1
        elif s < 0.5: ra[1] += 1; rb[0] += 1
        else: ra[2] += 1; rb[2] += 1
    prior = c["settings"]["prior"]
    th = fit(games, players, prior)
    boots = [[] for _ in players]
    if games:
        for _ in range(int(B if B is not None else c["settings"]["bootstrap"])):
            t = fit([games[rng.randrange(len(games))] for _ in games], players, prior)
            for i, v in enumerate(t):
                boots[i].append(v)
    rows = []
    for p, i in idx.items():
        bs = sorted(boots[i]) or [th[i]]
        lo, hi = bs[int(0.025 * (len(bs) - 1))], bs[int(0.975 * (len(bs) - 1))]
        w, l, t = wlt[p]
        rows.append({"player": p, "rating": round(1000 + SCALE * th[i]), "lo": round(1000 + SCALE * lo), "hi": round(1000 + SCALE * hi),
                     "games": w + l + t, "w": w, "l": l, "t": t})
    rows.sort(key=lambda r: -r["rating"])
    s = c["settings"]
    kth = rows[min(s["top_k"], len(rows)) - 1]["lo"] if rows else 0
    for r in rows:  # out: never won after N losses, or clearly below the top K (its best case under the K-th's worst case)
        r["out"] = bool((r["w"] == 0 and r["t"] == 0 and r["l"] >= s["out_after_losses"])
                        or (r["games"] >= s["min_games"] and r["hi"] < kth and rows.index(r) >= s["top_k"]))
    return rows


def meta_of(c):
    """Per player: label + the mean of every numeric meta field (seconds, GiB, cost...) over its items."""
    out = {}
    for it in c["items"]:
        m = out.setdefault(it["player"], {"label": (c.get("players") or {}).get(it["player"], it["player"]), "_n": {}})
        for k, v in (it.get("meta") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                acc = m["_n"].setdefault(k, [])
                acc.append(v)
    for m in out.values():
        for k, vs in m.pop("_n").items():
            m[k] = round(sorted(vs)[len(vs) // 2], 1)  # median
    return out


def agreement(ps):
    """Consistency checks: a decisive pair shown again with sides swapped. Rate = same verdict."""
    by = {p["id"]: p for p in ps}
    n = same = 0
    for p in ps:
        o = by.get(p.get("repeat_of"))
        if not o:
            continue
        v0, v1 = verdict(o), verdict(p)
        if v0 and v1:
            n += 1; same += v0 == v1
    return {"checks": n, "rate": round(same / n, 2) if n else None}


def verdict(p):
    """The winning item id of a pick (main metric, else overall), None for a tie."""
    ans = p.get("answers") or {}
    vals = [v for v in ans.values() if v in ("a", "b")]
    if not vals or p.get("bad"):
        return None
    a = vals.count("a"); b = vals.count("b")
    return p["a"] if a > b else p["b"] if b > a else None


def state(c=None, ps=None):
    c = c or cfg(); ps = picks() if ps is None else ps
    boards = {"__overall__": board(c, ps, "__overall__")}
    if len(c["metrics"]) > 1:
        for m in c["metrics"]:
            boards[m["id"]] = board(c, ps, m["id"])
    out = {"title": c.get("title", "Arena"), "picks": len(ps), "agreement": agreement(ps), "boards": boards, "meta": meta_of(c),
           "metrics": [{"id": m["id"], "label": m.get("label", m["id"])} for m in c["metrics"]]}
    save("results.json", out)
    save("results.md", markdown(out))
    return out


def markdown(st):
    meta = st["meta"]
    keys = sorted({k for m in meta.values() for k in m if k != "label"})
    L = [f"# {st['title']}: results", "", f"{st['picks']} picks. Consistency: {st['agreement']['rate'] if st['agreement']['rate'] is not None else '-'}"
         f" over {st['agreement']['checks']} repeat checks. Ratings are Elo points (1000 = average, +100 = wins 64 %); "
         "overlapping ranges = not settled yet.", ""]
    for bid, rows in st["boards"].items():
        name = "Overall" if bid == "__overall__" else next((m["label"] for m in st["metrics"] if m["id"] == bid), bid)
        L += [f"## {name}", "", "| # | Player | Rating | Range | Games | W-L-T | " + " | ".join(keys) + (" |" if keys else "") + " Out |",
              "|---|---|---|---|---|---|" + "---|" * len(keys) + "---|"]
        for i, r in enumerate(rows, 1):
            m = meta.get(r["player"], {})
            L.append(f"| {i} | {m.get('label', r['player'])} | {r['rating']} | {r['lo']}–{r['hi']} | {r['games']} | {r['w']}-{r['l']}-{r['t']} | "
                     + " | ".join(str(m.get(k, "")) for k in keys) + (" | " if keys else "") + ("out" if r["out"] else "") + " |")
        L.append("")
    return "\n".join(L)


def next_pair(c=None, ps=None, rng=random):
    """The next blind pair. 1 in `repeat_every` picks is a consistency check (an old decisive pair, sides swapped)."""
    c = c or cfg(); ps = picks() if ps is None else ps
    s = c["settings"]
    reps = [i for i, p in enumerate(ps) if p.get("repeat_of")]
    since = len(ps) - 1 - (reps[-1] if reps else -1)
    done = {p.get("repeat_of") for p in ps}
    cand = [p for p in ps if verdict(p) and not p.get("repeat_of") and p["id"] not in done]
    if cand and len(ps) >= 6 and since >= s["repeat_every"]:
        o = rng.choice(cand)
        left = o["b"] if o.get("left", o["a"]) == o["a"] else o["a"]
        return {"a": o["a"], "b": o["b"], "left": left, "repeat_of": o["id"], "why": "Consistency check: a pair you judged before, sides swapped."}
    rows = {r["player"]: r for r in board(c, ps, "__overall__", random.Random(1), B=40)}  # 40 resamples: fast enough per pick
    retired = {g for g, v in c["groups"].items() if v.get("retired")}
    skip = c.get("skip") or {}
    by = {}
    for it in c["items"]:
        if it.get("group") in retired or it["player"] in skip.get(it.get("group"), []):
            continue
        by.setdefault(it.get("group"), {}).setdefault(it["player"], []).append(it)
    items = {it["id"]: it for it in c["items"]}
    met, seen, recent = {}, {}, set()
    for p in ps:
        a, b = items.get(p["a"]), items.get(p["b"])
        if not a or not b:
            continue
        k = (a.get("group"), *sorted((a["player"], b["player"])))
        met[k] = met.get(k, 0) + 1
        seen[p["a"]] = seen.get(p["a"], 0) + 1; seen[p["b"]] = seen.get(p["b"], 0) + 1
    for p in ps[-3:]:
        for x in (p["a"], p["b"]):
            if x in items:
                recent.add(items[x]["player"])
    top = {r["player"] for r in sorted(rows.values(), key=lambda r: -r["lo"])[: s["top_k"]]}
    cands = []
    for g, pl in by.items():
        names = sorted(pl)
        for x in range(len(names)):
            for y in range(x + 1, len(names)):
                p1, p2 = names[x], names[y]
                r1, r2 = rows[p1], rows[p2]
                if r1["out"] or r2["out"]:
                    continue  # clearly not in the top K: no more pairs
                pw = 1 / (1 + 10 ** ((r2["rating"] - r1["rating"]) / 400))
                u = lambda r: max(0.15, (r["hi"] - r["lo"]) / 400) / math.sqrt(1 + r["games"] / 4)
                n = met.get((g, p1, p2), 0)
                v = (0.25 + pw * (1 - pw)) * (u(r1) + u(r2)) / (1 + n) ** 1.5
                if n >= 3:
                    v *= 0.05  # met 3+ times: nearly retired
                if p1 in recent or p2 in recent:
                    v *= 0.4
                few1, few2 = r1["games"] < 4, r2["games"] < 4
                if few1 or few2:
                    v *= 4  # every newcomer gets its first games fast, new-vs-new as often as new-vs-leader
                elif p1 in top and p2 in top:
                    v *= 1.5  # the top decides the defaults
                cands.append((v, g, p1, p2))
    if not cands:
        return {"error": "No pair left: every group has fewer than 2 live players. The ranking is done (or add items)."}
    cands.sort(key=lambda t: -t[0])
    pool = cands[:12]
    _, g, p1, p2 = rng.choices(pool, weights=[t[0] ** 2 for t in pool])[0]
    pick_item = lambda p: min(by[g][p], key=lambda it: (seen.get(it["id"], 0), rng.random()))  # least-shown take first
    a, b = pick_item(p1), pick_item(p2)
    left = rng.choice([a["id"], b["id"]])
    return {"a": a["id"], "b": b["id"], "left": left, "repeat_of": None, "why": f"Group {g}: these two are close or still unsure."}
