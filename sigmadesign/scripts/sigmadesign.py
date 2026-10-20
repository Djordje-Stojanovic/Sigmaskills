#!/usr/bin/env python3
"""sigmadesign: make a design system from one accent colour, build it into CSS and a sample page, check it, move a repo onto it.

Standard library only. The one source of truth is DESIGN.md (YAML front matter of tokens, then prose).

  new       <dir> --name N --accent "#34d399" [--neutral-hue DEG] [--neutral-sat PCT] [--font NAME] [--corners sharp|soft|round]
            writes <dir>/DESIGN.md: dark tokens, light-* tokens, type, rounded, spacing, components, prose skeleton
  pack      <DESIGN.md> --name yellow-black --accent "#fbbf24" [--light]
            adds a colour pack (a full dark or light palette from one accent) to design.packs.json next to DESIGN.md
  build     <DESIGN.md> --out DIR
            writes tokens.css (dark on :root, light, every pack), tailwind.css (@theme inline), components.css, index.html (sample page)
  check     <DESIGN.md> [--out DIR]
            WCAG contrast of every text/background pair in dark, light and each pack (AA 4.5, large and UI 3.0); with --out also fails when tokens.css is stale
  scan      <repo> [--tokens DESIGN.md] [--write]
            hard-coded colours in css/scss/html/jsx/tsx/vue/svelte; with --write, exact token values in .css/.scss files become var(--token)
  integrate <DESIGN.md> <repo> [--write]
            puts DESIGN.md at the repo root byte for byte and adds one pointer line to AGENTS.md / CLAUDE.md
  selftest  runs the built-in checks

Exit 0 = fine, 1 = a check failed, 2 = bad input.
"""
import argparse
import colorsys
import json
import re
import shutil
import sys
from pathlib import Path

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".venv", "venv", "__pycache__", "vendor", "vendored", "coverage", ".scratch"}
SCAN_EXT = {".css", ".scss", ".html", ".jsx", ".tsx", ".vue", ".svelte", ".js", ".ts"}
FONT_STACKS = {
    "mono": "ui-monospace, 'Cascadia Code', 'SF Mono', Menlo, Consolas, monospace",
    "sans": "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
}
CORNERS = {"sharp": (0, 2, 4, 6, 8), "soft": (4, 6, 10, 14, 16), "round": (8, 12, 16, 22, 28)}


# ---------- colour maths ----------

def hex_to_rgb(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError("not a hex colour: %r" % h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in rgb)


def hsl(h, s, l):
    """h in degrees, s and l in percent -> hex."""
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360.0, max(0, min(100, l)) / 100.0, max(0, min(100, s)) / 100.0)
    return rgb_to_hex((r * 255, g * 255, b * 255))


def to_hsl(hexv):
    r, g, b = [v / 255.0 for v in hex_to_rgb(hexv)]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s * 100, l * 100


