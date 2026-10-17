"""SigmaDeepLook: logs and subtitles (timestamped text that is too long to read).

Logs: a streaming pass, Drain template mining (dl_util.Drain, stdlib), per-minute volume, levels, bursts and gaps, rare templates,
the first error and what came just before it. Subtitles: srt, vtt, ass/ssa, sbv, lrc parsed with the standard library; formats that
need pysubs2 (MicroDVD, SAMI, TTML) become a Not-looked-at row until it is installed.
"""
import csv
import io
import re
import statistics
from collections import Counter
from datetime import datetime, timezone

import dl_core as core
import dl_util as U

LOG_LINES_STANDARD = 3_000_000
LOG_LINES_DEEP = 20_000_000
LOG_SECONDS = 45.0
LEVELS = ("TRACE", "DEBUG", "INFO", "NOTICE", "WARN", "ERROR", "CRIT", "FATAL")
LEVEL_RE = re.compile(r"\b(TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERR(?:OR)?|CRIT(?:ICAL)?|FATAL|SEVERE|PANIC)\b")
LEVEL_MAP = {"TRACE": "TRACE", "DEBUG": "DEBUG", "INFO": "INFO", "NOTICE": "NOTICE", "WARN": "WARN", "WARNING": "WARN", "ERR": "ERROR", "ERROR": "ERROR",
             "SEVERE": "ERROR", "CRIT": "CRIT", "CRITICAL": "CRIT", "FATAL": "FATAL", "PANIC": "FATAL"}
BAD = {"ERROR", "CRIT", "FATAL"}
ISO_RE = re.compile(r"(\d{4})[-/](\d{2})[-/](\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:[.,](\d{1,6}))?\s*(Z|[+-]\d{2}:?\d{2})?")
SYS_RE = re.compile(r"\b([A-Z][a-z]{2})\s+(\d{1,2})\s(\d{2}):(\d{2}):(\d{2})\b")
APACHE_RE = re.compile(r"\[(\d{2})/([A-Z][a-z]{2})/(\d{4}):(\d{2}):(\d{2}):(\d{2})\s*([+-]\d{4})?\]")
EPOCH_RE = re.compile(r"^\s*(\d{10})(?:\.(\d+))?\s")
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
LIB_FRAME_RE = re.compile(r"site-packages|node_modules|[\\/]lib[\\/]python|\bjava\.|\bjavax\.|\bjdk\.|\bsun\.|org\.springframework|org\.apache|<frozen|importlib|asyncio|threading\.py|/usr/lib|runtime\.", re.I)
TRACE_KEEP = 3          # in-app frames shown per error template
TRACE_LINES = 60        # continuation lines remembered per error template (the first occurrence only)
CONT_RE = re.compile(r"^(\s+at\s|\s+\.\.\.\s\d+\smore|Caused by:|\s+File \"|Traceback \(|\s{4,}\S)")


def parse_ts(line, year_hint):
    """-> (epoch seconds UTC, match end) or (None, 0). Naive times are taken as UTC (the look compares lines with each other only)."""
    m = ISO_RE.search(line[:60])
    if m:
        y, mo, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))
        try:
            dt = datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)
        except ValueError:
            return None, 0
        t = dt.timestamp() + (int((m.group(7) or "0").ljust(6, "0")[:6]) / 1e6)
        z = m.group(8)
        if z and z != "Z":
            sign = 1 if z[0] == "+" else -1
            hh, mm = int(z[1:3]), int(z[-2:])
            t -= sign * (hh * 3600 + mm * 60)
        return t, m.end()
    m = APACHE_RE.search(line[:80])
    if m and m.group(2) in MONTHS:
        try:
            dt = datetime(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)), int(m.group(4)), int(m.group(5)), int(m.group(6)), tzinfo=timezone.utc)
        except ValueError:
            return None, 0
        return dt.timestamp(), m.end()
    m = SYS_RE.search(line[:40])
    if m and m.group(1) in MONTHS:
        try:
            dt = datetime(year_hint, MONTHS[m.group(1)], int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), tzinfo=timezone.utc)
        except ValueError:
            return None, 0
        return dt.timestamp(), m.end()
    m = EPOCH_RE.match(line)
    if m and 946684800 <= int(m.group(1)) <= 4102444800:
        return float(m.group(1)), m.end()
    return None, 0


