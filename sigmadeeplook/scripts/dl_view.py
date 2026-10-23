"""SigmaDeepLook human views: view.html for one look (native on the left, what the agent sees on the right) and gallery.html over many.

Self-contained: inline CSS, no CDN, no network. Every file the page references exists on disk.
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

import dl_core as core

CSS = """
:root{--bg:#fafaf8;--fg:#1c1c1a;--mut:#6b6b66;--card:#fff;--line:#dcdcd5;--acc:#1f6f64;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ececea;--mut:#9a9a94;--card:#1f1f1d;--line:#34342f;--acc:#5fc4b6;--bad:#ff8a80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,sans-serif}
header{padding:14px 16px;border-bottom:1px solid var(--line)}h1{font-size:18px;margin:0}small{color:var(--mut)}
.cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px;padding:12px 16px}
@media (max-width:900px){.cols{grid-template-columns:1fr}}
.pane{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;min-width:0;overflow-x:auto;overflow-wrap:anywhere}
.pane h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:0 0 8px}
img,video{max-width:100%;height:auto;border:1px solid var(--line);border-radius:4px}audio{width:100%}iframe{width:100%;height:520px;border:1px solid var(--line)}
pre{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;max-width:100%;font:12.5px/1.45 ui-monospace,Consolas,monospace;margin:6px 0}
table{border-collapse:collapse;font-size:13px;width:100%}td,th{border:1px solid var(--line);padding:3px 6px;text-align:left;vertical-align:top;word-break:break-word}
code{font:12.5px ui-monospace,Consolas,monospace}.px{color:var(--mut);font-size:12px}.flag{color:var(--bad)}
"""


def esc(s):
    return html.escape(str(s), quote=True)


def md_to_html(md):
    out, fence, table = [], False, False
    for ln in md.splitlines():
        if ln.startswith("```"):
            out.append("</pre>" if fence else "<pre>")
            fence = not fence
            continue
        if fence:
            out.append(esc(ln))
            continue
        if ln.startswith("|") and ln.strip().endswith("|"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", ln.strip().strip("|"))]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                continue
            if not table:
                out.append("<table>")
                table = True
                out.append("<tr>" + "".join(f"<th>{esc(c)}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{esc(c.replace(chr(92) + '|', '|'))}</td>" for c in cells) + "</tr>")
            continue
        if table:
            out.append("</table>")
            table = False
        m = re.match(r"(#{1,3}) (.*)", ln)
        if m:
            out.append(f"<h{len(m.group(1)) + 1}>{esc(m.group(2))}</h{len(m.group(1)) + 1}>")
        elif ln.startswith(("- ", "* ")):
            out.append(f"<div>&bull; {inline(ln[2:])}</div>")
        elif ln.strip():
            out.append(f"<div>{inline(ln)}</div>")
    if table:
        out.append("</table>")
    if fence:
        out.append("</pre>")
    return "\n".join(out)


def inline(s):
    parts = re.split(r"(`[^`]+`)", s)
    return "".join(f"<code>{esc(p[1:-1])}</code>" if p.startswith("`") and p.endswith("`") and len(p) > 1 else esc(p) for p in parts)


def rel(look_out, p):
    try:
        return Path(p).resolve().relative_to(Path(look_out).resolve()).as_posix()
    except ValueError:
        return Path(p).resolve().as_uri()


def texty(b):
    """True when the bytes read as text (no NUL, few control characters), so showing them in a <pre> is useful."""
    if not b or b"\x00" in b[:4000]:
        return False
    return sum(1 for c in b[:4000] if c in (9, 10, 13) or c >= 32) / len(b[:4000]) > 0.97


def is_bomb(look):
    return any(f.get("kind") == "DECOMPRESSION-BOMB?" for f in look.flags)


def native_html(look, out):
    p = look.path
    uri = p.resolve().as_uri() if p.exists() else ""
    t, st = look.type, look.subtype
    if p.is_dir():
        return "<p>Folder: no native viewer in a browser. See the map on the right.</p>"
    if t == "video":
        return f'<video controls preload="metadata" src="{esc(uri)}"></video><div class="px">original file, played by the browser (needs a codec the browser knows)</div>'
    if t == "audio":
        return f'<audio controls src="{esc(uri)}"></audio><div class="px">original file</div>'
    if t == "image" and is_bomb(look):
        return "<p>The header claims a huge picture; it is not shown here, and it was not decoded.</p>"
    if t == "image" and st != "svg":
        return f'<img alt="original" src="{esc(uri)}">'
    if t == "image":
        return f'<img alt="original svg (scripts do not run in img)" src="{esc(uri)}">'
    if t == "pdf":
        return f'<iframe src="{esc(uri)}" title="original PDF"></iframe>'
    if t == "web":
        return f'<iframe sandbox src="{esc(uri)}" title="original page, scripts off"></iframe>'
    if t == "font":
        face = f"@font-face{{font-family:'dlspec';src:url('{uri}')}}"
        return f"<style>{face}</style><div style=\"font-family:'dlspec',serif;font-size:36px\">Hamburgefonstiv 0123456789</div><div style=\"font-family:'dlspec',serif;font-size:18px\">The quick brown fox jumps over the lazy dog</div>"
    if t in ("code", "data", "notebook", "email") and p.stat().st_size < 4 << 20 and texty(p.read_bytes()[:4000]):
        txt = p.read_bytes()[:20000].decode("utf-8", "replace")
        return f'<pre>{esc(txt)}</pre><div class="px">first 20 KB of the original</div>'
    if t == "office":
        pages = [a for a in look.artifacts if a["kind"] == "image"]
        if pages:
            return "".join(f'<img alt="page" src="{esc(rel(out, a["path"]))}">' for a in pages[:3]) + '<div class="px">native proxy: a LibreOffice render, not Microsoft Office</div>'
        return "<p>No native viewer in a browser, and no LibreOffice render on this machine.</p>"
    hexp = Path(out) / "hexdump.txt"
    head = hexp.read_text(encoding="utf-8", errors="replace") if hexp.exists() else core.hexdump(p.read_bytes()[:256]) if p.exists() else ""
    return f"<p>No native viewer in a browser for this kind of file.</p><pre>{esc(head)}</pre>"


def write_view(look):
    out = look.out
    md = (out / "LOOK.md").read_text(encoding="utf-8")
    imgs = "".join(f'<div><img alt="{esc(a["what"])}" src="{esc(rel(out, a["path"]))}"><div class="px">{esc(a.get("px", ""))} px - {esc(a["what"])}</div></div>'
                   for a in look.artifacts if a["kind"] == "image")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Look: {esc(look.path.name)}</title><style>{CSS}</style></head><body>
<header><h1>Look: {esc(look.path.name)}</h1><small>{esc(look.type)} / {esc(look.subtype)} - tier {esc(look.tier())} - sha256 {esc(look.sha[:16])}</small></header>
<div class="cols"><section class="pane"><h2>Native: the original</h2>{native_html(look, out)}</section>
<section class="pane"><h2>Agent sees: LOOK.md and the pictures actually sent</h2>{md_to_html(md)}{imgs}</section></div></body></html>"""
    (out / "view.html").write_text(page, encoding="utf-8")