def luminance(hexv):
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = [ch(v) for v in hex_to_rgb(hexv)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def push(hexv, against, target, direction):
    """Move lightness in `direction` (+1 lighter, -1 darker) until contrast with `against` reaches target."""
    h, s, l = to_hsl(hexv)
    for _ in range(100):
        c = hsl(h, s, l)
        if contrast(c, against) >= target:
            return c
        l += direction
        if l <= 0 or l >= 100:
            break
    return hsl(h, s, max(0, min(100, l)))


# ---------- palettes ----------

def palette(accent, neutral_hue=None, neutral_sat=6.0, light=False):
    """A full palette from one accent. Returns an ordered dict of token -> hex for dark (light=False) or light (light=True)."""
    ah, as_, al = to_hsl(accent)
    nh = ah if neutral_hue is None else neutral_hue
    ns = neutral_sat
    p = {}
    if not light:
        p["canvas"] = hsl(nh, ns, 4)
        p["glow"] = hsl(ah, min(as_, 70), 10)
        p["surface"] = hsl(nh, ns, 7)
        p["surface-2"] = hsl(nh, ns, 10)
        p["surface-3"] = hsl(nh, ns, 13)
        p["hairline"] = hsl(nh, ns, 16)
        p["hairline-strong"] = hsl(nh, ns, 26)
        p["ink"] = hsl(nh, ns, 96)
        p["body"] = hsl(nh, ns * 0.8, 84)
        p["mute"] = push(hsl(nh, ns * 0.8, 62), p["surface-2"], 4.5, +1)
        primary = push(accent, p["canvas"], 4.5, +1)
        p["primary"] = primary
        h, s, l = to_hsl(primary)
        p["primary-hover"] = hsl(h, s, min(l + 10, 90))
        p["primary-deep"] = hsl(h, s, max(l - 8, 20))
        p["on-primary"] = push(hsl(h, min(s, 80), 8), primary, 4.5, -1) if contrast(hsl(h, min(s, 80), 8), primary) >= contrast("#ffffff", primary) else push("#ffffff", primary, 4.5, +1)
        status = {"ok": 150, "warn": 43, "err": 5, "info": 199}
        for k, hue in status.items():
            p[k] = push(hsl(hue, 90, 68), p["surface"], 4.5, +1)
    else:
        p["canvas"] = hsl(nh, ns, 98)
        p["glow"] = p["canvas"]
        p["surface"] = "#ffffff"
        p["surface-2"] = hsl(nh, ns, 96)
        p["surface-3"] = hsl(nh, ns, 93)
        p["hairline"] = hsl(nh, ns, 90)
        p["hairline-strong"] = hsl(nh, ns, 80)
        p["ink"] = hsl(nh, ns, 10)
        p["body"] = hsl(nh, ns, 24)
        p["mute"] = push(hsl(nh, ns, 40), p["surface-2"], 4.5, -1)
        primary = push(accent, "#ffffff", 4.5, -1)
        p["primary"] = primary
        h, s, l = to_hsl(primary)
        p["primary-hover"] = hsl(h, s, max(l - 6, 10))
        p["primary-deep"] = hsl(h, s, max(l - 12, 8))
        p["on-primary"] = "#ffffff" if contrast("#ffffff", primary) >= 4.5 else hsl(h, s, 6)
        for k, hue in {"ok": 150, "warn": 38, "err": 5, "info": 205}.items():
            p[k] = push(hsl(hue, 85, 40), "#ffffff", 4.5, -1)
    return p


def build_tokens(name, accent, neutral_hue=None, neutral_sat=6.0, font="Inter", corners="soft", mono=None):
    dark = palette(accent, neutral_hue, neutral_sat, False)
    light = palette(accent, neutral_hue, neutral_sat, True)
    colors = dict(dark)
    for k, v in light.items():
        colors["light-" + k] = v
    sans = "%s, %s" % (font, FONT_STACKS["sans"])
    scale = [("display", 48, 600, 1.08, "-0.025em"), ("heading-xl", 28, 600, 1.25, "-0.015em"), ("heading-lg", 22, 600, 1.2, "-0.01em"),
             ("heading-md", 18, 600, 1.4, "0"), ("body-lg", 18, 400, 1.65, "0.01em"), ("body-md", 16, 400, 1.7, "0"),
             ("body-sm", 14, 400, 1.5, "0"), ("button", 14, 500, 1.0, "0"), ("caption", 13, 400, 1.4, "0"), ("label", 12, 700, 1.4, "0.08em")]
    typo = {}
    for n, size, weight, lh, ls in scale:
        typo[n] = {"fontFamily": sans, "fontSize": "%dpx" % size, "fontWeight": weight, "lineHeight": lh, "letterSpacing": ls}
    typo["code"] = {"fontFamily": mono or FONT_STACKS["mono"], "fontSize": "13.5px", "fontWeight": 400, "lineHeight": 1.55, "letterSpacing": "0"}
    xs, sm, md, lg, xl = CORNERS[corners]
    rounded = {"xs": "%dpx" % xs, "sm": "%dpx" % sm, "md": "%dpx" % md, "lg": "%dpx" % lg, "xl": "%dpx" % xl, "full": "9999px"}
    spacing = {"xxs": "2px", "xs": "4px", "sm": "8px", "md": "12px", "lg": "16px", "xl": "24px", "xxl": "32px", "section": "64px", "huge": "96px"}
    components = {}
    for pre, tag in (("", ""), ("light-", "light-")):
        def c(k, pre=pre):
            return "{colors.%s%s}" % (pre, k)

        def box(bg, fg, typo="body-sm", rad="md", **extra):
            d = {"backgroundColor": c(bg), "textColor": c(fg), "typography": "{typography.%s}" % typo, "rounded": "{rounded.%s}" % rad}
            d.update(extra)
            return d

        components[tag + "page"] = {"backgroundColor": c("canvas"), "textColor": c("body"), "typography": "{typography.body-md}"}
        components[tag + "page-glow"] = {"backgroundColor": c("glow"), "textColor": c("body")}
        components[tag + "button-primary"] = box("primary", "on-primary", "button", padding="0px 16px", height="40px")
        components[tag + "button-primary-hover"] = box("primary-hover", "on-primary", "button", padding="0px 16px", height="40px")
        components[tag + "button-primary-pressed"] = box("primary-deep", "on-primary", "button", padding="0px 16px", height="40px")
        components[tag + "button-outline"] = box("surface", "ink", "button", padding="0px 16px", height="40px")
        components[tag + "button-ghost"] = box("canvas", "mute", "button", padding="0px 12px", height="40px")
        components[tag + "text-input"] = box("surface-2", "ink", padding="0px 12px", height="40px")
        components[tag + "card"] = box("surface", "ink", rad="lg", padding="16px")
        components[tag + "card-raised"] = box("surface-3", "ink", rad="lg", padding="16px")
        components[tag + "chip"] = box("surface-2", "body", "caption", "full", padding="0px 12px", height="28px")
        components[tag + "divider"] = {"backgroundColor": c("hairline"), "textColor": c("ink"), "height": "1px"}
        components[tag + "divider-strong"] = {"backgroundColor": c("hairline-strong"), "textColor": c("ink"), "height": "1px"}
        for state in ("ok", "warn", "err", "info"):
            components["%sstatus-%s" % (tag, state)] = box("surface", state, "label", "full", padding="0px 12px", height="24px")
    return {"version": "alpha", "name": name, "colors": colors, "typography": typo, "rounded": rounded, "spacing": spacing, "components": components}


# ---------- DESIGN.md front matter (a small YAML subset: nested maps, scalars) ----------

def dump_front(tokens, description):
    out = ["---", "version: %s" % tokens["version"], "name: %s" % tokens["name"], "description: %s" % _scalar(description), ""]
    for section in ("colors", "typography", "rounded", "spacing", "components"):
        out.append(section + ":")
        for k, v in tokens[section].items():
            if isinstance(v, dict):
                out.append("  %s:" % k)
                for kk, vv in v.items():
                    out.append("    %s: %s" % (kk, _scalar(vv)))
            else:
                out.append("  %s: %s" % (k, _scalar(v)))
        out.append("")
    out.append("---")
    return "\n".join(out)


def _scalar(v):
    s = str(v)
    if s.startswith("#") or s.startswith("{") or "," in s or ":" in s:
        return '"%s"' % s.replace('"', '\\"')
    return s


def parse_front(text):
    m = re.match(r"﻿?---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        raise ValueError("no YAML front matter between --- lines")
    root, stack = {}, [(-1, {})]
    stack = [(-1, root)]
    for raw in m.group(1).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, _, val = raw.strip().partition(":")
        val = val.strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if val == "":
            parent[key] = {}
            stack.append((indent, parent[key]))
        else:
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            parent[key] = val
    return root


def load_design(path):
    p = Path(path)
    data = parse_front(p.read_text(encoding="utf-8"))
    for need in ("colors", "typography", "rounded", "spacing"):
        if need not in data:
            raise ValueError("front matter has no %r" % need)
    packs_file = p.parent / "design.packs.json"
    packs = json.loads(packs_file.read_text(encoding="utf-8")) if packs_file.exists() else {}
    return data, packs


# ---------- build ----------

def css_name(k):
    return "--" + k


def split_colors(colors):
    dark = {k: v for k, v in colors.items() if not k.startswith("light-")}
    light = {k[6:]: v for k, v in colors.items() if k.startswith("light-")}
    return dark, light


def tokens_css(data, packs):
    dark, light = split_colors(data["colors"])
    out = ["/* GENERATED by sigmadesign.py build from DESIGN.md. Edit DESIGN.md or design.packs.json, then run build again. */", ":root {"]
    out.append("  color-scheme: dark;")
    for k, v in dark.items():
        out.append("  %s: %s;" % (css_name(k), v))
    for k, v in data["rounded"].items():
        out.append("  --radius-%s: %s;" % (k, v))
    for k, v in data["spacing"].items():
        out.append("  --space-%s: %s;" % (k, v))
    for k, v in data["typography"].items():
        out.append("  --font-%s: %s;" % (k, v["fontFamily"]))
        out.append("  --text-%s: %s;" % (k, v["fontSize"]))
    out += ["  --ease: cubic-bezier(.2,.7,.2,1);", "  --dur-fast: 150ms;", "  --dur: 200ms;", "  --dur-slow: 300ms;", "  --hit: 44px;", "}", ""]
    out.append(':root[data-theme="light"] {')
    out.append("  color-scheme: light;")
    for k, v in light.items():
        out.append("  %s: %s;" % (css_name(k), v))
    out += ["}", ""]
    for name, pack in packs.items():
        out.append(':root[data-theme="%s"] {' % name)
        out.append("  color-scheme: %s;" % ("light" if pack.get("mode") == "light" else "dark"))
        for k, v in pack["colors"].items():
            out.append("  %s: %s;" % (css_name(k), v))
        out += ["}", ""]
    out += ["@media (prefers-reduced-motion: reduce) { :root { --dur-fast: 0ms; --dur: 0ms; --dur-slow: 0ms; } }", ""]
    return "\n".join(out)


def tailwind_css(data):
    names = list(split_colors(data["colors"])[0].keys())
    out = ["/* GENERATED by sigmadesign.py build. Import after tokens.css in a Tailwind 4 project. */", "@theme inline {"]
    for n in names:
        out.append("  --color-%s: var(--%s);" % (n, n))
    for n in data["rounded"]:
        out.append("  --radius-%s: var(--radius-%s);" % (n, n))
    out.append("  --font-sans: var(--font-body-md);")
    out.append("  --font-mono: var(--font-code);")
    out += ["}", ""]
    return "\n".join(out)


COMPONENTS_CSS = """/* GENERATED by sigmadesign.py build. Components read tokens only: no colour literal below. */
*, *::before, *::after { box-sizing: border-box; }
html { background: var(--canvas); }
body { margin: 0; min-height: 100vh; color: var(--body); background: radial-gradient(1100px 520px at 85% -10%, var(--glow, transparent), transparent 70%), var(--canvas);
  font: 400 var(--text-body-md)/1.7 var(--font-body-md); -webkit-font-smoothing: antialiased; }
:root[data-theme="light"] body { background: var(--canvas); }
h1, h2, h3 { color: var(--ink); font-family: var(--font-display); font-weight: 600; margin: 0; }
h1 { font-size: clamp(34px, 6vw, var(--text-display)); line-height: 1.08; letter-spacing: -0.025em; }
h2 { font-size: var(--text-heading-lg); line-height: 1.2; letter-spacing: -0.01em; }
h3 { font-size: var(--text-heading-md); line-height: 1.4; }
p { margin: 0; max-width: 62ch; }
a { color: var(--primary); }
code { font: 400 var(--text-code)/1.55 var(--font-code); background: var(--surface-2); padding: 2px 6px; border-radius: var(--radius-sm); }
:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.wrap { width: min(1080px, 100% - 32px); margin-inline: auto; }
.topbar { display: flex; align-items: center; gap: var(--space-lg); min-height: 56px; border-bottom: 1px solid var(--hairline); }
.topbar .brand { color: var(--ink); font-weight: 600; margin-right: auto; text-decoration: none; }
.label { font-size: var(--text-label); font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--mute); }
.hero { display: grid; gap: var(--space-lg); padding-block: var(--space-section) var(--space-xxl); }
.grid { display: grid; gap: var(--space-lg); grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); padding-bottom: var(--space-section); }
.card { background: var(--surface); border: 1px solid var(--hairline); border-radius: var(--radius-lg); padding: var(--space-lg); display: grid; gap: var(--space-sm); align-content: start; }
.card h3 { margin-bottom: 2px; }
.btn { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-sm); min-height: var(--hit); padding: 0 var(--space-lg); border-radius: var(--radius-md);
  border: 1px solid var(--hairline-strong, var(--hairline)); background: var(--surface); color: var(--ink); font: 500 var(--text-button)/1 var(--font-button); cursor: pointer; text-decoration: none;
  transition: background var(--dur) var(--ease), border-color var(--dur) var(--ease); }
.btn:hover { background: var(--surface-2); }
.btn-primary { background: var(--primary); border-color: var(--primary); color: var(--on-primary); }
.btn-primary:hover { background: var(--primary-hover); border-color: var(--primary-hover); }
.btn-ghost { background: transparent; border-color: transparent; color: var(--mute); }
.chip { display: inline-flex; align-items: center; min-height: 28px; padding: 0 var(--space-md); border-radius: var(--radius-full); background: var(--surface-2); color: var(--body); font-size: var(--text-caption); border: 1px solid var(--hairline); cursor: pointer; }
@media (pointer: coarse) { .chip { min-height: var(--hit); } }
.chip[aria-pressed="true"] { background: var(--primary); border-color: var(--primary); color: var(--on-primary); }
.field { display: grid; gap: 6px; }
.input { min-height: 40px; padding: 0 var(--space-md); border-radius: var(--radius-md); border: 1px solid var(--hairline); background: var(--surface-2); color: var(--ink); font: inherit; }
.row { display: flex; flex-wrap: wrap; gap: var(--space-sm); align-items: center; }
.swatches { display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: var(--space-sm); }
.swatch { border: 1px solid var(--hairline); border-radius: var(--radius-md); overflow: hidden; background: var(--surface); font-size: var(--text-caption); }
.swatch i { display: block; height: 40px; }
.swatch span { display: block; padding: 6px 8px; color: var(--body); }
.status { display: flex; gap: var(--space-md); flex-wrap: wrap; }
.status b { font-weight: 600; }
.ok { color: var(--ok); } .warn { color: var(--warn); } .err { color: var(--err); } .info { color: var(--info); }
@media (max-width: 640px) { .hero { padding-block: var(--space-xxl); } .topbar { flex-wrap: wrap; padding-block: var(--space-sm); } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
"""


def sample_page(data, packs):
    name = data.get("name", "Design")
    dark, _ = split_colors(data["colors"])
    sw = "".join('<div class="swatch"><i style="background:var(--%s)"></i><span>%s</span></div>' % (k, k) for k in dark)
    themes = ["dark", "light"] + list(packs)
    chips = "".join('<button class="chip" type="button" data-theme-pick="%s" aria-pressed="false">%s</button>' % (t, t) for t in themes)
    return """<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(name)s sample</title>
<link rel="stylesheet" href="tokens.css">
<link rel="stylesheet" href="components.css">
</head>
<body>
<header class="wrap topbar"><a class="brand" href="#">%(name)s</a><span class="label">sample page</span></header>
<main class="wrap">
  <section class="hero">
    <span class="label">Design system</span>
    <h1>One accent colour makes every theme.</h1>
    <p>This page uses tokens only. Switch the pack below: text, buttons and surfaces change, and nothing is written twice.</p>
    <div class="row" role="group" aria-label="Theme">%(chips)s</div>
    <div class="row"><a class="btn btn-primary" href="#swatches">See the tokens</a><a class="btn" href="#form">Outline button</a><button class="btn btn-ghost" type="button">Ghost button</button></div>
  </section>
  <section class="grid" aria-label="Cards">
    <article class="card"><h3>Card on a surface</h3><p>Body text sits on the surface ladder with a hairline border.</p><span class="label">label</span></article>
    <article class="card" id="form"><h3>Form field</h3><div class="field"><label class="label" for="x">Name</label><input class="input" id="x" placeholder="Type here"></div></article>
    <article class="card"><h3>Status colours</h3><div class="status"><b class="ok">ok</b><b class="warn">warn</b><b class="err">err</b><b class="info">info</b></div></article>
  </section>
  <section id="swatches" style="padding-bottom:var(--space-section)"><h2 style="margin-bottom:var(--space-lg)">Colour tokens</h2><div class="swatches">%(sw)s</div></section>
</main>
<script>
(function () {
  var root = document.documentElement, chips = document.querySelectorAll('[data-theme-pick]');
  function set(t) { root.setAttribute('data-theme', t); chips.forEach(function (c) { c.setAttribute('aria-pressed', c.dataset.themePick === t); }); try { localStorage.setItem('theme', t); } catch (e) {} }
  var q = new URLSearchParams(location.search).get('theme'), saved = null; try { saved = localStorage.getItem('theme'); } catch (e) {}
  set(q || saved || 'dark');
  chips.forEach(function (c) { c.addEventListener('click', function () { set(c.dataset.themePick); }); });
})();
</script>
</body>
</html>
""" % {"name": name, "chips": chips, "sw": sw}


def build(design, out):
    data, packs = load_design(design)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = {"tokens.css": tokens_css(data, packs), "tailwind.css": tailwind_css(data), "components.css": COMPONENTS_CSS, "index.html": sample_page(data, packs)}
    for n, t in files.items():
        (out / n).write_text(t, encoding="utf-8", newline="\n")
    return sorted(files)


# ---------- check ----------

PAIRS = [("ink", "canvas", 4.5), ("ink", "surface", 4.5), ("body", "surface", 4.5), ("mute", "surface", 4.5), ("mute", "surface-2", 4.5),
         ("on-primary", "primary", 4.5), ("primary", "canvas", 3.0), ("primary", "surface", 3.0),
         ("ok", "surface", 4.5), ("warn", "surface", 4.5), ("err", "surface", 4.5), ("info", "surface", 4.5)]


def check_palette(label, colors, pairs=PAIRS):
    bad = []
    for fg, bg, need in pairs:
        if fg in colors and bg in colors:
            c = contrast(colors[fg], colors[bg])
            if c < need:
                bad.append("%s: %s on %s = %.2f:1, needs %.1f:1" % (label, fg, bg, c, need))
    return bad


def check(design, out=None):
    data, packs = load_design(design)
    dark, light = split_colors(data["colors"])
    problems = check_palette("dark", dark)
    light_pairs = [p for p in PAIRS if p[1] != "surface-2" or "surface-2" in light]
    problems += check_palette("light", light, light_pairs)
    for name, pack in packs.items():
        problems += check_palette("pack " + name, pack["colors"], light_pairs if pack.get("mode") == "light" else PAIRS)
    if out:
        t = Path(out) / "tokens.css"
        if not t.exists() or t.read_text(encoding="utf-8") != tokens_css(data, packs):
            problems.append("%s is missing or stale: run build" % t)
    return problems


# ---------- packs ----------

def add_pack(design, name, accent, light=False):
    p = Path(design)
    data, packs = load_design(p)
    dark, _ = split_colors(data["colors"])
    nh = None
    pal = palette(accent, nh, 6.0, light)
    packs[name] = {"mode": "light" if light else "dark", "accent": accent, "colors": pal}
    bad = check_palette("pack " + name, pal, PAIRS if not light else [x for x in PAIRS if x[1] != "surface-2"])
    (p.parent / "design.packs.json").write_text(json.dumps(packs, indent=2), encoding="utf-8", newline="\n")
    return bad


# ---------- scan and integrate ----------

def iter_files(repo):
    for f in Path(repo).rglob("*"):
        if f.is_file() and f.suffix.lower() in SCAN_EXT and not (set(f.relative_to(repo).parts[:-1]) & SKIP_DIRS) and f.name not in ("tokens.css", "tailwind.css", "components.css"):
            yield f


HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def nearest(hexv, table):
    r, g, b = hex_to_rgb(hexv)
    best = None
    for name, val in table.items():
        try:
            r2, g2, b2 = hex_to_rgb(val)
        except ValueError:
            continue
        d = (r - r2) ** 2 + (g - g2) ** 2 + (b - b2) ** 2
        if best is None or d < best[0]:
            best = (d, name, val)
    return best


def scan(repo, tokens=None, write=False):
    table = {}
    if tokens:
        data, _ = load_design(tokens)
        table = {k: v for k, v in data["colors"].items() if re.fullmatch(r"#[0-9a-fA-F]{6}", v)}
        exact = {v.lower(): k for k, v in table.items() if not k.startswith("light-")}
    else:
        exact = {}
    found, changed = {}, 0
    for f in iter_files(repo):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in HEX_RE.finditer(text):
            v = m.group(0).lower()
            if len(v) == 4:
                v = "#" + "".join(c * 2 for c in v[1:])
            found.setdefault(v, []).append(str(f.relative_to(repo)))
        if write and exact and f.suffix.lower() in (".css", ".scss"):
            def sub(m):
                v = m.group(0).lower()
                if len(v) == 4:
                    v = "#" + "".join(c * 2 for c in v[1:])
                return "var(--%s)" % exact[v] if v in exact else m.group(0)
            new = HEX_RE.sub(sub, text)
            if new != text:
                f.write_bytes(new.encode("utf-8"))
                changed += 1
    rows = []
    for v, fl in sorted(found.items(), key=lambda kv: -len(kv[1])):
        near = nearest(v, table) if table else None
        rows.append({"value": v, "uses": len(fl), "files": sorted(set(fl))[:5], "token": ("--" + near[1]) if near and near[0] == 0 else None, "nearest": ("--%s (%s)" % (near[1], near[2])) if near else None})
    return rows, changed


def integrate(design, repo, write=False):
    src, repo = Path(design), Path(repo)
    dst = repo / "DESIGN.md"
    report = []
    same = dst.exists() and dst.read_bytes() == src.read_bytes()
    report.append("DESIGN.md at root: %s" % ("already identical" if same else "will be written" if not write else "written"))
    if write and not same:
        shutil.copyfile(src, dst)
    line = "UI work: read DESIGN.md first (the one design file: tokens, type, layout, components); change a value there, never in generated CSS."
    for n in ("AGENTS.md", "CLAUDE.md"):
        f = repo / n
        if not f.exists():
            continue
        raw = f.read_bytes()
        t = raw.decode("utf-8")
        eol = "\r\n" if b"\r\n" in raw else "\n"
        if "DESIGN.md" in t:
            report.append("%s: already mentions DESIGN.md" % n)
        else:
            report.append("%s: pointer %s" % (n, "added" if write else "will be added"))
            if write:
                f.write_bytes((t.rstrip("\r\n") + eol + eol + line + eol).encode("utf-8"))
    return report


# ---------- new ----------

PROSE = """
## Overview

FILL: one paragraph. What the product is, who uses it, the one mood word, and the single most memorable thing about the look.

## Colors

- **Canvas and surfaces** (`canvas`, `surface`, `surface-2`, `surface-3`): a tinted ladder, each step one notch lighter; borders are `hairline`.
- **Ink, body, mute**: text roles. `mute` is the quietest text that still passes 4.5:1 on a surface.
- **Primary**: the one accent. One filled primary button per view. `on-primary` is the text on it.
- **Status**: `ok`, `warn`, `err`, `info`, only for state.
- **Light tokens** (`light-*`) exist for a light theme; dark is the default.
- **Packs**: other accents live in `design.packs.json` (`sigmadesign.py pack`); each pack is checked for contrast.

## Typography

FILL: the families and why, the scale in use, line length under 80 characters, headings weight and case.

## Layout

FILL: grid, max width, spacing rhythm (`spacing` tokens), breakpoints, alignment rule.

## Components

Button, card, input and chip are defined above. FILL: add the components this product needs; each uses tokens only.

## Do's and Don'ts

- Do use `var(--token)`; do not write a colour literal in page CSS.
- Do keep one filled primary button per view; do not add a second accent.
- Do keep touch targets at least 44 px; do not remove the focus ring.

## Responsive Behavior

FILL: what changes at phone width (navigation, grids, type sizes) and the smallest width tested.

## Iteration Guide

Change a value here, run `python sigmadesign.py build DESIGN.md --out <dir>`, run `check`, look at `index.html`.
"""


def new(dest, name, accent, neutral_hue, neutral_sat, font, corners):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / "DESIGN.md"
    if target.exists():
        raise FileExistsError("%s exists; refusing to overwrite" % target)
    tokens = build_tokens(name, accent, neutral_hue, neutral_sat, font, corners)
    desc = "FILL: one sentence on the look: ground, accent, type, and what carries the colour."
    target.write_text(dump_front(tokens, desc) + "\n" + PROSE, encoding="utf-8", newline="\n")
    return target


# ---------- selftest and CLI ----------

def selftest():
    import tempfile
    assert abs(contrast("#000000", "#ffffff") - 21) < 0.01
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        new(d / "a", "Test", "#34d399", None, 6.0, "Inter", "soft")
        design = d / "a" / "DESIGN.md"
        assert check(design) == [], check(design)
        assert add_pack(design, "yellow-black", "#fbbf24") == []
        assert add_pack(design, "red-white", "#dc2626", light=True) == []
        build(design, d / "out")
        assert check(design, d / "out") == []
        assert "yellow-black" in (d / "out" / "tokens.css").read_text(encoding="utf-8")
    print("selftest ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new"); p.add_argument("dir"); p.add_argument("--name", required=True); p.add_argument("--accent", required=True)
    p.add_argument("--neutral-hue", type=float); p.add_argument("--neutral-sat", type=float, default=6.0); p.add_argument("--font", default="Inter"); p.add_argument("--corners", choices=list(CORNERS), default="soft")
    p = sub.add_parser("pack"); p.add_argument("design"); p.add_argument("--name", required=True); p.add_argument("--accent", required=True); p.add_argument("--light", action="store_true")
    p = sub.add_parser("build"); p.add_argument("design"); p.add_argument("--out", required=True)
    p = sub.add_parser("check"); p.add_argument("design"); p.add_argument("--out")
    p = sub.add_parser("scan"); p.add_argument("repo"); p.add_argument("--tokens"); p.add_argument("--write", action="store_true")
    p = sub.add_parser("integrate"); p.add_argument("design"); p.add_argument("repo"); p.add_argument("--write", action="store_true")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "new":
            print("wrote", new(a.dir, a.name, a.accent, a.neutral_hue, a.neutral_sat, a.font, a.corners))
            return 0
        if a.cmd == "pack":
            bad = add_pack(a.design, a.name, a.accent, a.light)
            print("pack %s added" % a.name)
            for b in bad:
                print("FAIL", b)
            return 1 if bad else 0
        if a.cmd == "build":
            print("wrote", ", ".join(build(a.design, a.out)), "in", a.out)
            return 0
        if a.cmd == "check":
            bad = check(a.design, a.out)
            for b in bad:
                print("FAIL", b)
            print("%d problem(s)" % len(bad) if bad else "contrast ok")
            return 1 if bad else 0
        if a.cmd == "scan":
            rows, changed = scan(a.repo, a.tokens, a.write)
            for r in rows[:60]:
                print("%-8s x%-3d %s  %s" % (r["value"], r["uses"], ("-> var(%s)" % r["token"]) if r["token"] else ("nearest " + r["nearest"] if r["nearest"] else ""), ", ".join(r["files"][:2])))
            print("%d distinct colours; %d css file(s) rewritten" % (len(rows), changed))
            return 0
        if a.cmd == "integrate":
            for line in integrate(a.design, a.repo, a.write):
                print(line)
            return 0
        if a.cmd == "selftest":
            return selftest()
    except (ValueError, FileExistsError, OSError) as e:
        print("error:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
