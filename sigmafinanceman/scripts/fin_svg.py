"""Charts as plain SVG and the report as one HTML page, in the Ledger look (white sheet, navy rules, banker colours).

No chart library and no network: the page opens offline. Each chart is drawn twice, wide (desktop, print, the .svg file) and
narrow (phone: every label sits above its bar, nothing scrolls sideways).
"""
import html

import fin_models as F

TOK = {"bg": "#FFFFFF", "ink": "#1B1F24", "muted": "#5F6B7A", "rule": "#D5DAE1", "panel": "#F2F4F7", "navy": "#0B2545",
       "gain": "#17633B", "loss": "#D92D20", "steel": "#8A9BB0", "marker": "#8A5200", "center": "#BDD7EE",
       "input": "#0000FF", "link": "#008000"}
ROLE = {"total": TOK["navy"], "part": TOK["steel"], "muted": TOK["muted"]}
FONT = "Calibri, Carlito, 'Segoe UI', Arial, sans-serif"


def esc(s):
    return html.escape(str(s), quote=True)


def fmt(v, kind="money"):
    if v is None:
        return "n/a"
    if kind == "pct":
        return F.pct(v)
    if kind == "x":
        return F.mult(v)
    if kind == "ps":
        return F.per_share(v)
    if kind == "int":
        return f"{v:,.0f}"
    if kind == "num1":
        return f"{v:,.1f}"
    return F.money(v)


def _svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{esc(title)}" '
            f'style="font-family:{FONT};max-width:{w}px"><rect width="{w}" height="{h}" fill="{TOK["bg"]}"/>{body}</svg>')


def _t(x, y, s, size=13, fill=None, anchor="start", weight="normal"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill or TOK["ink"]}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{esc(s)}</text>')


def _r(x, y, w, h, fill, extra=""):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(0.0, w):.1f}" height="{max(0.0, h):.1f}" fill="{fill}" {extra}/>'


def waterfall(c, w=720, narrow=False):
    steps = c["steps"]
    if narrow:   # a list of bars, label above, value at the end (no sideways scroll on a phone)
        return hbars({"title": c["title"], "rows": [(s[0], s[1]) for s in steps], "roles": [s[2] for s in steps]}, w=360, narrow=True)
    h, top, bottom, left = 360, 30, 70, 20
    run, bars = 0.0, []
    for label, v, kind in steps:
        if kind == "total":
            lo, hi, run = 0.0, v, v
        else:
            lo, hi = sorted((run, run + v))
            run += v
        color = ROLE["total"] if kind == "total" else ROLE["part"] if kind == "part" else (TOK["gain"] if v >= 0 else TOK["loss"])
        bars.append((label, v, lo, hi, color))
    vmin, vmax = min(0.0, min(b[2] for b in bars)), max(b[3] for b in bars)
    y = lambda val: top + (vmax - val) / ((vmax - vmin) or 1) * (h - top - bottom)
    slot = (w - 2 * left) / len(bars)
    out = [f'<line x1="{left}" x2="{w - left}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="{TOK["rule"]}"/>']
    for i, (label, v, lo, hi, color) in enumerate(bars):
        x = left + i * slot + slot * 0.18
        bw = slot * 0.64
        out.append(_r(x, y(hi), bw, y(lo) - y(hi), color))
        out.append(_t(x + bw / 2, y(hi) - 6, fmt(v, c.get("fmt", "money")), 12, anchor="middle", weight="bold"))
        for k, part in enumerate(_wrap(label, 14)):
            out.append(_t(x + bw / 2, h - bottom + 18 + 14 * k, part, 12, TOK["muted"], "middle"))
    return _svg(w, h, "".join(out), c["title"])


def _wrap(s, n):
    words, lines, cur = s.split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > n and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    return lines + [cur] if cur else lines


