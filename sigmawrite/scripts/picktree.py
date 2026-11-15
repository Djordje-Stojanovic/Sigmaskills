#!/usr/bin/env python3
"""A pick tree: the owner decides over many nested things with a size or a count, row by row. Reference: ../references/picktree.md.

  picktree.py TREE.json [-o OUT.html]                          one self-contained page (no server, no network) with Copy my picks
  picktree.py TREE.json --review ROOT --id ID [--title T] [--body HTML] [--project P]
                                                               an entry on a review page: ROOT/cards/ID.json and ROOT/media/ID/tree.json

Standard library only. Files are written to a .tmp name and renamed, so a reader never sees half a file.
"""
import argparse, html, json, os, re, sys

def put(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f: f.write(text)
    os.replace(path + ".tmp", path)

def fail(msg): sys.exit("picktree: " + msg)

def check(t):
    """The shape every reader expects: one plain line when it is wrong (asserts vanish under python -O)."""
    if not (isinstance(t, dict) and isinstance(t.get("rows"), list)): fail("the tree is an object with a rows list")
    if not (isinstance(t.get("choices"), list) and t["choices"] and all(isinstance(c, str) for c in t["choices"])): fail('choices: a list of words, for example ["keep", "delete"]')
    for k in ("title", "note", "root", "unit", "rest", "fmt"):
        if k in t and not isinstance(t[k], str): fail(f"{k}: text, if there")
    if "total" in t and not isinstance(t["total"], (int, float)): fail("total: a number, if there")
    def rows(rs, where):
        for r in rs:
            if not (isinstance(r, dict) and isinstance(r.get("n"), str) and r["n"].strip("/\\ ") and isinstance(r.get("s"), (int, float)) and isinstance(r.get("k") or [], list)):
                fail(f"{where}: a row needs n (name) and s (size); k, if there, is a list")
            if r.get("rec") not in (None, *t["choices"]): fail(f"{where}/{r['n']}: rec must be one of the choices")
            rows(r.get("k") or [], where + "/" + r["n"])
        names = [r["n"].rstrip("/\\") for r in rs]   # "a/" and "a" make one path, so they clash too
        if len(set(names)) != len(names): fail(f"{where}: two rows share a name, so one pick would land on both")
    rows(t["rows"], "rows")
    return t

def page(t, title):
    js = lambda v: json.dumps(v, ensure_ascii=False).replace("<", "\\u003c")   # no "</script>" or "<!--" can end a script block
    note = f"<p class=lead>{html.escape(t['note'])}</p>" if t.get("note") else ""
    subs = {"TITLE": html.escape(title), "TITLEJS": js(title), "NOTE": note, "DATA": js(t)}
    return re.sub(r"__(TITLEJS|TITLE|NOTE|DATA)__", lambda m: subs[m.group(1)], PAGE)   # one pass: a title that holds "__DATA__" stays text

def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("tree"); a.add_argument("-o", "--out"); a.add_argument("--title"); a.add_argument("--review"); a.add_argument("--id")
    a.add_argument("--body", default=""); a.add_argument("--project", default="")
    o = a.parse_args()
    try:
        with open(o.tree, encoding="utf-8") as f: t = check(json.load(f))
    except (OSError, ValueError) as e: sys.exit(f"picktree: {o.tree} is not a readable tree: {e}")
    title = o.title or t.get("title") or os.path.splitext(os.path.basename(o.tree))[0]
    if o.review:
        # the same rule as answers.py, or the answer box refuses the entry; the id is also a file name
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", o.id or ""): sys.exit("picktree: --review needs --id: letters, digits, dot, dash or underscore, up to 80 characters")
        if not os.path.isdir(o.review): sys.exit(f"picktree: --review {o.review} is not a folder: give the review page's run folder")
        put(os.path.join(o.review, "media", o.id, "tree.json"), json.dumps(t, ensure_ascii=False))
        put(os.path.join(o.review, "cards", o.id + ".json"), json.dumps({"id": o.id, "kind": "tree", "title": title, "body": o.body or (t.get("note") and f"<p>{html.escape(t['note'])}</p>") or "",
                                                                         "tree": "tree.json", "project": o.project, "state": "open"}, ensure_ascii=False))
        print("entry", o.id, "written to", o.review); return
    out = o.out or os.path.splitext(o.tree)[0] + ".html"
    if os.path.abspath(out) == os.path.abspath(o.tree): sys.exit("picktree: the page would overwrite the tree file; give -o another name")
    put(out, page(t, title)); print("wrote", out)

PAGE = r"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--canvas:#fafafa;--surface:#fff;--surface-2:#f4f4f5;--line:#e4e4e7;--line-2:#d4d4d8;--ink:#18181b;--mute:#52525b;--acc:#047857;--on-acc:#ecfdf5;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--canvas:#09090b;--surface:#111113;--surface-2:#18181b;--line:#27272a;--line-2:#3f3f46;--ink:#f4f4f5;--mute:#a1a1aa;--acc:#34d399;--on-acc:#022c22;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--canvas);color:var(--ink);font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding:20px 16px 120px}h1{font-size:22px;font-weight:600;letter-spacing:-.01em;margin:0 0 4px;text-wrap:balance}.lead{color:var(--mute);margin:0 0 12px}
input,select,textarea,button{font:inherit;color:inherit}
.input{width:100%;min-height:44px;padding:0 12px;border:1px solid var(--line-2);border-radius:10px;background:var(--surface-2)}textarea.input{padding:10px 12px;min-height:72px}
.input:focus,select:focus,button:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.bar{display:flex;gap:8px;margin:0 0 8px}.btn{min-height:44px;padding:0 16px;border:1px solid var(--line);border-radius:10px;background:var(--surface);cursor:pointer;font-weight:500;white-space:nowrap}
.btn.go{background:var(--acc);color:var(--on-acc);border-color:transparent}
.tw{border-top:1px solid var(--line)}.tw>.empty{color:var(--mute);padding:12px 0}
.tr{position:relative;border-bottom:1px solid var(--line)}.tr:last-child{border-bottom:0}
.tr>details>summary{position:relative;display:grid;grid-template-columns:clamp(52px,14vw,76px) minmax(0,1fr);column-gap:10px;align-items:baseline;min-height:44px;padding:11px calc(clamp(96px,24vw,184px) + 8px) 11px 0;list-style:none;cursor:pointer}
.tr>details>summary::-webkit-details-marker{display:none}
.tr>details[data-k]>summary .tn::before{content:"▸ ";color:var(--mute)}.tr>details[data-k][open]>summary .tn::before{content:"▾ "}
.ts{text-align:right;font-weight:600;font-variant-numeric:tabular-nums;font-size:14px}.tn{overflow-wrap:anywhere;font-size:14px}
.trec{font-style:normal;font-weight:600;color:var(--acc);font-size:13px}.tc{grid-column:2;color:var(--mute);font-size:13px;line-height:1.4;margin-top:2px;overflow-wrap:anywhere}.tc span{display:inline-block;margin-right:12px}.tc b{font-weight:600}
.tsh{position:absolute;left:0;bottom:-1px;height:2px;background:var(--acc);opacity:.55}
.tp{position:absolute;right:0;top:4px;width:clamp(96px,24vw,184px);height:36px;padding:0 8px;border:1px solid var(--line-2);border-radius:10px;background:var(--surface-2);font-size:14px;font-weight:500}
@media (pointer:coarse),(max-width:640px){.tp{height:44px;top:0}}
.tk{margin-left:8px;padding:0 0 6px 10px;border-left:1px solid var(--line)}.tw-w{display:block;margin:4px 0 8px;min-height:44px}
.tr.rest .trow{display:grid;grid-template-columns:clamp(52px,14vw,76px) minmax(0,1fr);column-gap:10px;padding:10px 0;color:var(--mute);font-size:14px}
.send{position:sticky;bottom:0;display:flex;align-items:center;gap:12px;margin:16px -16px 0;padding:12px 16px;background:var(--canvas);border-top:1px solid var(--line)}#n{color:var(--mute);font-size:14px}
#out{display:none;margin-top:8px;min-height:140px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
<div class="wrap"><h1>__TITLE__</h1>__NOTE__
<div class="bar"><input type="search" class="input tq" placeholder="Search this tree" aria-label="Search this tree" autocomplete="off"><button type="button" class="btn tall" hidden>Take my picks</button></div>
<div class="tw"></div>
<textarea class="input" id="any" placeholder="A comment on the whole tree, if you have one" aria-label="A comment on the whole tree" style="margin-top:12px"></textarea>
<div class="send"><button type="button" class="btn go" id="copy">Copy my picks</button><span id="n" role="status"></span></div>
<textarea class="input" id="out" readonly aria-label="Your picks, to copy by hand"></textarea></div>
<script type="application/json" id="data">__DATA__</script>
<script>
"use strict";
/* the same tree as the review page's pick-tree entry: rows open (children drawn on the first open, a rest row so a folder adds up),
   a share bar, short columns, a pick per row, a word on a picked row, a search; the picks stay in this browser until Copy my picks */
(function () {
  const G = 2 ** 30, MAX = 150, TITLE = __TITLEJS__, KEY = "picktree:" + TITLE, $ = (s) => document.querySelector(s);
  const data = JSON.parse($("#data").textContent); data.fmt = data.fmt || "bytes";
  const t = { data, choices: data.choices, picks: {}, q: "" };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const fmt = (v) => data.fmt === "bytes" ? (v >= 10 * G ? Math.round(v / G).toLocaleString("en") + " GB" : (v / G).toFixed(1) + " GB") : Number(v).toLocaleString("en") + (data.unit ? " " + data.unit : "");
  const join = (a, b) => (a ? a.replace(/[\\/]$/, "") + (a.includes("\\") ? "\\" : "/") : "") + b.replace(/[\\/]$/, "");
  function row(r, path, parent, flat) {
    if (r.rest) return `<div class="tr rest"><div class="trow"><span class="ts">${esc(fmt(r.s))}</span><span class="tn">${esc(r.n)}</span></div></div>`;
    const pk = t.picks[path] || {}, cols = Object.entries(r.c || {}).map(([k, v]) => `<span><b>${esc(k)}:</b> ${esc(v)}</span>`).join(" ");
    const opts = ['<option value="">Pick</option>'].concat(t.choices.map((ch) => `<option value="${esc(ch)}"${pk.p === ch ? " selected" : ""}>${esc(ch)}${r.rec === ch ? " (my pick)" : ""}</option>`)).join("");
    const w = parent ? Math.max(1, Math.round(100 * r.s / parent)) : 0;
    return `<div class="tr" data-path="${esc(path)}"><details${r.k && !flat ? " data-k" : ""}><summary><span class="ts">${esc(fmt(r.s))}</span>`
      + `<span class="tn">${esc(flat ? path : r.n)}${r.rec ? ` <em class="trec">my pick: ${esc(r.rec)}</em>` : ""}</span>${cols ? `<span class="tc">${cols}</span>` : ""}${w ? `<i class="tsh" style="width:${w}%"></i>` : ""}</summary>`
      + `<div class="tk"></div></details><select class="tp" aria-label="Your pick for ${esc(r.n)}">${opts}</select></div>`;
  }
  function kids(r, path) {
    const list = (r.k || []).slice(), rest = r.s - list.reduce((a, k) => a + k.s, 0);
    if (list.length && rest >= (data.fmt === "bytes" ? 0.05 * G : 1)) list.push({ n: data.rest || "the rest, under the size shown", s: rest, rest: 1 });
    return list.map((k) => row(k, k.rest ? path + "#rest" : join(path, k.n), r.s)).join("");
  }
  const index = new Map(), all = [];
  (function walk(rows, base, at) { rows.forEach((r, i) => { const p = join(base, r.n), here = at.concat(i); index.set(p, here);
    all.push([p, (p + " " + Object.values(r.c || {}).join(" ")).toLowerCase(), r]); if (r.k) walk(r.k, p, here); }); })(data.rows, data.root || "", []);
  const find = (p) => (index.get(p) || []).reduce((r, k) => r.k[k], { k: data.rows });
  const box = $(".tw");
  function draw() {
    if (!t.q) { box.innerHTML = data.rows.map((r) => row(r, join(data.root || "", r.n), data.total || 0)).join(""); return; }
    const hit = all.filter((a) => a[1].includes(t.q));
    box.innerHTML = hit.slice(0, MAX).map(([p, , r]) => row(r, p, 0, true)).join("")
      + `<p class="empty">${hit.length ? (hit.length > MAX ? `${MAX} of ${hit.length} rows shown. Type more to narrow it.` : "") : "No row matches."}</p>`;
  }
  const text = () => all.filter(([p]) => t.picks[p] && (t.picks[p].p || t.picks[p].w)).map(([p, , r]) => { const k = t.picks[p]; return `${k.p || "note"}: ${p} (${fmt(r.s)})${k.w ? ` “${k.w}”` : ""}`; }).join("\n");
  function keep() { const n = Object.values(t.picks).filter((k) => k.p).length; $("#n").textContent = n ? n + " picked" : "";
    try { localStorage.setItem(KEY, JSON.stringify({ picks: t.picks, any: $("#any").value })); } catch (e) {} }
  try { const s = JSON.parse(localStorage.getItem(KEY) || "null"); if (s) { t.picks = s.picks || {}; $("#any").value = s.any || ""; } } catch (e) {}
  const word = (p, k) => `<input type="text" class="input tw-w" placeholder="A word on this row" aria-label="A word on ${esc(p)}" value="${esc(k.w || "")}">`;
  box.addEventListener("toggle", (e) => { const d = e.target; if (!d.open || d.dataset.done) return; d.dataset.done = 1;
    const p = d.closest(".tr").dataset.path, r = find(p), k = t.picks[p] || {};
    d.querySelector(".tk").innerHTML = (k.p || k.w ? word(p, k) : "") + (r.k && !t.q ? kids(r, p) : ""); }, true);
  box.addEventListener("input", (e) => { const x = e.target.closest(".tp,.tw-w"); if (!x) return; const p = x.closest(".tr").dataset.path, k = t.picks[p] = t.picks[p] || {};
    if (!x.classList.contains("tp")) { k.w = x.value.trim(); return keep(); }
    k.p = x.value; const d = x.closest(".tr").querySelector(":scope>details");
    if (k.p && d.dataset.done && !d.querySelector(":scope>.tk>.tw-w")) d.querySelector(".tk").insertAdjacentHTML("afterbegin", word(p, k));
    if (k.p) d.open = true; keep(); });
  let tm; $(".tq").addEventListener("input", (e) => { clearTimeout(tm); tm = setTimeout(() => { t.q = e.target.value.trim().toLowerCase(); draw(); }, 200); });
  $("#any").addEventListener("input", keep);
  const tall = $(".tall"); tall.hidden = !all.some(([, , r]) => r.rec);
  tall.addEventListener("click", () => { all.forEach(([p, , r]) => { if (r.rec && !(t.picks[p] || {}).p) (t.picks[p] = t.picks[p] || {}).p = r.rec; }); draw(); keep(); });
  $("#copy").addEventListener("click", function () { const b = this, a = $("#any").value.trim();
    const out = "PICKTREE REPLY: " + TITLE + "\n" + (text() || "(no picks)") + (a ? "\nGeneral: " + a : "");
    const ok = () => { b.textContent = "Copied"; setTimeout(() => { b.textContent = "Copy my picks"; }, 1600); };
    const fb = () => { const o = $("#out"); o.style.display = "block"; o.value = out; o.focus(); o.select(); };
    try { navigator.clipboard.writeText(out).then(ok, fb); } catch (e) { fb(); } });
  draw(); keep();
})();
</script>
</html>
"""

if __name__ == "__main__":
    main()