# ---------------------------------------------------------------- gallery
GALLERY_CSS = """
.wrap{max-width:1500px;margin:0 auto}
.intro{margin:14px 16px;padding:14px 16px;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:8px}
.intro h2{margin:0 0 6px;font-size:16px}.intro p{margin:6px 0}.intro .q{font-weight:600}
.tok{margin:0 16px 14px;overflow-x:auto}.tok table{min-width:640px}
.row{border-top:2px solid var(--line);padding-bottom:10px}
.row>h2{padding:12px 16px 0;margin:0;font-size:17px;overflow-wrap:anywhere}
.meta{padding:4px 16px 0;color:var(--mut);font-size:13px;overflow-wrap:anywhere}.meta b{color:var(--fg)}
.cost{margin:6px 16px 0;padding:6px 10px;background:var(--card);border:1px dashed var(--line);border-radius:6px;font-size:13px;overflow-wrap:anywhere}
.pane h3{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:0 0 8px}
details{margin:6px 0;border:1px solid var(--line);border-radius:6px;padding:4px 8px;background:var(--bg)}
details>summary{cursor:pointer;font-size:13px;overflow-wrap:anywhere}
.px{overflow-wrap:anywhere}.pane,.pane *{max-width:100%}
.pane pre{overflow-x:auto;max-height:420px}.pane table{table-layout:fixed}
.pane td,.pane th{overflow-wrap:anywhere}
.pane video,.pane iframe,.pane img{max-width:100%}
.nav{padding:0 16px;font-size:14px}
"""

