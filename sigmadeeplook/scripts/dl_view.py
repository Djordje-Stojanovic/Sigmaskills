"""SigmaDeepLook human views: view.html for one look (native on the left, what the agent sees on the right) and gallery.html over many.

Self-contained: inline CSS, no CDN, no network. Every file the page references exists on disk.
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import dl_core as core

CSS = """
:root{--bg:#fafaf8;--fg:#1c1c1a;--mut:#6b6b66;--card:#fff;--line:#dcdcd5;--acc:#1f6f64;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ececea;--mut:#9a9a94;--card:#1f1f1d;--line:#34342f;--acc:#5fc4b6;--bad:#ff8a80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,sans-serif}
header{padding:14px 16px;border-bottom:1px solid var(--line)}h1{font-size:18px;margin:0}small{color:var(--mut)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px 16px}
@media (max-width:900px){.cols{grid-template-columns:1fr}}
.pane{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;min-width:0;overflow:auto}
.pane h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:0 0 8px}
img,video{max-width:100%;height:auto;border:1px solid var(--line);border-radius:4px}audio{width:100%}iframe{width:100%;height:520px;border:1px solid var(--line)}
pre{white-space:pre-wrap;word-break:break-word;font:12.5px/1.45 ui-monospace,Consolas,monospace;margin:6px 0}
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
    if t in ("code", "data", "notebook", "email") and p.stat().st_size < 4 << 20:
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
def gallery_main(argv):
    ap = argparse.ArgumentParser(prog="look.py gallery")
    ap.add_argument("dir", help="folder whose sub-folders hold look.json files")
    ap.add_argument("-o", "--output", default="gallery.html")
    ap.add_argument("--title", default="SigmaDeepLook gallery")
    o = ap.parse_args(argv)
    root = Path(o.dir)
    outp = Path(o.output).resolve()
    assets = outp.parent / (outp.stem + "_assets")
    shutil.rmtree(assets, ignore_errors=True)
    assets.mkdir(parents=True, exist_ok=True)
    rows = []
    for jf in sorted(root.glob("*/look.json")):
        d = json.loads(jf.read_text(encoding="utf-8"))
        name = jf.parent.name
        a_dir = assets / name
        a_dir.mkdir(exist_ok=True)
        src = Path(d["file"])
        native = ""
        t = d["type"]
        if src.is_file():
            size = src.stat().st_size
            copyable = size < 6 << 20
            if t in ("image",) and d["subtype"] != "svg" and copyable:
                shutil.copy2(src, a_dir / src.name)
                native = f'<img alt="original" src="{esc(rel(outp.parent, a_dir / src.name))}">'
            elif t == "video":
                prev = a_dir / "preview.mp4"
                ff = core.find_tool("ffmpeg")
                if copyable and src.suffix.lower() == ".mp4":
                    shutil.copy2(src, prev)
                elif ff:
                    subprocess.run([ff, "-y", "-v", "error", "-t", "20", "-i", str(src), "-vf", "scale=-2:360", "-c:v", "libx264", "-crf", "30", "-preset", "veryfast", "-c:a", "aac", "-b:a", "64k", str(prev)],
                                   capture_output=True, timeout=300)
                if prev.exists():
                    native = f'<video controls preload="metadata" src="{esc(rel(outp.parent, prev))}"></video><div class="px">{"original" if copyable else "first 20 s, 360p preview of the original"}</div>'
            elif t == "audio" and copyable:
                shutil.copy2(src, a_dir / src.name)
                native = f'<audio controls src="{esc(rel(outp.parent, a_dir / src.name))}"></audio>'
            elif t == "pdf" and copyable:
                shutil.copy2(src, a_dir / src.name)
                native = f'<iframe src="{esc(rel(outp.parent, a_dir / src.name))}" title="original PDF"></iframe>'
            elif t in ("code", "data", "notebook", "email", "web") and size < 200000:
                native = f"<pre>{esc(src.read_bytes()[:3000].decode('utf-8', 'replace'))}</pre><div class=\"px\">first 3 KB of the original</div>"
        if not native:
            native = '<div class="px">No browser viewer for the original of this kind; what the agent sees is on the right.</div>'
        imgs = []
        for a in d["artifacts"]:
            if a["kind"] == "image" and Path(a["path"]).exists():
                dst = a_dir / Path(a["path"]).name
                shutil.copy2(a["path"], dst)
                imgs.append(f'<div><img alt="{esc(a["what"])}" src="{esc(rel(outp.parent, dst))}"><div class="px">{esc(a.get("px", ""))} px</div></div>')
        flags = "".join(f'<tr><td class="flag">{esc(f["kind"])}</td><td>{esc(f["where"])}</td><td>{esc(f["value"])}</td></tr>' for f in d["flags"][:8])
        miss = "".join(f"<li>{esc(s['name'] if 'name' in s else s.get('step', ''))}: {esc(s['reason'])}</li>" for s in d["steps"] if s["status"] in ("skipped", "failed"))
        summ = "".join(f"<div>{inline(s) if chr(10) not in s else esc(s.splitlines()[0])}</div>" for s in d["summary"][:6])
        rows.append(f"""<section class="row"><h2>{esc(d['name'])} <small>{esc(t)} / {esc(d['subtype'])} - tier {esc(d['tier'])} - exit {d['exit']} - {d['elapsed_s']} s</small></h2>
<div class="cols"><div class="pane"><h2>Native</h2>{native}</div>
<div class="pane"><h2>Agent sees</h2>{summ}{''.join(imgs[:3])}{('<table>' + flags + '</table>') if flags else '<div class="px">Flags: none</div>'}{('<details><summary>Not looked at (' + str(miss.count('<li>')) + ')</summary><ul>' + miss + '</ul></details>') if miss else ''}</div></div></section>""")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(o.title)}</title><style>{CSS}.row{{border-bottom:2px solid var(--line);padding-bottom:8px}}.row>h2{{padding:10px 16px 0;margin:0;font-size:16px}}</style></head><body>
<header><h1>{esc(o.title)}</h1><small>{len(rows)} looks. Left: the original as a human sees it. Right: what the agent gets (facts, flags, the pictures at the size sent). Missing tools show as Not looked at.</small></header>
{''.join(rows)}</body></html>"""
    outp.write_text(page, encoding="utf-8")
    print(f"gallery: {len(rows)} looks -> {outp}")
    return 0
