"""SigmaDeepLook: which rows to show. Anomalies first, then one row from each tenth of the file, then head and tail; near-duplicates dropped.

A uniform random sample shows what is normal and misses the one row that matters. The profile already knows where the odd rows are
(first non-matching cell, the maximum, the first repeated key, the first negative); this module fetches exactly those rows with a
second cheap pass, labels each with its reason, and fills the rest with a stratified sample so every part of the file is represented.
"""
import csv
import io

import dl_util as U
from dl_data import ID_NAME_RE


def md_cell(c):
    return str(c).replace("|", "\\|").replace("\n", " ")[:60]


def anomaly_lines(prof, repeats, dominant_skip=("empty", "null-token")):
    """-> {line_number: reason} from the column profiles (first line of each oddity). Earliest reason wins per line."""
    want = {}

    def add(line, why):
        if line and line not in want:
            want[line] = why
    for ln in repeats[:2]:
        add(ln, "repeated header")
    for p in prof:
        dom = p.dominant()
        for kind, line in sorted(p.first_line.items(), key=lambda kv: kv[1]):
            if kind != dom and kind not in dominant_skip and p.kinds[kind] <= max(5, sum(p.kinds.values()) // 20):
                add(line, f"{p.name}: {kind}")
        if p.lo is not None and p.hi is not None and p.pct(0.99) is not None and p.hi > 20 * max(1.0, abs(p.pct(0.99))):
            add(p.hi_line, f"{p.name}: maximum {p.hi:.12g}")
        if p.neg_line and p.neg <= max(5, sum(p.kinds.values()) // 20):
            add(p.neg_line, f"{p.name}: negative")
        if p.dup_line and p.dup <= max(5, sum(p.kinds.values()) // 20) and (p is prof[0] or ID_NAME_RE.search(p.name or "")):
            add(p.dup_line, f"{p.name}: repeated key")
    return want


def fetch(text, delim, n_cols, line_targets, idx_targets, line_off=0):
    """Second pass: rows whose line number or row index is wanted. -> {key: record}, key = ('line', n) or ('idx', i)."""
    got = {}
    need_l, need_i = set(line_targets), set(idx_targets)
    rd = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    i = -1
    first = True
    for rec in rd:
        if first:
            first = False
            continue
        if len(rec) != n_cols:
            continue
        i += 1
        ln = rd.line_num + line_off
        if ln in need_l:
            got[("line", ln)] = rec
            need_l.discard(ln)
        if i in need_i:
            got[("idx", i)] = rec
            need_i.discard(i)
        if not need_l and not need_i:
            break
    return got


def build_sample(look, text, delim, header, prof, rows_n, repeats, tail, rows_head, partial=False, max_anomaly=14, line_off=0):
    """Write sample.md and return nothing. Rows: anomalies (with reason), strata, head, tail."""
    lines = anomaly_lines(prof, repeats)
    line_targets = dict(list(lines.items())[:max_anomaly])
    plan = U.sample_plan(rows_n, anomalies=(), head=3, tail=3, strata=10)
    idx_targets = {i: lab for i, lab in plan}
    got = {} if partial else fetch(text, delim, len(header), set(line_targets), set(idx_targets), line_off)
    table_head = "| why | " + " | ".join(header) + " |\n|---|" + "---|" * len(header) + "\n"
    out_rows = []
    seen = set()
    for ln, why in line_targets.items():
        rec = got.get(("line", ln))
        if rec is None and repeats and ln in repeats:
            rec = header
        if rec is not None:
            out_rows.append((f"line {ln}: {why}", rec))
            seen.add(tuple(rec))
    strat = []
    for i, lab in plan:
        rec = got.get(("idx", i))
        if rec is None and i < len(rows_head):
            rec = rows_head[i]
        if rec is not None and tuple(rec) not in seen:
            strat.append((lab, rec))
            seen.add(tuple(rec))
    kept, dropped = U.dedupe_text(strat, ratio=96, key=lambda x: " ".join(x[1]))
    out_rows += kept
    if tail:
        for rec in tail[-3:]:
            if tuple(rec) not in seen:
                out_rows.append(("tail", rec))
                seen.add(tuple(rec))
    body = table_head + "\n".join("| " + w.replace("|", "/") + " | " + " | ".join(md_cell(c) for c in r) + " |" for w, r in out_rows)
    note = f"\n\n{len(line_targets)} anomaly row(s) first, then one row from each tenth of the {rows_n} rows" + (f" ({dropped} near-duplicate dropped)" if dropped else "") + ", then head and tail. Row reasons come from the full-file profile."
    look.write_text("sample.md", body + note + "\n", "rows worth reading: the odd ones first (with why), one per tenth of the file, head and tail", value=7, slice_cmd="--sql \"SELECT ... FROM t\"")