def bars(c, w=720, narrow=False):
    labels, series = c["labels"], c["series"]
    if narrow:
        w = 360
    h, top, bottom, left = (300 if narrow else 340), 40, 40, 12
    vals = [v for _, s, _ in series for v in s if v is not None]
    vmax, vmin = max(vals + [0]), min(vals + [0])
    y = lambda val: top + (vmax - val) / ((vmax - vmin) or 1) * (h - top - bottom)
    slot = (w - 2 * left) / len(labels)
    bw = slot * 0.7 / len(series)
    out = []
    lx = left
    for name, _, role in series:   # legend
        out.append(_r(lx, 10, 10, 10, ROLE.get(role, TOK["navy"])))
        out.append(_t(lx + 14, 19, name, 12, TOK["muted"]))
        lx += 24 + 7 * len(name)
    out.append(f'<line x1="{left}" x2="{w - left}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="{TOK["rule"]}"/>')
    show_vals = len(labels) * len(series) <= (7 if narrow else 13 if len(series) == 1 else 12)
    for i, lab in enumerate(labels):
        for k, (name, s, role) in enumerate(series):
            v = s[i]
            if v is None:
                continue
            x = left + i * slot + slot * 0.15 + k * bw
            out.append(_r(x, min(y(v), y(0)), bw - 1, abs(y(v) - y(0)), ROLE.get(role, TOK["navy"])))
            if show_vals:
                out.append(_t(x + bw / 2, min(y(v), y(0)) - 4, fmt(v, c.get("fmt", "money")), 11 if narrow else 12, anchor="middle"))
        if not narrow or i % max(1, len(labels) // 7) == 0:
            out.append(_t(left + i * slot + slot / 2, h - bottom + 18, lab, 12, TOK["muted"], "middle"))
    return _svg(w, h, "".join(out), c["title"])


def hbars(c, w=720, narrow=False):
    rows = c["rows"]
    roles = c.get("roles")
    status = c.get("status")
    if narrow:
        w = 360
    label_w = 0 if narrow else 220
    row_h = 44 if narrow else 30
    h = 16 + row_h * len(rows)
    vals = [abs(v) for _, v in rows if v is not None]
    vmax = max(vals + [1e-9])
    span = w - label_w - 90
    out = []
    for i, (lab, v) in enumerate(rows):
        y0 = 10 + i * row_h
        if status:
            color = TOK["gain"] if v else TOK["loss"]
        elif roles:
            r = roles[i]
            color = ROLE["total"] if r == "total" else ROLE["part"] if r == "part" else (TOK["gain"] if (v or 0) >= 0 else TOK["loss"])
        else:
            color = TOK["navy"] if lab == c.get("highlight") else TOK["steel"]
        by = y0 + (18 if narrow else 4)
        if narrow:
            out.append(_t(0, y0 + 13, lab, 12, TOK["muted"]))
        else:
            out.append(_t(label_w - 10, y0 + 17, lab[:34], 12, TOK["muted"], "end"))
        bwid = (abs(v) / vmax * span) if v is not None else 0
        out.append(_r(label_w, by, max(bwid, 2 if status else 0), 18, color))
        shown = ("pass" if v else "fail") if status else fmt(v, c.get("fmt", "money"))
        out.append(_t(label_w + bwid + 6, by + 14, shown, 12, weight="bold"))
    return _svg(w, h, "".join(out), c["title"])


def football(c, w=720, narrow=False):
    rows = [r for r in c["rows"] if r[1] is not None and r[2] is not None]
    mlabel, mval = c["marker"]
    if narrow:
        w = 360
    label_w = 0 if narrow else 200
    row_h = 52 if narrow else 36
    h = 40 + row_h * len(rows) + 10
    lo = min([r[1] for r in rows] + [mval]) * 0.8   # room for the low labels left of the bars
    hi = max([r[2] for r in rows] + [mval]) * 1.05
    x = lambda v: label_w + 10 + (v - lo) / ((hi - lo) or 1) * (w - label_w - 70)
    out = []
    for i, (lab, a, b) in enumerate(rows):
        y0 = 40 + i * row_h
        by = y0 + (18 if narrow else 6)
        if narrow:
            out.append(_t(0, y0 + 13, lab, 12, TOK["muted"]))
        else:
            out.append(_t(label_w - 8, y0 + 21, lab, 12, TOK["muted"], "end"))
        out.append(_r(x(a), by, x(b) - x(a), 20, TOK["steel"]))
        out.append(_t(x(a) - 4, by + 34 if narrow else by + 15, F.per_share(a), 12, anchor="end" if not narrow else "start"))
        out.append(_t(x(b) + 4, by + 15, F.per_share(b), 12))
    mx = x(mval)
    out.append(f'<line x1="{mx:.1f}" x2="{mx:.1f}" y1="30" y2="{h - 6}" stroke="{TOK["marker"]}" stroke-width="2" stroke-dasharray="5 4"/>')
    tag = f"{mlabel} {F.per_share(mval)}"
    tw = 8 + 7 * len(tag)
    tx = min(max(mx - tw / 2, 0), w - tw)
    out.append(_r(tx, 4, tw, 22, TOK["navy"], 'rx="3"'))
    out.append(_t(tx + tw / 2, 20, tag, 12, "#FFFFFF", "middle", "bold"))
    return _svg(w, h, "".join(out), c["title"])


DRAW = {"waterfall": waterfall, "bars": bars, "hbars": hbars, "football": football}


def chart_svg(c, narrow=False):
    return DRAW[c["kind"]](c, narrow=narrow)


# ---------- the HTML page ----------

def cell(v, kind):
    """(html, css class) for one table cell. Positive numbers get a hidden ')' so digits line up with bracketed negatives."""
    if isinstance(v, str) or kind == "text":
        return esc("" if v is None else v), "l"
    if v is None:
        return "&nbsp;", "n"
    if kind == "auto":
        kind = "pct" if isinstance(v, float) and abs(v) < 1 and v != 0 else "num"
        if kind == "num":
            return esc(f"{v:,.2f}" if isinstance(v, float) and abs(v) < 1000 else f"{v:,.0f}"), "n"
    s = fmt(v, kind)
    pad = '<span class="pad">)</span>' if not s.endswith(")") and kind in ("money", "ps") else ""
    return esc(s) + pad, "n" + (" neg" if s.startswith("(") else "")


def table_html(t):
    head = "".join(f'<th class="{"l" if i == 0 or t["formats"][i] == "text" else "n"}">{esc(c)}</th>' for i, c in enumerate(t["columns"]))
    body = []
    rf = t.get("row_formats", {})
    center = t.get("center")
    for ri, row in enumerate(t["rows"]):
        cls = " total" if ri in t["totals"] else ""
        cls += " double" if ri in t["double"] else ""
        tds = []
        for ci, v in enumerate(row):
            kind = t["formats"][ci]
            if ci > 0 and rf.get(ri) and kind in ("money", "auto"):
                kind = rf[ri]
            h, c = cell(v, kind)
            if t.get("status_col") == ci:
                c += " ok" if str(v).lower() in ("pass", "clear") else " bad"
            if center and (ri, ci) == center:
                c += " center"
            tds.append(f'<td class="{c}">{h}</td>')
        body.append(f'<tr class="{cls.strip()}">{"".join(tds)}</tr>')
    note = f'<p class="note">{esc(t["note"])}</p>' if t.get("note") else ""
    return (f'<section class="sheet"><h2>{esc(t["title"])}</h2><div class="scroll"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>{note}</section>')


CSS = """
:root{--bg:%(bg)s;--ink:%(ink)s;--muted:%(muted)s;--rule:%(rule)s;--panel:%(panel)s;--navy:%(navy)s;--gain:%(gain)s;--loss:%(loss)s;--center:%(center)s}
*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 %(font)s;font-variant-numeric:tabular-nums}
main{max-width:1040px;margin:0 auto;padding:24px 16px 48px}
header.top{border-bottom:3px solid var(--navy);padding-bottom:12px;margin-bottom:20px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--muted);margin:0}
.hero{margin:18px 0 8px}.hero .v{font-size:44px;font-weight:700;line-height:1.05;color:var(--navy)}.hero .lab{color:var(--muted);font-size:14px}
.hero p{margin:6px 0 0;font-size:16px}
.kpis{display:flex;flex-wrap:wrap;gap:6px 22px;margin:14px 0 22px;padding:10px 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.kpis div{font-size:13px;color:var(--muted)}.kpis b{display:block;color:var(--ink);font-size:16px}
.sheet{margin:0 0 22px}h2{font-size:15px;margin:0 0 6px;color:var(--navy);border-bottom:1px solid var(--navy);padding-bottom:3px}
.scroll{overflow-x:auto}table{border-collapse:collapse;min-width:100%%}
th,td{padding:4px 8px;border-bottom:1px solid var(--rule);white-space:nowrap}th{font-size:13px;background:var(--navy);color:#fff;font-weight:600}
th.l,td.l{text-align:left}th.n,td.n{text-align:right}td.l{white-space:normal;min-width:120px}
tbody tr td:first-child,thead tr th:first-child{position:sticky;left:0;z-index:1}tbody tr td:first-child{background:var(--bg)}
td.neg{color:var(--ink)}.pad{visibility:hidden}
tr.total td{font-weight:700;border-top:1px solid var(--ink)}tr.double td{border-bottom:3px double var(--ink);font-weight:700}
td.center{background:var(--center);font-weight:700}td.ok{color:var(--gain);font-weight:700}td.bad{color:var(--loss);font-weight:700}
figure{margin:0 0 24px}figcaption{font-size:15px;font-weight:600;color:var(--navy);margin-bottom:6px}
.narrow{display:none}@media (max-width:600px){.wide{display:none}.narrow{display:block}.hero .v{font-size:36px}}
.notes{color:var(--muted);font-size:13px}.notes li{margin:2px 0;overflow-wrap:anywhere}td.l{overflow-wrap:anywhere}
:focus-visible{outline:2px solid var(--navy);outline-offset:2px}
@media print{.narrow{display:none}.wide{display:block}}
"""


def page(rep):
    hero = rep["hero"]
    kpis = "".join(f"<div>{esc(k)}<b>{esc(v)}</b></div>" for k, v in rep.get("kpis", []))
    figs = "".join(f'<figure><figcaption>{esc(c["title"])}</figcaption><div class="wide">{chart_svg(c)}</div>'
                   f'<div class="narrow">{chart_svg(c, True)}</div></figure>' for c in rep.get("charts", []))
    tables = "".join(table_html(t) for t in rep.get("tables", []))
    notes = "".join(f"<li>{esc(n)}</li>" for n in rep.get("notes", []))
    srcs = "".join(f"<li>{esc(s)}</li>" for s in rep.get("sources", []) if s)
    css = CSS % dict(TOK, font=FONT)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(rep["title"])}</title><style>{css}</style></head><body><main>'
            f'<header class="top"><h1>{esc(rep["title"])}</h1><p class="sub">{esc(rep["subtitle"])}</p></header>'
            f'<div class="hero"><div class="v">{esc(hero["value"])}</div><div class="lab">{esc(hero["label"])}</div><p>{esc(hero["line"])}</p></div>'
            f'<div class="kpis">{kpis}</div>{figs}{tables}'
            f'<section class="notes"><h2>Notes</h2><ul>{notes}</ul><h2>Sources</h2><ul>{srcs}</ul></section></main></body></html>')
