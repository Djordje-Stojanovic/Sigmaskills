"""plot_progress.py - draws progress.png from results.tsv and state/champion.json. The owner looks at it.
Run it at a KEEP and at the end, not after every pass. A chart failure never stops a pass: it warns and exits 0."""
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
KEEP, BAD, GRAY, BASE = "#2ecc71", "#e74c3c", "#b0b0b0", "#3498db"


def colours(df):
    return [KEEP if v == "KEEP" else BASE if v in ("BASELINE", "AA") else BAD if v in ("CRASH", "VOID") else GRAY
            for v in df["verdict"]]


def p_chain(ax, champ, machine):
    """Each champion against the start, back to the first baseline, labelled with who found it."""
    hist = champ.get("history", [])
    xs, ys = [0] + list(range(1, len(hist) + 1)), [1.0] + [h["vs_start"] or 1.0 for h in hist]
    ax.step(xs, ys, where="post", color=KEEP, lw=2)
    for i, h in enumerate(hist, start=1):
        ax.annotate(f"#{i} {h.get('who') or '?'}" + (" (owner's word)" if h.get("owner") else ""), (i, ys[i]),
                    fontsize=7, rotation=20, xytext=(3, 3), textcoords="offset points")
    ax.axhline(1.0, color="k", lw=.6, ls=":")
    ax.set_title(f"champions against the start (1.0 = start; higher is better), measured on {machine}", fontsize=9)
    ax.grid(alpha=.2)


def p_vs_champion(ax, df):
    m = df["vs_champion"].notna()
    ax.scatter(df.index[m], df["vs_champion"][m], c=[c for c, k in zip(colours(df), m) if k], s=30, zorder=3)
    ax.axhline(1.0, color="k", lw=.6, ls=":")
    ax.set_title("each pass against the champion before it (gray = tried, green = kept)", fontsize=9)
    ax.grid(alpha=.2)


def p_probe(ax, df, name, lower):
    vals = df["probes"].fillna("").map(lambda s: dict(x.split("=") for x in s.split() if "=" in x).get(name))
    vals = vals.astype(float)
    m = vals.notna()
    ax.scatter(df.index[m], vals[m], c=[c for c, k in zip(colours(df), m) if k], s=24, zorder=3)
    ax.set_title(f"{name} ({'lower' if lower else 'higher'} is better)", fontsize=9)
    ax.grid(alpha=.2)


def p_loop(ax, df):
    ax.bar(df.index, df["minutes"].fillna(0), color=colours(df))
    ax2 = ax.twinx()
    ax2.plot(df.index, df["score_share"] * 100, color=BASE, lw=1.5)
    ax2.axhline(50, color=BASE, lw=.6, ls=":")
    ax2.set_ylabel("% of the pass that measures the score", fontsize=7)
    ax.set_title("minutes per pass (bars) and the share that measures the score (line; keep it above 50 %)", fontsize=9)


def render(out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    df = pd.read_csv(os.path.join(ROOT, "results.tsv"), sep="\t")
    if df.empty:
        print("no data yet")
        return
    for c in ("vs_champion", "vs_start", "minutes", "score_share"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    proj = json.load(open(os.path.join(ROOT, "project.json"), encoding="utf-8"))
    cp = os.path.join(ROOT, "state", "champion.json")
    champ = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}
    top = sorted(proj.get("weights", {}), key=lambda k: -proj["weights"][k])[:4]
    fig, axes = plt.subplots(4, 2, figsize=(16, 18), constrained_layout=True)
    fig.suptitle(f"{proj.get('name', 'climb')}: {len(df)} passes, {len(champ.get('history', []))} champions",
                 fontweight="bold")
    panels = [lambda a: p_chain(a, champ, proj.get("machine", "?")), lambda a: p_vs_champion(a, df)]
    panels += [lambda a, k=k: p_probe(a, df, k, k in proj.get("lower_is_better", [])) for k in top]
    panels += [lambda a: p_loop(a, df)]
    for a, f in zip(axes.flat, panels):
        try:
            f(a)
        except Exception as e:  # one broken panel never kills the chart
            a.set_title(f"panel unavailable: {e}", fontsize=8)
    fig.savefig(out, dpi=120)
    print(f"saved {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "progress.png"))
    args = ap.parse_args()
    try:
        render(args.out)
    except Exception as e:
        print(f"WARNING: chart failed ({e}) - pass continues")
    sys.exit(0)