def fmt_ts(t):
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def clock(t, day0=None):
    """Time of day with milliseconds when the line has them (05:30:45.785); the date is added when it differs from the first day of the log."""
    d = datetime.fromtimestamp(t, tz=timezone.utc)
    ms = f".{int(t % 1 * 1000):03d}" if abs(t % 1) > 0.0005 else ""
    day = "" if day0 is None or d.date() == day0 else d.strftime("%Y-%m-%d ")
    return day + d.strftime("%H:%M:%S") + ms


def span_text(sec):
    sec = int(sec)
    if sec >= 86400:
        return f"{sec / 86400:.1f} days"
    if sec >= 3600:
        return f"{sec / 3600:.1f} h"
    if sec >= 60:
        return f"{sec / 60:.0f} min"
    return f"{sec} s"


def scan_log(path, max_lines, max_seconds):
    """Stream the file. -> dict with records (as small tuples), drain, per-minute counts, timestamps, flags."""
    import time
    t0 = time.time()
    year = datetime.now(timezone.utc).year
    drain = U.Drain()
    minutes = Counter()
    levels = Counter()
    recs = []      # (line_no, ts or None, level or None, template cluster)
    first_ts = last_ts = None
    backwards = []
    prev_ts = None
    n = untimed = 0
    first_cont = None
    cur = None
    partial = False
    with open(path, "rb") as f:
        for ln, raw in enumerate(f, 1):
            n = ln
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if not line.strip():
                continue
            if ln % 20000 == 0 and time.time() - t0 > max_seconds or ln > max_lines:
                partial = True
                break
            ts, end = parse_ts(line, year)
            if ts is None:
                untimed += 1
                if cur is not None and cur.get("level") in BAD and cur["count"] == 1 and CONT_RE.match(line) and len(cur.setdefault("trace", [])) < TRACE_LINES:
                    cur["trace"].append(line.rstrip())
                if cur is None and first_cont is None and CONT_RE.match(line):
                    first_cont = ln
                continue
            lm = LEVEL_RE.search(line[end:end + 40]) or LEVEL_RE.search(line[:200])
            lvl = LEVEL_MAP.get(lm.group(1)) if lm else None
            body = line[end:]
            c = drain.add(body, ln)
            if prev_ts is not None and ts < prev_ts - 1.0:
                if len(backwards) < 5:
                    backwards.append((ln, prev_ts, ts))
            prev_ts = ts
            first_ts = ts if first_ts is None else min(first_ts, ts)
            last_ts = ts if last_ts is None else max(last_ts, ts)
            minutes[int(ts // 60)] += 1
            if lvl:
                levels[lvl] += 1
            if c is not None and lvl and "level" not in c:
                c["level"] = lvl
            if c is not None:
                if "t0" not in c or ts < c["t0"]:
                    c["t0"] = ts
                if ts > c.get("t1", ts - 1):
                    c["t1"] = ts
            if len(recs) < 400000:
                recs.append((ln, ts, lvl, c))
            cur = c
    return {"lines": n, "untimed": untimed, "recs": recs, "drain": drain, "minutes": minutes, "levels": levels, "first": first_ts, "last": last_ts,
            "backwards": backwards, "first_cont": first_cont, "partial": partial, "timed": sum(minutes.values())}


def fold_trace(lines, keep=TRACE_KEEP):
    """A stack trace as the reader needs it: the cause lines and the first `keep` frames of the app's own code, the rest counted.
    (Sentry groups by in-app frames only; frames of libraries and the runtime differ without meaning anything.)"""
    if not lines:
        return ""
    causes = [l.strip() for l in lines if l.strip().startswith(("Caused by", "Traceback"))][:3]
    frames = [l for l in lines if re.match(r"\s+(File |at )", l)]   # a Python frame's source line (4 spaces, code) is not a frame
    app = [l for l in frames if not LIB_FRAME_RE.search(l)]
    shown = [l.strip() for l in app[:keep]]
    hidden = len(frames) - len(shown)
    out = causes[:1] + shown + causes[1:]
    if hidden > 0:
        out.append(f"... {hidden} more frame(s), {len(frames) - len(app)} of them library code")
    return "\n".join("    " + x for x in out)


def look_log(look):
    if look.subtype == "evtx":
        import dl_adapt
        return dl_adapt.look_evtx(look)
    r = scan_log(look.path, LOG_LINES_DEEP if look.deep else LOG_LINES_STANDARD, 120.0 if look.deep else LOG_SECONDS)
    timed = r["timed"]
    look.fact("lines", r["lines"])
    look.fact("timed_records", timed)
    if not timed:
        look.line(f"Text log without recognisable timestamps: {r['lines']} lines.", 90)
        look.skip("timeline, bursts and gaps", "no timestamp format found (ISO, syslog, Apache or epoch)")
        look.excerpt("First lines", "\n".join(open(look.path, "r", encoding="utf-8", errors="replace").read(3000).splitlines()[:10]), 10, 800, 60)
        return
    first, last = r["first"], r["last"]
    span = last - first
    look.fact("first", fmt_ts(first))
    look.fact("last", fmt_ts(last))
    mins = r["minutes"]
    look.headline = f"log, {U.compact(r['lines'])} lines over {span_text(span)}, {fmt_ts(first)} to {fmt_ts(last)}"
    lv = ", ".join(f"{k} {U.compact(v)}" for k, v in sorted(r["levels"].items(), key=lambda kv: LEVELS.index(kv[0]) if kv[0] in LEVELS else 9))
    nb = min(30, max(1, len(range(min(mins), max(mins) + 1))))
    series = [mins.get(m, 0) for m in range(min(mins), max(mins) + 1)]
    spark = U.sparkline(series, nb)
    look.line(f"{U.compact(r['lines'])} lines ({U.compact(timed)} timed records), {fmt_ts(first)} to {fmt_ts(last)} ({span_text(span)}); levels: {lv or 'none found'}", 95)
    look.line(f"Volume per time bucket: {spark} (peak {U.compact(max(series))} records/min, median {U.compact(U.median([x for x in series if x]))})", 92)
    look.dims = f"{U.compact(r['lines'])} lines"
    # templates
    clusters = sorted(r["drain"].clusters, key=lambda c: -c["count"])
    look.fact("templates", len(clusters))
    day0 = datetime.fromtimestamp(first, tz=timezone.utc).date()
    quiet = [c for c in clusters if c.get("level") not in BAD and c.get("level") != "WARN"]
    top = quiet[:5]
    rows = [f"{U.compact(c['count'])}x [{c.get('level', '-')}] {Drain_t(c)[:110]}" for c in top]
    look.line(f"{len(clusters)} message templates; most frequent:\n" + "\n".join("  " + x for x in rows), 80, "templates")
    loud = [c for c in clusters if c.get("level") in BAD or c.get("level") == "WARN"]
    if loud:
        def trow(c):
            tpl = Drain_t(c)[:110]
            ex = "" if "<*>" not in tpl else f"; e.g. {c['example'][:70]}"
            when = clock(c["t0"], day0) + (f" to {clock(c['t1'], day0)}" if c["t1"] > c["t0"] else "") if "t0" in c else ""
            return f"{U.compact(c['count'])}x [{c.get('level')}] {tpl} | {when} | lines {c['first']}-{c['last']}{ex}"
        look.line("Warning and error templates, with count, first and last time:\n" + "\n".join("  " + trow(c) for c in loud[:6]), 93, "errors")
    # first error and what came before
    bad = [(ln, ts, c) for ln, ts, lvl, c in r["recs"] if lvl in BAD]
    if bad:
        ln, ts, c = bad[0]
        look.fact("first_error", f"line {ln} at {fmt_ts(ts)}: {c['example'][:120].strip()}")
        look.fact("errors", len(bad))
        burst = error_burst(r["recs"], bad, span)
        anchor_ln, anchor_ts, what = (burst["line"], burst["start"], "error burst") if burst else (ln, ts, "first error")
        if burst:
            c0 = burst["cluster"]
            look.flag("ERROR-BURST", clock(burst["start"], day0),
                      f"{burst['n']}x [{c0.get('level')}] {Drain_t(c0)[:90]}, {clock(burst['start'], day0)} to {clock(burst['end'], day0)} ({burst['end'] - burst['start']:.0f} s), "
                      f"lines {burst['line']}-{burst['last_line']}; its usual rate is {burst['usual']:.1f} per minute",
                      "an incident: the start time is the anchor, read what came just before it")
            look.fact("error_burst_start", fmt_ts(burst["start"]))
        near = [(l2, t2, lv2, c2) for l2, t2, lv2, c2 in r["recs"] if anchor_ts - 120 <= t2 < anchor_ts and l2 < anchor_ln]
        odd = [(l2, t2, lv2, c2) for l2, t2, lv2, c2 in near if c2 is not None and (c2["count"] <= 2 or lv2 in ("WARN",))]
        seen = set()
        pre = []
        for l2, t2, lv2, c2 in odd:
            if id(c2) not in seen:
                seen.add(id(c2))
                pre.append((l2, t2, lv2, c2))
        if pre:
            l2, t2, lv2, c2 = pre[-1]   # the one closest to the anchor
            look.flag("ROOT-CAUSE-EARLIER?", f"{clock(t2, day0)}, line {l2}",
                      f"[{lv2 or '-'}] {c2['example'][:110]} - {anchor_ts - t2:.0f} s before the {what} at {clock(anchor_ts, day0)}" + (f" (+{len(pre) - 1} more rare or WARN line(s))" if len(pre) > 1 else ""),
                      "the loudest error is usually a symptom; read what came first")
    # bursts and gaps
    nz = [x for x in series if x]
    med = U.median(nz) if nz else 0
    if med >= 1:
        bursts = [(m, c) for m, c in mins.items() if c > 5 * med and c >= 20]
        if bursts:
            bursts.sort(key=lambda mc: -mc[1])
            m0, c0 = bursts[0]
            look.flag("BURST", fmt_ts(m0 * 60), f"{U.compact(c0)} records in one minute vs median {U.compact(med)}; {len(bursts)} such minute(s)", "a spike: an incident, a retry storm or a batch job")
    ts_list = sorted(t for _, t, _, _ in r["recs"])
    if len(ts_list) > 20:
        gaps = [(b - a, a) for a, b in zip(ts_list, ts_list[1:])]
        mg = U.median([g for g, _ in gaps])
        big = [(g, a) for g, a in gaps if g > max(60.0, 10 * max(mg, 0.001))]
        if big:
            big.sort(reverse=True)
            look.flag("GAP", fmt_ts(big[0][1]), f"{span_text(big[0][0])} without a record ({len(big)} gap(s) over {span_text(max(60.0, 10 * mg))})", "silence: a restart, an outage or logging that stopped")
    if r["backwards"]:
        ln, a, b = r["backwards"][0]
        look.flag("TIME-BACKWARDS", f"line {ln}", f"{len(r['backwards'])}+ time(s): {fmt_ts(a)} then {fmt_ts(b)}", "two sources merged or a clock jump: do not trust the order")
    if r["first_cont"] == 1 or (r["first_cont"] and r["first_cont"] <= 3):
        look.flag("ROTATED-MID-TRACE", f"line {r['first_cont']}", "the file starts inside a stack trace", "log rotated mid-incident: the beginning is in the previous file")
    if r["partial"]:
        look.flag("PARTIAL", "scan", f"stopped at line {r['lines']}", "counts are lower bounds; the time cap was reached")
    head = open(look.path, "r", encoding="utf-8", errors="replace").read(8000)
    if ISO_RE.search(head) and not re.search(r"\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(Z|[+-]\d{2}:?\d{2})", head):
        look.flag("NO-TIMEZONE", "timestamps", "no zone on the timestamps", "compare with other systems only after finding the zone")
    # rare templates
    rare = [c for c in r["drain"].clusters if c["count"] <= 2][:5]
    rare_quiet = [c for c in rare if c.get("level") not in BAD and c.get("level") != "WARN"]   # warnings and errors are already in the template list
    if rare_quiet:
        look.line("Rare lines (templates seen once or twice):\n" + "\n".join(f"  line {c['first']} at {clock(c['t0'], day0)}: {c['example'][:110]}" for c in rare_quiet), 40, "rare")
    # artifacts
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["count", "level", "first_line", "last_line", "template"])
    for c in clusters[:5000]:
        w.writerow([c["count"], c.get("level", ""), c["first"], c["last"], Drain_t(c)])
    look.write_text("templates.csv", buf.getvalue(), "every message template: count, level, first and last line", value=4, inline=False)
    errs = [c for c in clusters if c.get("level") in BAD][:40]
    if errs:
        look.write_text("errors.md", "\n\n".join(f"### {U.compact(c['count'])}x {c.get('level')} (lines {c['first']}-{c['last']}, {clock(c['t0'], day0)} to {clock(c['t1'], day0)})\n{c['example']}" + ("\n" + fold_trace(c.get("trace")) if c.get("trace") else "") for c in errs),
                        "each error template once with its times, an example line and a folded stack trace", value=7, inline=True if any(c.get("trace") for c in errs) else False)
    if rare:
        look.write_text("rare.md", "\n".join(f"line {c['first']} at {clock(c['t0'], day0)}: {c['example']}" for c in clusters if c["count"] <= 2)[:60000], "templates seen once or twice, with their line and time", value=4, inline=False)
    tl = io.StringIO()
    tw = csv.writer(tl)
    tw.writerow(["minute_utc", "records"])
    for m in range(min(mins), max(mins) + 1):
        if mins.get(m):
            tw.writerow([fmt_ts(m * 60), mins[m]])
    look.write_text("timeline.csv", tl.getvalue(), "records per minute", value=2, inline=False)
    look.cmd('--grep "REGEX"', "search templates and errors (raw lines around a time: grep the file for its timestamp)", None)
    look.step("log scan, Drain templates, bursts and gaps", "stdlib")


def error_burst(recs, bad, log_span, window=60.0):
    """The sharpest burst of one error template: the 60 s window holding far more of its lines than its usual rate predicts.
    -> dict(cluster, n, start, end, line, last_line, usual) or None. (A volume spike per minute is the BURST flag; this finds a burst of a rare error in a flat log.)"""
    by = {}
    for ln, ts, c in bad:
        if c is not None:
            by.setdefault(id(c), (c, []))[1].append((ts, ln))
    best = None
    for c, pts in by.values():
        if len(pts) < 8:
            continue
        pts.sort()
        usual = len(pts) * window / max(log_span, window)   # the rate if the template were spread over the whole log
        j = 0
        top = (0, 0, 0)
        for i in range(len(pts)):
            while pts[i][0] - pts[j][0] > window:
                j += 1
            if i - j + 1 > top[0]:
                top = (i - j + 1, j, i)
        n, a, b = top
        if n >= 8 and n >= 5 * usual and n >= 0.3 * len(pts):
            score = n / max(usual, 0.05)
            if best is None or score > best[0]:
                best = (score, dict(cluster=c, n=n, start=pts[a][0], end=pts[b][0], line=min(x[1] for x in pts[a:b + 1]), last_line=max(x[1] for x in pts[a:b + 1]), usual=usual))
    return best[1] if best else None


def Drain_t(c):
    return U.Drain.template(c)


# ================================================================= subtitles
CUE_SRT = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")
CUE_VTT = re.compile(r"(?:(\d{1,2}):)?(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(?:(\d{1,2}):)?(\d{2}):(\d{2})\.(\d{3})")
TAGS = re.compile(r"<[^>]+>|\{\\[^}]*\}")


def hms(h, m, s, ms):
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000


def parse_cues(text, kind, numbers=None):
    """-> list of (start, end, text). Standard library only. `numbers`, when a list, receives the cue number written in the file (else the position)."""
    cues = []
    if kind in ("srt", "vtt", "sbv"):
        if kind == "sbv":
            blocks = re.split(r"\r?\n\r?\n", text.strip())
            for b in blocks:
                lines = b.splitlines()
                m = re.match(r"(\d+):(\d{2}):(\d{2})\.(\d{3}),(\d+):(\d{2}):(\d{2})\.(\d{3})", lines[0]) if lines else None
                if m:
                    g = m.groups()
                    cues.append((hms(g[0], g[1], g[2], g[3]), hms(g[4], g[5], g[6], g[7]), " ".join(lines[1:])))
            return cues
        rx = CUE_SRT if kind == "srt" else CUE_VTT
        for b in re.split(r"\r?\n\r?\n", text.strip()):
            lines = [x for x in b.splitlines()]
            for i, ln in enumerate(lines):
                m = rx.search(ln)
                if m:
                    g = m.groups()
                    cues.append((hms(g[0], g[1], g[2], g[3]), hms(g[4], g[5], g[6], g[7]), "\n".join(lines[i + 1:])))
                    if numbers is not None:
                        numbers.append(int(lines[i - 1]) if i and lines[i - 1].strip().isdigit() else len(cues))
                    break
        return cues
    if kind == "ass":
        fmt = None
        for ln in text.splitlines():
            if ln.startswith("Format:") and "Start" in ln and "Text" in ln:
                fmt = [x.strip() for x in ln[7:].split(",")]
            elif ln.startswith("Dialogue:") and fmt:
                parts = ln[9:].split(",", len(fmt) - 1)
                d = dict(zip(fmt, [p.strip() for p in parts]))
                try:
                    def t(v):
                        h, m, s = v.split(":")
                        return int(h) * 3600 + int(m) * 60 + float(s)
                    cues.append((t(d["Start"]), t(d["End"]), d.get("Text", "").replace("\\N", "\n")))
                except (KeyError, ValueError):
                    continue
        return cues
    if kind == "lrc":
        pts = []
        for ln in text.splitlines():
            m = re.match(r"\[(\d{2}):(\d{2})[.:](\d{2,3})\](.*)", ln)
            if m:
                pts.append((int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3).ljust(3, "0")[:3]) / 1000, m.group(4).strip()))
        for i, (t, tx) in enumerate(pts):
            cues.append((t, pts[i + 1][0] if i + 1 < len(pts) else t + 4, tx))
    return cues