TEXT_TYPES = {"data", "code", "email", "web", "notebook"}
BINARY_DATA = {"sqlite", "parquet", "arrow"}
PDF_TOKENS_PER_PAGE = 2000  # estimate: a page read by the host's own PDF reader (text plus picture)


def tok(n):
    return f"{int(n):,}"


def direct_cost(d):
    """-> (tokens or None, note). What it would cost to hand the raw file to an agent that reads natively."""
    t, st, size = d["type"], d["subtype"], d["size"]
    if (t in TEXT_TYPES and st not in BINARY_DATA) or (t == "image" and st == "svg") or (t == "3d" and st in ("obj", "stl-ascii", "ply", "gltf", "usd")):
        return core.direct_tokens(size), "raw text, size / 4"
    if t == "pdf":
        pages = d.get("facts", {}).get("pages") or 0
        return pages * PDF_TOKENS_PER_PAGE, f"{pages} pages x ~{tok(PDF_TOKENS_PER_PAGE)} tokens (estimate for the host's own PDF reader)"
    return None, "cannot be read directly (binary or media)"


def deeplook_cost(d, look_md):
    first = core.direct_tokens(len(look_md.encode("utf-8")))
    arts = sum(a.get("tokens_est", 0) for a in d["artifacts"] if a.get("kind") != "internal")
    if d["tier"] == "direct":  # the Read next of a direct look is the file itself: LOOK.md (tiny) plus the file
        arts = core.direct_tokens(d["size"])
    return first, first + arts


def native_for(d, src, assets, base):
    t, st = d["type"], d["subtype"]
    uri = src.resolve().as_uri() if src.exists() else ""
    if not src.is_file():
        return '<div class="px">The original is no longer at this path.</div>'
    size = src.stat().st_size

    def local(name=None):
        dst = assets / (name or src.name)
        if not dst.exists():
            shutil.copy2(src, dst)
        return esc(rel(base, dst))
    bomb = any(f.get("kind") == "DECOMPRESSION-BOMB?" for f in d["flags"])
    if t == "video":
        if src.suffix.lower() in (".mp4", ".m4v", ".webm"):
            return f'<video controls preload="metadata" src="{esc(uri)}"></video><div class="px">the original file, played by the browser (not copied; opened in place)</div>'
        prev = assets / "preview.mp4"
        ff = core.find_tool("ffmpeg")
        if ff and not prev.exists():
            core.run_tree([ff, "-y", "-v", "error", "-t", "20", "-i", str(src), "-vf", "scale=-2:360", "-c:v", "libx264", "-crf", "30", "-preset", "veryfast", "-c:a", "aac", "-b:a", "64k", str(prev)], 300)
        return f'<video controls preload="metadata" src="{esc(rel(base, prev))}"></video><div class="px">first 20 s, 360p preview of the original</div>' if prev.exists() else "<p>No browser player for this video.</p>"
    if t == "audio":
        return f'<audio controls src="{local() if size < 6 << 20 else esc(uri)}"></audio>'
    if t == "image" and bomb:
        return "<p>The header claims a huge picture; it is not shown, and it was not decoded.</p>"
    if t == "image":
        return f'<img alt="original" src="{local() if size < 12 << 20 else esc(uri)}">'
    if t == "pdf":
        return f'<iframe src="{local() if size < 12 << 20 else esc(uri)}" title="original PDF" style="height:560px"></iframe><div class="px">the original PDF in the browser viewer</div>'
    if t in TEXT_TYPES and st not in BINARY_DATA:
        n = 40 if size > 200000 else 400
        with open(src, "rb") as f:
            raw = f.read(24000)
        lines = raw.decode("utf-8", "replace").splitlines()[:n]
        total = sum(1 for _ in open(src, "rb")) if size < (300 << 20) else "many"
        return f"<pre>{esc(chr(10).join(lines))}</pre><div class=\"px\">what a text editor shows on opening: the first {len(lines)} of {total} lines ({core.human(size)} in all)</div>"
    if t == "archive" and st == "zip":
        try:
            import zipfile
            z = zipfile.ZipFile(src)
            names = [i.filename for i in z.infolist()]
            top = sorted({n.split("/")[0] + ("/" if "/" in n else "") for n in names})
            return f"<pre>{esc(chr(10).join(top[:40]))}</pre><div class=\"px\">what Explorer shows when the zip is opened: {len(top)} top-level entries ({len(names)} members in all)</div>"
        except Exception:
            pass
    if t == "office":
        pages = [a for a in d["artifacts"] if a["kind"] == "image"]
        if pages:
            dst = assets / Path(pages[0]["path"]).name
            shutil.copy2(pages[0]["path"], dst)
            return f'<img alt="page" src="{esc(rel(base, dst))}"><div class="px">LibreOffice render, not Microsoft Office</div>'
    if t == "font":
        face = f"@font-face{{font-family:'dlg{abs(hash(src.name)) % 99999}';src:url('{uri}')}}"
        fam = face.split("'")[1]
        return f"<style>{face}</style><div style=\"font-family:'{fam}',serif;font-size:32px\">Hamburgefonstiv 0123456789</div>"
    with open(src, "rb") as f:
        head = f.read(256)
    return f"<p>Double-clicking shows no content a person can read. The first 256 bytes, as a hex editor would:</p><pre>{esc(core.hexdump(head))}</pre>"


