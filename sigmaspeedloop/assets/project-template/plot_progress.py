"""plot_progress.py - draws progress.png from results.tsv. The human looks at it; the worker only runs it.
A chart failure never stops a pass: it prints a warning and exits 0."""
import argparse, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
KEEP, BAD, GRAY, BASE = "#2ecc71", "#e74c3c", "#b0b0b0", "#3498db"
# metric column, label, higher is better
SPEED = [("replay_wall_s", "agent replay wall time (s)", False),
         ("decode_tps", "short decode tok/s, 1 stream (low/medium, T=1)", True),
         ("prefill_tps_64k", "prefill tok/s at 64k", True),
         ("c3_tps", "3 parallel requests, total tok/s", True)]
CAVEAT = "Vast.ai GB10 box, not the home Spark. Gray = tried, green = kept, blue = baseline / A-A."


def load():
    import pandas as pd
    df = pd.read_csv(os.path.join(ROOT, "results.tsv"), sep="\t")
    for c in df.columns:
        if c not in ("utc", "parent", "idea_id", "category", "work_type", "image", "verdict", "description"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.reset_index(drop=True)


def colours(df):
    return [KEEP if v == "KEEP" else BASE if v in ("BASELINE", "AA") else BAD if v in ("CRASH", "VOID") else GRAY
            for v in df["verdict"]]


def p_score(ax, df):
    m = df["score"].notna()
    ax.scatter(df.index[m], df["score"][m], c=[c for c, k in zip(colours(df), m) if k], s=30, zorder=3)
    kept = df[(df["verdict"] == "KEEP") & df["description"].astype(str).str.contains("PROMOTED")]
    if not kept.empty:
        # only promotions count (a KEEP and its confirmation run measure the same change once);
        # score is relative to the champion at the time, so the cumulative product is the gain over the first baseline
        cum = kept["score"].cumprod()
        ax.step(kept.index, cum, where="post", color=KEEP, lw=2, label="cumulative gain vs first baseline")
        for i, r in kept.iterrows():
            ax.annotate(str(r["idea_id"])[:24], (i, cum[i]), fontsize=6, rotation=20, xytext=(3, 3),
                        textcoords="offset points")
        ax.legend(fontsize=7)
    ax.axhline(1.0, color="k", lw=.6, ls=":")
    ax.set_title("speed score vs champion (1.0 = same; higher is better)")
    ax.grid(alpha=.2)


def p_discovery(ax, df):
    wins = (df["verdict"] == "KEEP").cumsum()
    ax.plot(df.index, wins, color=KEEP, lw=2)
    tail = wins.iloc[-20:]
    slope = (tail.iloc[-1] - tail.iloc[0]) / max(len(tail) - 1, 1) if len(tail) else 0
    ax.text(.02, .92, f"last 20 passes: {slope:.2f} keeps/pass", transform=ax.transAxes, fontsize=8)
    ax.set_title("discovery curve (flat = escalate: new category or research)")
    ax.grid(alpha=.2)


def p_metric(ax, df, col, label, higher):
    if col not in df or df[col].notna().sum() == 0:
        ax.set_title(f"{label}: no data yet", fontsize=9)
        return
    m = df[col].notna()
    ax.scatter(df.index[m], df[col][m], c=[c for c, k in zip(colours(df), m) if k], s=24, zorder=3)
    best_rows = df[m & df["verdict"].isin(["KEEP", "BASELINE"])]
    if not best_rows.empty:
        ax.step(best_rows.index, best_rows[col], where="post", color=KEEP, lw=1.5)
    ax.set_title(f"{label} ({'higher' if higher else 'lower'} is better)", fontsize=9)
    ax.grid(alpha=.2)


def p_gate(ax, df):
    if df["gate_top1"].notna().sum() == 0:
        ax.set_title("quality gate: no data yet", fontsize=9)
        return
    m = df["gate_top1"].notna()
    ax.scatter(df.index[m], df["gate_top1"][m] * 100, c=[c for c, k in zip(colours(df), m) if k], s=24)
    aa = df[df["verdict"] == "AA"]["gate_top1"].dropna()
    if not aa.empty:
        ax.axhspan(aa.min() * 100, 100, color=BASE, alpha=.12, label="A/A band (normal restart drift)")
        ax.legend(fontsize=7)
    ax.set_title("quality gate: top-1 agreement with baseline % (must stay in the band)", fontsize=9)
    ax.grid(alpha=.2)


def p_time(ax, df):
    if df["minutes"].notna().sum():
        ax.bar(df.index, df["minutes"].fillna(0), color=colours(df))
        ax2 = ax.twinx()
        ax2.plot(df.index, df["cost_usd"].fillna(0).cumsum(), color=BAD, lw=1.5)
        ax2.set_ylabel("cumulative $", fontsize=7)
    ax.set_title("minutes per pass (bars) + cumulative cost (line)", fontsize=9)


def render(out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    df = load()
    if df.empty:
        print("no data yet")
        return
    fig, axes = plt.subplots(4, 2, figsize=(16, 18), constrained_layout=True)
    ax = list(axes.flat)
    kept = int((df["verdict"] == "KEEP").sum())
    fig.suptitle(f"la125 speed loop: {len(df)} passes, {kept} kept\n{CAVEAT}", fontweight="bold")
    panels = [lambda a: p_score(a, df), lambda a: p_discovery(a, df)]
    panels += [lambda a, s=s: p_metric(a, df, *s) for s in SPEED]
    panels += [lambda a: p_gate(a, df), lambda a: p_time(a, df)]
    for a, f in zip(ax, panels):
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