def look_subtitle(look):
    raw = look.path.read_bytes()[:20_000_000]
    text, enc = core.decode_text(raw)
    if text is None:
        look.flag("ENCODING", "file", "not text", "")
        return
    text = text.lstrip("﻿")
    kind = look.subtype
    nums = []
    cues = parse_cues(text, kind, nums)
    if not cues:
        look.line(f"{kind} subtitle file, no cues could be parsed.", 90)
        look.skip("subtitle cues of this format", "format not covered by the built-in parser", "pysubs2")
        return
    nums = nums if len(nums) == len(cues) else list(range(1, len(cues) + 1))
    look.fact("cues", len(cues))
    start, end = min(c[0] for c in cues), max(c[1] for c in cues)
    plain = [TAGS.sub("", c[2]).strip() for c in cues]
    cps = [len(re.sub(r"\s+", "", p)) / max(0.2, c[1] - c[0]) for c, p in zip(cues, plain)]
    p95 = sorted(cps)[min(len(cps) - 1, int(0.95 * len(cps)))] if cps else 0
    over17 = sum(1 for x in cps if x > 17)
    over21 = sum(1 for x in cps if x > 21)
    short = sum(1 for c in cues if 0 <= c[1] - c[0] < 0.8)
    inverted = [i for i, c in enumerate(cues) if c[1] < c[0] - 0.001]
    overlaps = [i + 1 for i, (a, b) in enumerate(zip(cues, cues[1:])) if b[0] < a[1] - 0.001 and a[1] >= a[0]]   # index of the LATER cue
    gaps = [(b[0] - a[1], i + 1) for i, (a, b) in enumerate(zip(cues, cues[1:])) if b[0] - a[1] > 5]
    longest = max((len(l) for p in plain for l in p.splitlines()), default=0)
    look.headline = f"{kind} subtitles, {len(cues)} cues, {core.mmss(start)} to {core.mmss(end)}"
    look.dims = f"{len(cues)} cues"

    def where(idx, limit=6):
        return ", ".join(f"#{nums[i]} at {core.mmss(cues[i][0])}" for i in idx[:limit]) + (f" +{len(idx) - limit} more" if len(idx) > limit else "")
    look.line(f"{len(cues)} cues, {core.mmss(start)} to {core.mmss(end)}, {enc}. Reading speed p95 {p95:.0f} chars/s ({over17} cues over 17, {over21} over 21); longest line {longest} chars; {short} under 0.8 s.", 95)
    if inverted:
        look.flag("INVERTED-CUE", where(inverted), f"{len(inverted)} cue(s) end before they start", "a player shows them for no time or not at all")
    if overlaps:
        look.flag("OVERLAPPING-CUES", where(overlaps), f"{len(overlaps)} cue(s) start before the previous one ends", "two cues on screen at once")
    if over21 > max(3, len(cues) * 0.05):
        look.flag("FAST-CUES", "reading speed", f"{over21} cues above 21 chars/s", "viewers cannot read these in time")
    if gaps:
        g, i = max(gaps)
        look.line(f"{len(gaps)} gap(s) over 5 s between cues; longest {g:.0f} s before cue #{nums[i]} at {core.mmss(cues[i][0])}.", 70)
    bad = [i for i, p in enumerate(plain) if "�" in p or re.search("Ã[-¿]|â€", p)]
    if bad:
        flat = " ".join(plain[bad[0]].split())
        mm = re.search("Ã[-¿]|â€|�", flat)
        k = max(0, (mm.start() if mm else 0) - 15)
        snip = flat[k:k + 36]
        look.flag("MOJIBAKE", where(bad), f"{len(bad)} cue(s) with broken characters, e.g. {snip!r}", "wrong encoding: the accents are broken")
    elif "�" in text or re.search("Ã[-¿]|â€", text):
        look.flag("MOJIBAKE", "text", "replacement characters or UTF-8 read as Latin-1", "wrong encoding: the accents are broken")
    if kind == "ass":
        styles = re.findall(r"(?m)^Style:\s*([^,]+),", text)
        look.line(f"ASS styles: {', '.join(dict.fromkeys(styles))[:200]}; {len(re.findall(r'{.*?pos', text))} positioned cues.", 55)
    merged = []
    for c, p in zip(cues, plain):
        p1 = " ".join(p.split())
        if p1:
            merged.append(f"[{core.mmss(c[0])}] {p1}")
    sents, buf = [], ""
    for line in merged:
        buf = (buf + " " + line).strip() if not buf else buf + " " + line.split("] ", 1)[1]
        if re.search(r"[.!?…]$", line):
            sents.append(buf)
            buf = ""
    if buf:
        sents.append(buf)
    look.write_text("text.md", "\n".join(sents), "the subtitle text, one line per sentence, with the start time", value=6)
    cb = io.StringIO()
    w = csv.writer(cb)
    w.writerow(["start", "end", "chars_per_s", "text"])
    for c, p, x in zip(cues, plain, cps):
        w.writerow([f"{c[0]:.2f}", f"{c[1]:.2f}", f"{x:.1f}", " / ".join(p.splitlines())])
    look.write_text("cues.csv", cb.getvalue(), "every cue with start, end and reading speed", value=2, inline=False)
    look.step("subtitle parse and reading-speed checks", "stdlib")
    look.mapline("first cues:\n" + "\n".join(merged[:4]), 50)
