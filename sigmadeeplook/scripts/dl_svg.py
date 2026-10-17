"""SigmaDeepLook: what an SVG holds, counted (fix round 4). Stdlib only; never rendered, scripts never run.

Element counts per tag, path commands and subpaths (every M/m starts one), colours from attributes and style= (fill, stroke,
stop-color) with counts, stroke widths, opacity, coordinate extremes from shapes and from path data (absolute positions worked out
from relative commands; transforms are counted, not applied), ids, classes, text, gradients, groups, uses.
"""
import re
from collections import Counter

import dl_prof as P

CMD_RE = re.compile(r"([MmZzLlHhVvCcSsQqTtAa])|([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")
ARGS = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "t": 2, "a": 7, "z": 0}
COLOR_PROPS = ("fill", "stroke", "stop-color", "color", "flood-color", "lighting-color")


def path_points(d):
    """-> (subpaths, Counter of commands, [(x, y)] absolute end and control points). Arcs contribute their end point."""
    toks = CMD_RE.findall(d or "")
    cmds = Counter()
    pts = []
    sub = 0
    x = y = sx = sy = 0.0
    cmd = None
    nums = []

    def flush(c, args):
        nonlocal x, y, sx, sy, sub
        lc = c.lower()
        rel = c.islower()
        if lc == "m":
            x, y = (x + args[0], y + args[1]) if rel else (args[0], args[1])
            sx, sy = x, y
            pts.append((x, y))
        elif lc == "l" or lc == "t":
            x, y = (x + args[0], y + args[1]) if rel else (args[0], args[1])
            pts.append((x, y))
        elif lc == "h":
            x = x + args[0] if rel else args[0]
            pts.append((x, y))
        elif lc == "v":
            y = y + args[0] if rel else args[0]
            pts.append((x, y))
        elif lc in ("c", "s", "q"):
            n = ARGS[lc]
            for i in range(0, n, 2):
                px, py = (x + args[i], y + args[i + 1]) if rel else (args[i], args[i + 1])
                pts.append((px, py))
            x, y = pts[-1]
        elif lc == "a":
            x, y = (x + args[5], y + args[6]) if rel else (args[5], args[6])
            pts.append((x, y))
    for c, n in toks:
        if c:
            if c in "Zz":
                cmds[c] += 1
                x, y = sx, sy
                cmd = None
                continue
            cmd = c
            cmds[c] += 1
            if c in "Mm":
                sub += 1
            nums = []
            continue
        if cmd is None:
            continue
        nums.append(float(n))
        k = ARGS[cmd.lower()]
        if k and len(nums) == k:
            flush(cmd, nums)
            nums = []
            if cmd in "Mm":   # extra pairs after a moveto are linetos
                cmd = "l" if cmd == "m" else "L"
    return sub, cmds, pts


def norm_color(c):
    c = c.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        c = "#" + "".join(ch * 2 for ch in c[1:])
    return c


