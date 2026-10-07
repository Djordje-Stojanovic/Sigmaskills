"""Self-test of the ranking engine: a simulated judge with known true strengths and 65 % consistency
(the usual rate of a human judge). Passes when the engine finds the true #1 and the true order has a high rank correlation.

  python selftest.py          (writes nothing next to the arena: it works in a temp copy)
"""
import json, os, random, shutil, sys, tempfile

SRC = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp(prefix="arena-selftest-")
for f in ("arena.py",):
    shutil.copy(os.path.join(SRC, f), tmp)
sys.path.insert(0, tmp)
import arena  # noqa: E402  (the copy in tmp: HERE points there)

rng = random.Random(42)
true = {f"p{i}": 1000 + 60 * (7 - i) for i in range(8)}  # p0 best ... p7 worst, 60 Elo apart
items = [{"id": f"{p}__g{g}__{t}", "player": p, "group": f"g{g}", "text": "x"} for p in true for g in range(3) for t in range(2)]
cfg = {"title": "selftest", "metrics": [{"id": "look", "label": "Look"}, {"id": "fit", "label": "Fit", "weight": 2}],
       "groups": {f"g{g}": {"label": f"g{g}"} for g in range(3)}, "items": items,
       "settings": {"prior": 1.0, "bootstrap": 60, "repeat_every": 14, "out_after_losses": 3, "top_k": 3, "min_games": 6}}
arena.save("arena.json", cfg)
by = {i["id"]: i for i in items}
ps = []
for n in range(220):
    c = arena.cfg()
    pr = arena.next_pair(c, ps, rng)
    a, b = pr["left"], pr["b"] if pr["left"] == pr["a"] else pr["a"]
    d = true[by[a]["player"]] - true[by[b]["player"]]
    pa = 1 / (1 + 10 ** (-d / 400))
    ans = {}
    for m in ("look", "fit"):
        r = rng.random()
        ans[m] = "same" if abs(d) < 30 and r < 0.3 else ("a" if rng.random() < pa else "b")
    rec = {"id": f"k{n}", "a": a, "b": b, "left": a, "answers": ans}
    if pr.get("repeat_of"):
        rec["repeat_of"] = pr["repeat_of"]
    ps.append(rec)
st = arena.state(arena.cfg(), ps)
rows = st["boards"]["__overall__"]
order = [r["player"] for r in rows]
rank = {p: i for i, p in enumerate(order)}
n = len(order)
rho = 1 - 6 * sum((rank[p] - int(p[1:])) ** 2 for p in order) / (n * (n * n - 1))
reps = sum(1 for p in ps if p.get("repeat_of"))
games = {r["player"]: r["games"] for r in rows}
print("order:", " > ".join(f"{r['player']}({r['rating']} {r['lo']}-{r['hi']}{' out' if r['out'] else ''})" for r in rows))
print(f"spearman {rho:.2f}, consistency checks {reps}, agreement {st['agreement']}, games min/max {min(games.values())}/{max(games.values())}")
ok = order[0] in ("p0", "p1") and rho >= 0.8 and reps >= 8  # the top two are 60 Elo apart: either may lead
shutil.rmtree(tmp, ignore_errors=True)
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