def read_next_inline(d, assets, base, cap=24000):
    out = []
    n = 0
    arts = [a for a in d["artifacts"] if a.get("kind") != "internal"]
    for a in [x for x in arts if x["kind"] != "image"] + [x for x in arts if x["kind"] == "image"]:
        n += 1
        p = Path(a["path"])
        label = f"{n}. {esc(p.name)} - {esc(a['what'])} - " + (f"{esc(a.get('px', ''))} px, " if a["kind"] == "image" else "") + f"~{tok(a.get('tokens_est', 0))} tokens"
        if not p.exists():
            out.append(f"<details><summary>{label}</summary><div class=\"px\">file missing</div></details>")
        elif a["kind"] == "image":
            dst = assets / p.name
            shutil.copy2(p, dst)
            out.append(f'<details><summary>{label}</summary><img alt="{esc(a["what"])}" src="{esc(rel(base, dst))}"></details>')
        else:
            raw = p.read_bytes()
            txt = raw[:cap].decode("utf-8", "replace")
            more = f'<div class="px">... shown: first {core.human(min(cap, len(raw)))} of {core.human(len(raw))}</div>' if len(raw) > cap else ""
            out.append(f"<details><summary>{label}</summary><pre>{esc(txt)}</pre>{more}</details>")
    return "".join(out) or '<div class="px">Nothing to read beyond LOOK.md.</div>'


INTRO = """<div class="intro"><h2>What SigmaDeepLook is for</h2>
<p>A coding agent can read text, but it cannot play a video, open a database, list a binary or read 50 MB of CSV without burning its whole budget. SigmaDeepLook turns such a file into a short <b>LOOK.md</b> (facts, flags, what to read next) plus a few text files and pictures. Small plain-text files (up to 50,000 bytes) are not touched: LOOK.md just says <i>Read this file directly</i>, because the agent reads them better itself.</p>
<p class="q">What to check on every row: from the right side alone, would you know what the file is and what is wrong with it?</p>
<p>Left is what a person gets by opening the file. Right is what the agent gets: the full LOOK.md, and under it every <i>Read next</i> file (click to open). A row passes when the right side answers the question faster and cheaper than the file itself would. The cost line under each title compares the two.</p>
<p><b>To approve:</b> type <b>yes deeplook</b> in chat. To send it back, name the rows that fail and what you could not tell from the right side.</p>
%LINKS%</div>"""