def look_svg(look, text):
    import xml.etree.ElementTree as ET
    dx = look.mod("defusedxml")
    if dx:
        from defusedxml import ElementTree as DET
        parse = DET.fromstring
    else:
        if "<!ENTITY" in text:
            look.flag("ENTITY-DECLARATION", "svg", "DTD entity declared", "not parsed")
            return
        parse = ET.fromstring
    try:
        root = parse(text.encode("utf-8"))
    except Exception as e:
        look.flag("INVALID-XML", "svg", f"{type(e).__name__}: {e}"[:120], "")
        return

    def local(t):
        return t.rsplit("}", 1)[-1] if isinstance(t, str) else str(t)
    tags = Counter()
    colors = {p: Counter() for p in COLOR_PROPS}
    widths, opac, ids, classes, transforms = Counter(), Counter(), [], Counter(), 0
    subpaths, cmds, xs, ys = 0, Counter(), [], []
    per_path = []
    texts = []
    for el in root.iter():
        t = local(el.tag)
        tags[t] += 1
        at = {local(k): v for k, v in el.attrib.items()}
        style = dict(kv.split(":", 1) for kv in (x.strip() for x in at.get("style", "").split(";")) if ":" in kv)
        props = {**at, **{k.strip(): v.strip() for k, v in style.items()}}
        for p in COLOR_PROPS:
            if p in props and props[p] not in ("", "inherit"):
                colors[p][norm_color(props[p])] += 1
        if "stroke-width" in props:
            widths[props["stroke-width"]] += 1
        for p in ("opacity", "fill-opacity", "stroke-opacity"):
            if p in props:
                opac[f"{p} {props[p]}"] += 1
        if "id" in at:
            ids.append(at["id"])
        for c in at.get("class", "").split():
            classes[c] += 1
        if "transform" in at:
            transforms += 1
        if t == "path":
            s, c, pts = path_points(at.get("d", ""))
            subpaths += s
            cmds.update(c)
            per_path.append((at.get("id", f"path {tags['path']}"), s, len(pts)))
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
        for kx, ky in (("x", "y"), ("cx", "cy"), ("x1", "y1"), ("x2", "y2")):
            try:
                if kx in at:
                    xs.append(float(re.match(r"[-+.\d eE]+", at[kx]).group()))
                if ky in at:
                    ys.append(float(re.match(r"[-+.\d eE]+", at[ky]).group()))
            except (AttributeError, ValueError):
                pass
        if t in ("rect", "image", "foreignObject") and "width" in at and "%" not in at["width"] + at.get("height", ""):
            try:
                x0, y0 = float(at.get("x", 0)), float(at.get("y", 0))
                xs += [x0, x0 + float(at["width"])]
                ys += [y0, y0 + float(at.get("height", 0))]
            except ValueError:
                pass
        if t == "circle" and "r" in at:
            try:
                r, cx, cy = float(at["r"]), float(at.get("cx", 0)), float(at.get("cy", 0))
                xs += [cx - r, cx + r]
                ys += [cy - r, cy + r]
            except ValueError:
                pass
        if t in ("polygon", "polyline") and at.get("points"):
            nums = [float(n) for n in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", at["points"])]
            xs += nums[0::2]
            ys += nums[1::2]
        if t in ("text", "tspan", "title", "desc") and (el.text or "").strip():
            texts.append(f"{t}: {el.text.strip()}")
    ra = {local(k): v for k, v in root.attrib.items()}
    all_colors = Counter()
    for p in colors.values():
        all_colors.update(p)
    P.counts(look, [("elements", sum(tags.values())), ("element kinds", len(tags)), ("paths", tags.get("path", 0)), ("subpaths (M/m commands)", subpaths),
                    ("path commands", sum(cmds.values())), ("groups", tags.get("g", 0)), ("shapes (rect, circle, ellipse, line, polyline, polygon)", sum(tags.get(k, 0) for k in ("rect", "circle", "ellipse", "line", "polyline", "polygon"))),
                    ("text elements", tags.get("text", 0) + tags.get("tspan", 0)), ("distinct colours", len(all_colors)), ("ids", len(ids)), ("classes", len(classes) or None),
                    ("transforms", transforms or None), ("gradients", tags.get("linearGradient", 0) + tags.get("radialGradient", 0) or None), ("uses", tags.get("use", 0) or None)], 95, "SVG counts")
    look.headline = f"SVG, {sum(tags.values()):,} elements ({tags.get('path', 0):,} paths, {subpaths:,} subpaths), viewBox {ra.get('viewBox', '-')}"
    look.line(f"SVG root: width {ra.get('width', '-')}, height {ra.get('height', '-')}, viewBox {ra.get('viewBox', '-')}; elements: " + ", ".join(f"{k} {v}" for k, v in tags.most_common()), 92)
    if xs and ys:
        look.line(f"Coordinate extremes (user units, transforms not applied): x {P.fmt(min(xs))} .. {P.fmt(max(xs))}, y {P.fmt(min(ys))} .. {P.fmt(max(ys))} ({len(xs):,} points).", 86)
    for p, c in colors.items():
        if c:
            look.line(f"{p} colours ({len(c)} distinct, uses): " + ", ".join(f"{k} {v}" for k, v in c.most_common(30)), 84 if p in ("fill", "stroke") else 60)
    if widths:
        look.line("stroke-width values: " + ", ".join(f"{k} x{v}" for k, v in widths.most_common(15)), 58)
    if opac:
        look.line("Opacity values: " + ", ".join(f"{k} x{v}" for k, v in opac.most_common(15)), 50)
    if cmds:
        look.line("Path commands (upper case absolute, lower case relative): " + ", ".join(f"{k} {v}" for k, v in sorted(cmds.items())), 62)
    if per_path:
        look.line(f"Subpaths per path ({len(per_path)} paths; id or number: subpaths, points): " + "; ".join(f"{n} {s}, {k}" for n, s, k in per_path[:200]), 34, "values")
    if ids:
        look.line(f"ids ({len(ids)}): " + ", ".join(ids[:150]), 40, "values")
    if classes:
        look.line(f"classes ({len(classes)}): " + ", ".join(f"{k} x{v}" for k, v in classes.most_common(60)), 38, "values")
    if texts:
        look.line(f"Text in the SVG ({len(texts)}): " + " | ".join(P.short(x, 80) for x in texts[:60]), 80)
