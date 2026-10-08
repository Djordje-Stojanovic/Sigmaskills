"""Self-test of the ranking engine: a simulated judge with known true strengths and 65 % consistency
(the usual rate of a human judge). Passes when the engine finds the true #1 and the true order has a high rank correlation.
Also checks anchors (a reference player stronger than all candidates must not take a top place or soak up the picks)
and refs (a group's reference media reach the page as /g/<group>/<i> links with a kind and a label).

  python selftest.py          (writes nothing next to the arena: it works in a temp copy)
"""
import json, os, random, shutil, sys, tempfile

SRC = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp(prefix="arena-selftest-")
for f in ("arena.py", "server.py"):
    shutil.copy(os.path.join(SRC, f), tmp)
sys.path.insert(0, tmp)
import arena  # noqa: E402  (the copy in tmp: HERE points there)


def simulate(true, anchors=(), n_picks=220, seed=42):
    """A simulated judge on 3 groups x 2 takes per player. Returns (state, picks)."""
    rng = random.Random(seed)
    items = [{"id": f"{p}__g{g}__{t}", "player": p, "group": f"g{g}", "text": "x"} for p in true for g in range(3) for t in range(2)]
    cfg = {"title": "selftest", "metrics": [{"id": "look", "label": "Look"}, {"id": "fit", "label": "Fit", "weight": 2}],
           "groups": {f"g{g}": {"label": f"g{g}"} for g in range(3)}, "items": items, "anchors": list(anchors),
           "settings": {"prior": 1.0, "bootstrap": 60, "repeat_every": 14, "out_after_losses": 3, "top_k": 3, "min_games": 6}}
    arena.save("arena.json", cfg)
    by = {i["id"]: i for i in items}
    ps = []
    for n in range(n_picks):
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
    return arena.state(arena.cfg(), ps), ps


# 1. the ranking: 8 candidates, p0 best ... p7 worst, 60 Elo apart
true = {f"p{i}": 1000 + 60 * (7 - i) for i in range(8)}
st, ps = simulate(true)
rows = st["boards"]["__overall__"]
order = [r["player"] for r in rows]
rank = {p: i for i, p in enumerate(order)}
n = len(order)
rho = 1 - 6 * sum((rank[p] - int(p[1:])) ** 2 for p in order) / (n * (n * n - 1))
reps = sum(1 for p in ps if p.get("repeat_of"))
games = {r["player"]: r["games"] for r in rows}
print("order:", " > ".join(f"{r['player']}({r['rating']} {r['lo']}-{r['hi']}{' out' if r['out'] else ''})" for r in rows))
print(f"spearman {rho:.2f}, consistency checks {reps}, agreement {st['agreement']}, games min/max {min(games.values())}/{max(games.values())}")
ok_rank = order[0] in ("p0", "p1") and rho >= 0.8 and reps >= 8  # the top two are 60 Elo apart: either may lead
print("ranking:", "PASS" if ok_rank else "FAIL")

# 2. anchors: a reference player 200 Elo above every candidate. It keeps a rating, but takes no top-K place
#    (no top candidate is cut as "out" because of it) and, once it has `anchor_games` games, gets far fewer picks
#    than the same player gets when it is not an anchor.
true2 = dict(true, ref=1000 + 60 * 7 + 200)
plain, _ = simulate(true2)
st2, ps2 = simulate(true2, anchors=["ref"])
rows2 = st2["boards"]["__overall__"]
g_plain = {r["player"]: r["games"] for r in plain["boards"]["__overall__"]}["ref"]
g2 = {r["player"]: r["games"] for r in rows2}
cand = [r for r in rows2 if r["player"] != "ref"]
ref_row = next(r for r in rows2 if r["player"] == "ref")
top3_out = [r["player"] for r in cand[:3] if r["out"]]
print(f"anchor: rating {ref_row['rating']} (#{[r['player'] for r in rows2].index('ref') + 1}), games {g2['ref']} "
      f"(as a normal player {g_plain}), top-3 candidates {[r['player'] for r in cand[:3]]}, out among them {top3_out}")
ok_anchor = (ref_row["rating"] > cand[0]["rating"] and g2["ref"] >= 8 and g2["ref"] <= 0.75 * g_plain and not top3_out
             and cand[0]["player"] in ("p0", "p1"))
print("anchors:", "PASS" if ok_anchor else "FAIL")

# 3. refs: a group's reference media (string or {src, label}) become blind-safe /g/ links; no refs = empty list
import server  # noqa: E402  (the copy in tmp)
rs = server.public_refs("g 1", {"refs": ["refs/a.jpg", {"src": "refs/b.wav", "label": "Voice"}]})
ok_refs = (rs == [{"url": "/g/g%201/0", "label": "", "kind": "image"}, {"url": "/g/g%201/1", "label": "Voice", "kind": "audio"}]
           and server.public_refs("g0", {}) == [])
print("refs:", "PASS" if ok_refs else "FAIL", rs)

ok = ok_rank and ok_anchor and ok_refs
shutil.rmtree(tmp, ignore_errors=True)
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