def gallery_main(argv):
    ap = argparse.ArgumentParser(prog="look.py gallery")
    ap.add_argument("dir", help="folder whose sub-folders hold look.json files")
    ap.add_argument("-o", "--output", default="gallery.html")
    ap.add_argument("--title", default="SigmaDeepLook gallery")
    ap.add_argument("--manifest", help="JSON list of {id, origin, note, kind}: row order and the notes shown under each title")
    ap.add_argument("--link", action="append", default=[], metavar="TEXT=URL", help="a link shown in the top box (repeatable)")
    ap.add_argument("--tokens-md", help="also write the token table as Markdown to this file")
    o = ap.parse_args(argv)
    root = Path(o.dir)
    outp = Path(o.output).resolve()
    base = outp.parent
    assets = base / (outp.stem + "_assets")
    shutil.rmtree(assets, ignore_errors=True)
    assets.mkdir(parents=True, exist_ok=True)
    meta = {}
    order = None
    if o.manifest:
        man = json.loads(Path(o.manifest).read_text(encoding="utf-8"))
        meta = {m["id"]: m for m in man}
        order = [m["id"] for m in man]
    dirs = [root / i for i in order if (root / i / "look.json").exists()] if order else sorted(p.parent for p in root.glob("*/look.json"))
    rows, table = [], []
    for dd in dirs:
        d = json.loads((dd / "look.json").read_text(encoding="utf-8"))
        name = dd.name
        info = meta.get(name, {})
        a_dir = assets / name
        a_dir.mkdir(exist_ok=True)
        src = Path(d["file"])
        look_md = (dd / "LOOK.md").read_text(encoding="utf-8")
        shown_md = look_md.replace(str(dd) + os.sep, "").replace(str(dd), "(look folder)")
        dtok, dnote = direct_cost(d)
        first, everything = deeplook_cost(d, look_md)
        size_h = core.human(d["size"])
        if dtok is None:
            cost = f"<b>size: {esc(size_h)}</b>. Direct read: {esc(dnote)}. SigmaDeepLook: <b>~{tok(first)} tokens</b> for LOOK.md, ~{tok(everything)} if every Read-next file is opened."
        else:
            ratio = f" ({dtok / max(1, first):.0f}x more than LOOK.md)" if dtok > first else ""
            cost = f"<b>size: {esc(size_h)}</b>. Direct read would cost <b>~{tok(dtok)} tokens</b> ({esc(dnote)}){ratio}. SigmaDeepLook: <b>~{tok(first)} tokens</b> for LOOK.md, ~{tok(everything)} if every Read-next file is opened."
        table.append((d["name"], size_h, dtok, dnote, first, everything, d["tier"]))
        origin = f'<b>{esc(info.get("kind", "").upper() or "fixture")}</b> - {esc(info.get("origin", ""))}. {esc(info.get("note", ""))}' if info else ""
        rows.append(f"""<section class="row" id="{esc(name)}"><h2>{esc(d['name'])} <small>{esc(d['type'])} / {esc(d['subtype'])} - tier {esc(d['tier'])} - exit {d['exit']} - {d['elapsed_s']} s</small></h2>
<div class="meta">{origin}</div><div class="cost">{cost}</div>
<div class="cols"><div class="pane"><h3>Native: what a person gets</h3>{native_for(d, src, a_dir, base)}</div>
<div class="pane"><h3>Agent view: the full LOOK.md (paths shown relative to its folder)</h3>{md_to_html(shown_md)}<h3 style="margin-top:14px">Read next: open any file the agent would open</h3>{read_next_inline(d, a_dir, base)}</div></div></section>""")
    links = ('<p class="nav">' + " | ".join(f'<a href="{esc(u)}">{esc(t)}</a>' for t, u in (x.split("=", 1) for x in o.link)) + "</p>") if o.link else ""
    trows = "".join(
        f"<tr><td>{esc(n)}</td><td>{esc(s)}</td><td>{('~' + tok(dt)) if dt is not None else 'n/a (binary or media)'}</td><td>~{tok(f)}</td><td>~{tok(e)}</td><td>{esc(tier)}</td></tr>"
        for n, s, dt, dn, f, e, tier in table)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(o.title)}</title><style>{CSS}{GALLERY_CSS}</style></head><body><div class="wrap">
<header><h1>{esc(o.title)}</h1><small>{len(rows)} rows</small></header>
{INTRO.replace('%LINKS%', links)}
<div class="tok"><table><tr><th>file</th><th>size</th><th>direct read costs</th><th>LOOK.md costs</th><th>LOOK.md + every Read-next file</th><th>tier</th></tr>{trows}</table>
<div class="px">Tokens are estimated: text = bytes / 4, PDF = pages x {tok(PDF_TOKENS_PER_PAGE)}, pictures = ceil(w/28) x ceil(h/28) after the long edge is shrunk to 1568 px (standard tier, at most 1568 tokens) or 2576 px (high-resolution tier, at most 4784). Binary and media cannot be read directly at all.</div></div>
{''.join(rows)}</div></body></html>"""
    outp.write_text(page, encoding="utf-8")
    if o.tokens_md:
        L = ["| file | size | direct read | LOOK.md | LOOK.md + all Read next | tier |", "|---|---|---|---|---|---|"]
        for n, s, dt, dn, f, e, tier in table:
            L.append(f"| {n} | {s} | {('~' + tok(dt)) if dt is not None else 'n/a (binary/media)'} | ~{tok(f)} | ~{tok(e)} | {tier} |")
        Path(o.tokens_md).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"gallery: {len(rows)} looks -> {outp}")
    return 0
