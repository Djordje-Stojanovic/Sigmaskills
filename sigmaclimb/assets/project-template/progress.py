#!/usr/bin/env python3
"""Draw progress.png from progress.json and results.tsv. An optional project directory selects another chart."""
import csv, json, statistics, sys, textwrap
from pathlib import Path

GRAY, INK = "#b8b8b8", "#555555"
REF = ("AA", "BASELINE")


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load(proj, seg, offset):
    """Rows of one segment, each with its place on the x axis. Numbered passes keep their number; named ones
    sit at the segment start when numbers exist too (set-up runs), else they follow each other."""
    with (proj / seg.get("results", "results.tsv")).open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f, delimiter="\t") if r.get("verdict") != "RECON"]
    numbered = any(num(r["pass"]) is not None for r in rows)
    k = 0
    for r in rows:
        n = num(r["pass"])
        if n is None:
            k += 1
        r["_x"] = offset + (n if n is not None else (0.01 * k if numbered else k))
        r["_local"] = n if n is not None else (0.0 if numbered else k)
    return rows


def draw(proj):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.ticker import MaxNLocator

    cfg = json.loads((proj / "progress.json").read_text(encoding="utf-8"))
    metrics = [{"title": m["key"], "unit": "", "higher": True, **m} for m in cfg["metrics"]]
    segs, offset = [], 0.0
    for s in cfg.get("segments", [{}]):
        rows = load(proj, s, offset)
        s = {"color": "#0b5d7a", "label": "Passes", "who": "", **s}
        s.setdefault("base", {"label": "start", "passes": [r["pass"] for r in rows if r["verdict"] in REF]})
        if "champions" not in s:
            s["champions"] = [{"label": "#" + r["pass"], "passes": [r["pass"]]} for r in rows if r["verdict"] == "KEEP"]
        segs.append({**s, "rows": rows, "by": {r["pass"]: r for r in rows}, "x0": offset, "scale": {}})
        offset = max((r["_x"] for r in rows), default=offset) + 3

    def raw(seg, r, key):
        col = seg.get("columns", {}).get(key, key)
        if not col or r["_local"] < seg.get("from", {}).get(key, -1):
            return None
        return num(r.get(col))

    def med(seg, passes, key, scaled=True):
        v = [raw(seg, seg["by"][p], key) for p in passes if p in seg["by"]]
        v = [x for x in v if x is not None]
        return statistics.median(v) * (seg["scale"].get(key, 1.0) if scaled else 1.0) if v else None

    for s in segs:  # a segment from another machine is scaled onto the segment it continues
        al = s.get("align")
        for m in metrics if al else []:
            want, have = med(segs[al["segment"]], al["passes"], m["key"]), med(s, s["base"]["passes"], m["key"], scaled=False)
            if want and have:
                s["scale"][m["key"]] = want / have

    def gain(b, n, higher):
        return (n / b - 1) * 100 if higher else (b / n - 1) * 100

    def finder(part):  # a summary bar takes the colour and name of the round that found the gain, not of the machine it ran on
        return segs[part.get("found_in", part["segment"])]

    allrows = [r for s in segs for r in s["rows"]]
    tried = sum(1 for r in allrows if r["verdict"] not in REF)
    champs = sum(len(s.get("champions", [])) for s in segs)
    sm = cfg.get("summary")
    cost_panel = any("cost_total" in s or "cost_column" in s for s in segs)
    panels = len(metrics) + int(cost_panel)
    cols = min(2, panels)
    nrows = (panels + cols - 1) // cols
    fig = plt.figure(figsize=(7.5 * cols, 1.8 + 4.1 * nrows + (3 if sm else 0)))
    gs = fig.add_gridspec(nrows + int(bool(sm)), cols, height_ratios=([1.15] if sm else []) + [1] * nrows,
                          hspace=0.45, wspace=0.3)
    fig.suptitle(f"{cfg['title']}: {tried} experiments, {champs} champions", fontsize=17, fontweight="bold")
    if sm:
        ax = fig.add_subplot(gs[0, :])
        labels, y = [], 0
        for m in metrics:
            if m["key"] in sm.get("skip", []):
                continue
            total, left, start = 1.0, 0.0, None
            for part in sm["parts"]:
                seg = segs[part["segment"]]
                b, n = med(seg, part["base"], m["key"], scaled=False), med(seg, part["now"], m["key"], scaled=False)
                if not (b and n):
                    continue
                start = b if start is None else start
                total *= 1 + gain(b, n, m["higher"]) / 100
                ax.barh(y, (total - 1) * 100 - left, left=left, color=finder(part)["color"])
                left = (total - 1) * 100
            if start is None:
                continue
            end = start * total if m["higher"] else start / total
            f = ".0f" if max(start, end) >= 200 else ".1f" if max(start, end) >= 2 else ".2f"
            labels.append(f"{m['title']}\n{start:{f}} -> {end:{f}} {m['unit']}")
            ax.text(left + 0.8, y, f"+{left:.0f}%" if left >= 0 else f"{left:.0f}%", va="center", fontsize=12, fontweight="bold")
            y += 1
        ax.set_yticks(list(range(y)), labels, fontsize=10.5)
        ax.invert_yaxis()
        ax.axvline(0, color="black", lw=0.8)
        ax.margins(x=0.08)
        ax.set_xlabel("% better than the start. Colour = the round that found that gain (see the legend); each part is one machine, same weights, same quality gate")
        ax.set_title(sm["title"] + "      " + "   ".join(f"[{finder(p)['who']}: {finder(p)['label']}]" for p in sm["parts"]), fontsize=13, loc="left")
        ax.grid(axis="x", alpha=0.3)

    xmax = max((r["_x"] for r in allrows), default=0) + 1

    def panel(i):
        return fig.add_subplot(gs[int(bool(sm)) + i // cols, i % cols])

    def decorate(ax, flags=()):
        lo, hi = ax.get_ylim()
        head = 0.28 * (hi - lo)  # headroom above every dot and line: a row of break tags, then a row of champion numbers
        ax.set_ylim(lo, hi + head)
        top = ax.get_ylim()[1]
        for k, (x0, v, text, col) in enumerate(flags):  # a bold number, a dotted guide down to its step; neighbours take turns on two rows
            y = top - (0.5 if k % 2 == 0 else 0.8) * head
            ax.plot([x0, x0], [v, y], color=col, lw=0.8, ls=":", zorder=1)
            ax.text(x0, y, text, fontsize=10, fontweight="bold", color=col, ha="center", va="center", bbox=dict(fc="white", ec="none", pad=0.6))
        for n, s in enumerate(segs):
            if n:
                ax.axvspan(s["x0"] - 1.5, max((r["_x"] for r in s["rows"]), default=s["x0"]) + 1, color=s["color"], alpha=0.07, zorder=0)
                ax.axvline(s["x0"] - 1.5, color=s["color"], lw=1.2, zorder=1)  # the break: a new machine
                if s.get("tag"):  # one short tag per break; the round names are in the legend, once
                    left = s.get("tag_side") == "left"  # the side of the break that has room for the tag
                    ax.text(s["x0"] - 1.5 + (-0.6 if left else 0.6), top, s["tag"], fontsize=8, color=s["color"], va="top", ha="right" if left else "left")
            for mk in s.get("marks", []):
                ax.axvline(s["x0"] + mk["at"], color="#999999", lw=0.8, ls=":")
                ax.text(s["x0"] + mk["at"] + 0.6, top, mk["text"], fontsize=8, color="#777777", va="top")
        ax.grid(alpha=0.25)
        ax.set_xlabel("experiment, in the order it ran")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))  # an experiment number is a whole number

    for i, m in enumerate(metrics):
        ax, key, home, last, flags = panel(i), m["key"], None, None, []
        for s in segs:
            k = s["scale"].get(key, 1.0)
            for r in s["rows"]:
                v = raw(s, r, key)
                if v is None:
                    continue
                if r["verdict"] in REF:  # a ring: the same recipe measured again
                    ax.scatter(r["_x"], v * k, s=30, facecolor="white", edgecolor=INK, linewidth=1.1, zorder=3)
                else:
                    c = s["color"] if r["verdict"] == "KEEP" else GRAY
                    ax.scatter(r["_x"], v * k, s=22 if c == GRAY else 36, color=c, zorder=2 if c == GRAY else 3, edgecolor="white", linewidth=0.4)
            end = max((r["_x"] for r in s["rows"]), default=s["x0"]) + 1
            start = s["x0"] + s.get("from", {}).get(key, 0)
            b = med(s, s["base"]["passes"], key) if s.get("base") else None
            if home is None and b is not None:
                home = (start, b, s["base"]["label"])
            steps = [(start, b, None)] if b is not None else []
            for ch in s.get("champions", []):
                v = med(s, ch["passes"], key)
                xs = [s["by"][p]["_x"] for p in ch["passes"] if p in s["by"] and raw(s, s["by"][p], key) is not None]
                if v is not None and xs:
                    steps.append((min(xs), v, ch["label"]))
            for j, (x0, v, label) in enumerate(steps):
                x1 = steps[j + 1][0] if j + 1 < len(steps) else end
                if label is None:  # the level this segment starts from: the start recipe, or the champion it continues
                    ax.plot([x0, x1], [v, v], color=INK if s is segs[0] else s["color"], lw=2.6 if s is segs[0] else 1.6, ls="--", zorder=4)
                    continue
                ax.plot([x0, x1], [v, v], color=s["color"], lw=2.6, zorder=4)
                if j:
                    ax.plot([x0, x0], [steps[j - 1][1], v], color=s["color"], lw=2.6, zorder=4)
                flags.append((x0, v, label.split()[0].lstrip("#"), s["color"]))  # the number only; the legend names the champions
            if steps and steps[-1][2] is not None:
                last = steps[-1][1]
        if home:
            ax.plot([home[0], xmax], [home[1], home[1]], color=INK, ls="--", lw=1, zorder=1)
            ax.text(xmax + 0.8, home[1], home[2], va="center", fontsize=9, color=INK)
        f = ".2f" if m["unit"] == "fraction" else ".1f"
        g = gain(home[1], last, m["higher"]) if home and home[1] and last else None
        starts = [r["_x"] for s in segs for r in s["rows"] if raw(s, r, key) is not None]
        late = f" (measured from experiment {min(starts):.0f})" if starts and any(key in s.get("from", {}) for s in segs) else ""
        ax.set_title(m["title"] + late + (f"\nnow {last:{f}} {m['unit']} ({'+' if g >= 0 else ''}{g:.0f}% vs {home[2]})" if g is not None else ""), fontsize=11.5, loc="left")
        ax.set_ylabel(m["unit"] + ("" if m["higher"] else "  (lower is better)"))
        decorate(ax, flags)

    # Last panel: money, and how the experiments ended.
    if cost_panel:
        ax, cost, xs, counts = panel(len(metrics)), 0.0, [], {}
        for s in segs:
            per = (s.get("cost_total", 0.0) / len(s["rows"])) if "cost_total" in s and s["rows"] else None
            for r in s["rows"]:
                cost += per if per is not None else (num(r.get(s.get("cost_column", "cost_usd"))) or 0.0)
                xs.append((r["_x"], cost))
                counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        ax.plot([x for x, _ in xs], [c for _, c in xs], color="#d1495b", lw=2)
        ax.set_title(f"Cost of the logged runs: {cost:.2f} USD\n" + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), fontsize=11.5, loc="left")
        ax.set_ylabel("USD")
        decorate(ax)

    # One legend for the rounds, and one key for the champion numbers (each name once).
    handles, keys = [Patch(color=s["color"], label=f"{s['label']}: {s.get('who', '')}") for s in segs], []
    for s in segs:
        for ch in s.get("champions", []):
            if all(ch["label"].split()[0] != k.split()[0] for k in keys):
                keys.append(ch["label"])
    legend = len(segs) > 1 or any(s["who"] for s in segs)
    if legend:
        fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.01, 0.07), ncol=2, frameon=False, fontsize=10.5)
    fig.text(0.01, 0.012 if legend else -0.01, "gray dot = tried   coloured dot = kept   ring = same recipe measured again   line = champion\n"
             + textwrap.fill("champions: " + "   ".join(keys), 150) + ("\n" + textwrap.fill(cfg["note"], 150) if cfg.get("note") else ""), fontsize=10, color="#444444", va="bottom" if legend else "top")
    out = proj / "progress.png"
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print("saved", out)


if __name__ == "__main__":
    try:
        draw(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent)
    except Exception as exc:
        print(f"Warning: progress chart: {exc}", file=sys.stderr)
