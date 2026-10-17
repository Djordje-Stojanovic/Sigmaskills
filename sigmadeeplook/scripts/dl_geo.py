"""SigmaDeepLook: calendars (ics), tracks (gpx, kml) and geo data (GeoJSON) with their most-asked facts in step 1 (fix round 5).

Stdlib only. Counts, ranges and totals come first: events with their dates, durations, recurrence (expanded where the rule is
bounded), status and all-day flags; track points, segments, distance (haversine on the mean Earth radius), elapsed and moving
time, elevation range and total ascent and descent, speeds and waypoint names; GeoJSON features by geometry type, bounding box
with the feature at each edge, line lengths and polygon areas (spherical, as GIS tools compute them), and the properties profile.
"""
import datetime as dt
import math
import re
from collections import Counter

import dl_prof as P

R_EARTH = 6371008.8   # metres, mean radius (IUGG)


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(min(1.0, math.sqrt(h)))


def hms(s):
    if s is None:
        return "?"
    s = int(round(s))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return (f"{d}d " if d else "") + f"{h}:{m:02d}:{s:02d}"


def km(m):
    return f"{m / 1000:.3f} km"


# ================================================================= calendar
def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def unescape(v):
    return v.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def parse_ics_dt(v, params):
    """-> (datetime, kind) kind: date | utc | floating | tz:<name>."""
    v = v.strip()
    tz = next((p.split("=", 1)[1] for p in params if p.upper().startswith("TZID=")), None)
    if re.fullmatch(r"\d{8}", v):
        return dt.datetime.strptime(v, "%Y%m%d"), "date"
    if v.endswith("Z"):
        return dt.datetime.strptime(v[:16], "%Y%m%dT%H%M%SZ"), "utc"
    return dt.datetime.strptime(v[:15], "%Y%m%dT%H%M%S"), (f"tz:{tz}" if tz else "floating")


DUR_RE = re.compile(r"^([-+])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def parse_duration(v):
    m = DUR_RE.match(v.strip())
    if not m:
        return None
    w, d, h, mi, s = (int(x or 0) for x in m.groups()[1:])
    secs = (((w * 7 + d) * 24 + h) * 60 + mi) * 60 + s
    return -secs if m.group(1) == "-" else secs


def parse_components(text, kind):
    """Each BEGIN:<kind> block -> dict of property name -> list of (value, params); nested VALARMs counted, not merged."""
    out = []
    for blk in re.findall(rf"BEGIN:{kind}\r?\n(.*?)END:{kind}", text, re.S):
        alarms = len(re.findall(r"BEGIN:VALARM", blk))
        blk = re.sub(r"BEGIN:VALARM.*?END:VALARM", "", blk, flags=re.S)
        props = {}
        for ln in blk.splitlines():
            if ":" not in ln:
                continue
            k, v = ln.split(":", 1)
            name, *params = k.split(";")
            props.setdefault(name.upper(), []).append((v, params))
        props["_alarms"] = alarms
        out.append(props)
    return out


def first(props, k):
    v = props.get(k)
    return unescape(v[0][0]) if v else None


def event_row(props):
    import dl_cal
    e = {"summary": first(props, "SUMMARY") or "(no title)", "location": first(props, "LOCATION"), "status": (first(props, "STATUS") or "").upper() or None,
         "rrule": first(props, "RRULE"), "uid": first(props, "UID"), "alarms": props.get("_alarms", 0), "organizer": first(props, "ORGANIZER"),
         "attendees": len(props.get("ATTENDEE", [])), "categories": first(props, "CATEGORIES"), "transp": first(props, "TRANSP"), "class": first(props, "CLASS"),
         "recurrence_id": first(props, "RECURRENCE-ID"), "exdates": sum(len(v.split(",")) for v, _ in props.get("EXDATE", [])), "rdates": len(props.get("RDATE", []))}
    s = props.get("DTSTART")
    e["start"] = e["kind"] = e["end"] = None
    if s:
        try:
            e["start"], e["kind"] = parse_ics_dt(s[0][0], s[0][1])
        except ValueError:
            pass
    en = props.get("DTEND") or props.get("DUE")
    if en:
        try:
            e["end"] = parse_ics_dt(en[0][0], en[0][1])[0]
        except ValueError:
            pass
    elif props.get("DURATION") and e["start"]:
        d = parse_duration(props["DURATION"][0][0])
        if d is not None:
            e["end"] = e["start"] + dt.timedelta(seconds=d)
    elif e["kind"] == "date" and e["start"]:
        e["end"] = e["start"] + dt.timedelta(days=1)
    e["all_day"] = e["kind"] == "date"
    e["dur"] = (e["end"] - e["start"]).total_seconds() if e["start"] and e["end"] else None
    e["occurrences"] = 1
    if e["rrule"] and e["start"]:
        rule = dl_cal.parse_rrule(e["rrule"])
        e["rule_text"] = dl_cal.describe(rule)
        if "COUNT" in rule or "UNTIL" in rule:
            ex = []
            for v, _ in props.get("EXDATE", []):
                for x in v.split(","):
                    try:
                        ex.append(dl_cal.parse_dt(x)[0])
                    except ValueError:
                        pass
            occ, ok = dl_cal.expand(e["start"], rule, limit=100000, horizon_years=200, exdates=ex)
            e["occurrences"] = len(occ) if ok else None
            e["last_occurrence"] = occ[-1] if ok and occ else None
        else:
            e["occurrences"] = None   # repeats forever
    return e


def fmt_dt(d, kind):
    if d is None:
        return "?"
    return d.strftime("%Y-%m-%d") if kind == "date" else d.strftime("%Y-%m-%d %H:%M") + (" UTC" if kind == "utc" else f" ({kind[3:]})" if kind and kind.startswith("tz:") else "")


def look_ics(look):
    import csv
    import io
    raw = open(look.path, "rb").read(32 << 20)
    import dl_delim
    text = unfold(re.sub(r"\r\n?", "\n", dl_delim.sniff_encoding(raw)[0]))
    cal = {k: v for k, v in (ln.split(":", 1) for ln in text.split("BEGIN:V")[1].splitlines()[1:] if ":" in ln and not ln.startswith(("BEGIN", "END"))) if k in ("PRODID", "X-WR-CALNAME", "METHOD", "X-WR-TIMEZONE", "CALSCALE", "VERSION")} if "BEGIN:V" in text else {}
    evs = [event_row(p) for p in parse_components(text, "VEVENT")]
    todos = [event_row(p) for p in parse_components(text, "VTODO")]
    journals = len(re.findall(r"BEGIN:VJOURNAL", text))
    tzids = re.findall(r"BEGIN:VTIMEZONE\r?\n(?:.*\r?\n)*?TZID:([^\r\n]+)", text)
    look.headline = f"calendar, {len(evs)} event(s)" + (f", {len(todos)} to-do(s)" if todos else "")
    look.dims = f"{len(evs)} events"
    dated = [e for e in evs if e["start"]]
    rec = [e for e in evs if e["rrule"]]
    bounded = [e for e in rec if e["occurrences"] is not None]
    total_occ = sum(e["occurrences"] or 0 for e in evs if not e["rrule"]) + sum(e["occurrences"] for e in bounded)
    st = Counter(e["status"] or "(none)" for e in evs)
    look.fact("events", len(evs))
    look.fact("recurring_events", len(rec))
    P.counts(look, [("events", len(evs)), ("to-dos", len(todos) or None), ("journal entries", journals or None), ("recurring events", len(rec)),
                    ("occurrences (bounded rules expanded)", total_occ if rec else None), ("repeating forever", len(rec) - len(bounded) or None),
                    ("all-day events", sum(e["all_day"] for e in evs)), ("cancelled", st.get("CANCELLED", 0)), ("tentative", st.get("TENTATIVE", 0) or None),
                    ("confirmed", st.get("CONFIRMED", 0) or None), ("with a location", sum(1 for e in evs if e["location"])), ("attendees (all events)", sum(e["attendees"] for e in evs) or None),
                    ("alarms", sum(e["alarms"] for e in evs) or None), ("changed occurrences (RECURRENCE-ID)", sum(1 for e in evs if e["recurrence_id"]) or None),
                    ("excluded dates (EXDATE)", sum(e["exdates"] for e in evs) or None), ("time zones defined", len(set(tzids)) or None)], 97)
    if dated:
        lo = min(dated, key=lambda e: e["start"])
        hi = max(dated, key=lambda e: e["start"])
        ends = [e for e in dated if e["end"]]
        last_end = max(ends, key=lambda e: e["end"]) if ends else None
        last_occ = max((e for e in bounded if e.get("last_occurrence")), key=lambda e: e["last_occurrence"], default=None)
        durs = [e for e in dated if e["dur"] is not None]
        bits = [f"first start {fmt_dt(lo['start'], lo['kind'])} ({lo['summary']})", f"last start {fmt_dt(hi['start'], hi['kind'])} ({hi['summary']})"]
        if last_end:
            bits.append(f"last end {fmt_dt(last_end['end'], last_end['kind'])} ({last_end['summary']})")
        if last_occ:
            bits.append(f"last occurrence of a repeating event {fmt_dt(last_occ['last_occurrence'], last_occ['kind'])} ({last_occ['summary']})")
        if durs:
            lg = max(durs, key=lambda e: e["dur"])
            sh = min(durs, key=lambda e: e["dur"])
            bits.append(f"longest {hms(lg['dur'])} ({lg['summary']}), shortest {hms(sh['dur'])} ({sh['summary']}), total {hms(sum(e['dur'] for e in durs))} over {len(durs)} events")
        months = Counter(e["start"].strftime("%Y-%m") for e in dated)
        bits.append("events by start month: " + ", ".join(f"{k} {v}" for k, v in sorted(months.items())))
        wd = Counter(e["start"].strftime("%a") for e in dated if not e["all_day"])
        if wd:
            bits.append("timed events by weekday: " + ", ".join(f"{k} {v}" for k, v in wd.most_common()))
        look.line("Dates: " + "; ".join(bits) + ".", 96, "range")
    if cal:
        look.line("Calendar properties: " + "; ".join(f"{k} {v}" for k, v in cal.items()), 85)
    kinds = Counter(e["kind"].split(":")[0] if e["kind"] else "?" for e in dated)
    if kinds:
        look.line("Time kinds of the starts: " + ", ".join(f"{k} {v}" for k, v in kinds.items()) + (f"; zones {', '.join(sorted(set(tzids)))}" if tzids else ""), 70)
    rows = []
    for i, e in enumerate(evs, 1):
        bits = [f"{i}. {e['summary']}: {fmt_dt(e['start'], e['kind'])}" + (f" -> {fmt_dt(e['end'], e['kind'])}" if e["end"] else "") + (f" ({'all day, ' if e['all_day'] else ''}{hms(e['dur'])})" if e["dur"] is not None else "")]
        if e["rrule"]:
            bits.append(f"repeats {e.get('rule_text')}" + (f", {e['occurrences']} occurrences" if e["occurrences"] else ", forever"))
        for k in ("status", "location", "categories"):
            if e[k]:
                bits.append(f"{k} {e[k]}")
        if e["attendees"]:
            bits.append(f"{e['attendees']} attendees")
        if e["recurrence_id"]:
            bits.append(f"changes the occurrence of {e['recurrence_id']}")
        rows.append("; ".join(bits))
    head = rows[:30]
    if head:
        look.line(f"Events in file order ({len(evs)}; start -> end (duration), rule, status, location):\n" + "\n".join(head), 94 if len(evs) <= 30 else 88, "events")
    for k in range(30, len(rows), 40):
        look.line(f"Events {k + 1}-{min(len(rows), k + 40)}:\n" + "\n".join(rows[k:k + 40]), 30, "events")
    if todos:
        done = sum(1 for t in todos if (t["status"] or "") == "COMPLETED")
        look.line(f"To-dos ({len(todos)}, {done} completed): " + "; ".join(f"{t['summary']}" + (f" due {fmt_dt(t['end'], t['kind'])}" if t["end"] else "") + (f" [{t['status']}]" if t["status"] else "") for t in todos[:30]), 89)
    locs = Counter(e["location"] for e in evs if e["location"])
    if locs:
        look.line("Locations (events): " + ", ".join(f"{k} {v}" for k, v in locs.most_common(20)), 70)
    orgs = Counter(e["organizer"] for e in evs if e["organizer"])
    if orgs:
        look.line("Organizers (events): " + ", ".join(f"{P.short(k, 50)} {v}" for k, v in orgs.most_common(10)), 60)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["uid", "summary", "start", "start_kind", "end", "duration_s", "all_day", "rrule", "occurrences", "status", "location", "organizer", "attendees"])
    for e in evs:
        w.writerow([e["uid"], e["summary"], e["start"], e["kind"], e["end"], e["dur"], e["all_day"], e["rrule"], e["occurrences"], e["status"], e["location"], e["organizer"], e["attendees"]])
    look.write_text("events.csv", buf.getvalue(), f"{len(evs)} events: start, end, duration, rule, status, location", value=2, inline=None if len(evs) <= 60 else False)
    look.fact("event_list", [{"summary": e["summary"], "start": str(e["start"]), "kind": e["kind"]} for e in evs[:200]])
    import dl_docs
    legacy = []   # the older recurrence reader: rule traps (forever, floating times) and the next occurrences
    for p in parse_components(text, "VEVENT"):
        ev = {k: v[0][0] for k, v in p.items() if not k.startswith("_")}
        if p.get("DTSTART"):
            prm = p["DTSTART"][0][1]
            v = p["DTSTART"][0][0]
            ev["DTSTART_TZ"] = next((x.split("=", 1)[1] for x in prm if x.upper().startswith("TZID=")), "UTC" if v.endswith("Z") else "floating")
        legacy.append(ev)
    dl_docs.ics_recurrence(look, legacy)
    look.step("calendar parse", "stdlib")


# ================================================================= tracks: GPX and KML
def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _time(s):
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        t = dt.datetime.fromisoformat(s)
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def track_stats(segs):
    """segs: [[(lat, lon, ele or None, time or None, extras dict)]] -> dict of exact totals."""
    pts = [p for s in segs for p in s]
    d = sum(haversine(a[0], a[1], b[0], b[1]) for s in segs for a, b in zip(s, s[1:]))
    out = {"points": len(pts), "segments": len(segs), "distance_m": d}
    eles = [(p[2], i) for i, p in enumerate(pts) if p[2] is not None]
    if eles:
        out["ele_min"], out["ele_min_at"] = min(eles)
        out["ele_max"], out["ele_max_at"] = max(eles)
        up = down = 0.0
        for s in segs:
            e = [p[2] for p in s if p[2] is not None]
            for a, b in zip(e, e[1:]):
                up += max(0.0, b - a)
                down += max(0.0, a - b)
        out["ascent"], out["descent"] = up, down
        out["ele_start"], out["ele_end"] = eles[0][0], eles[-1][0]
    times = [p[3] for p in pts if p[3] is not None]
    if times:
        out["start"], out["end"] = min(times), max(times)
        out["elapsed_s"] = (out["end"] - out["start"]).total_seconds()
        moving, vmax, vmax_at = 0.0, 0.0, None
        for s in segs:
            for a, b in zip(s, s[1:]):
                if a[3] and b[3]:
                    dtt = (b[3] - a[3]).total_seconds()
                    dd = haversine(a[0], a[1], b[0], b[1])
                    if dtt > 0:
                        v = dd / dtt
                        if v > 0.3 and dtt <= 300:   # moving: faster than 1 km/h and no gap over 5 minutes
                            moving += dtt
                        if v > vmax:
                            vmax, vmax_at = v, b[3]
        out["moving_s"], out["vmax"], out["vmax_at"] = moving, vmax, vmax_at
    if pts:
        out["bbox"] = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
    ext = {}
    for p in pts:
        for k, v in (p[4] or {}).items():
            ext.setdefault(k, []).append(v)
    out["extensions"] = {k: (len(v), min(v), max(v), sum(v) / len(v)) for k, v in ext.items()}
    return out


def stats_line(name, s):
    bits = [f"{s['points']:,} points in {s['segments']} segment(s)", f"distance {km(s['distance_m'])}"]
    if "start" in s:
        bits.append(f"start {s['start']:%Y-%m-%d %H:%M:%S %Z}, end {s['end']:%Y-%m-%d %H:%M:%S %Z}, elapsed {hms(s['elapsed_s'])}, moving {hms(s['moving_s'])}")
        if s["elapsed_s"] > 0:
            bits.append(f"average speed {s['distance_m'] / s['elapsed_s'] * 3.6:.2f} km/h elapsed, {s['distance_m'] / max(1, s['moving_s']) * 3.6:.2f} km/h moving; top {s['vmax'] * 3.6:.1f} km/h")
    if "ele_min" in s:
        bits.append(f"elevation {s['ele_min']:.1f}..{s['ele_max']:.1f} m (low at point {s['ele_min_at'] + 1}, high at point {s['ele_max_at'] + 1}), start {s['ele_start']:.1f} m, end {s['ele_end']:.1f} m, "
                    f"total ascent {s['ascent']:.1f} m, descent {s['descent']:.1f} m (raw, no smoothing)")
    for k, (n, lo, hi, mean) in s.get("extensions", {}).items():
        bits.append(f"{k} {P.fmt(lo)}..{P.fmt(hi)} (mean {P.fmt(round(mean, 2))}, {n:,} points)")
    return f"{name}: " + "; ".join(bits)


def look_gpx(look, root):
    trks, wpts, rtes = [], [], []
    meta = {}
    for el in root:
        t = _local(el.tag)
        if t == "metadata":
            for m in el.iter():
                if _local(m.tag) in ("name", "desc", "time", "keywords") and (m.text or "").strip():
                    meta[_local(m.tag)] = m.text.strip()
                if _local(m.tag) == "author":
                    nm = next((x.text for x in m.iter() if _local(x.tag) == "name" and x.text), None)
                    if nm:
                        meta["author"] = nm
        elif t in ("trk", "rte"):
            name = next((c.text for c in el if _local(c.tag) == "name"), None)
            segs = []
            groups = [s for s in el if _local(s.tag) == "trkseg"] if t == "trk" else [el]
            for g in groups:
                pts = []
                for p in g:
                    if _local(p.tag) not in ("trkpt", "rtept"):
                        continue
                    ele = tm = None
                    ext = {}
                    for c in p.iter():
                        ct = _local(c.tag)
                        if ct == "ele" and c.text:
                            try:
                                ele = float(c.text)
                            except ValueError:
                                pass
                        elif ct == "time":
                            tm = _time(c.text)
                        elif c is not p and len(c) == 0 and c.text and ct not in ("name", "desc", "sym", "type", "cmt") and re.match(r"^-?\d+(\.\d+)?$", c.text.strip()):
                            ext[ct] = float(c.text)
                    try:
                        pts.append((float(p.get("lat")), float(p.get("lon")), ele, tm, ext))
                    except (TypeError, ValueError):
                        continue
                segs.append(pts)
            (trks if t == "trk" else rtes).append((name, segs))
        elif t == "wpt":
            name = next((c.text for c in el if _local(c.tag) == "name"), None)
            ele = next((c.text for c in el if _local(c.tag) == "ele"), None)
            wpts.append((name, el.get("lat"), el.get("lon"), ele))
    all_segs = [s for _, segs in trks for s in segs]
    tot = track_stats(all_segs) if all_segs else None
    look.headline = f"GPX: {len(trks)} track(s), {sum(len(s) for _, segs in trks for s in segs):,} points" + (f", {km(tot['distance_m'])}" if tot else "")
    P.counts(look, [("tracks", len(trks)), ("track segments", len(all_segs)), ("track points", sum(len(s) for s in all_segs)), ("routes", len(rtes) or None),
                    ("route points", sum(len(s) for _, segs in rtes for s in segs) or None), ("waypoints", len(wpts))], 97)
    if tot:
        look.fact("distance_km", round(tot["distance_m"] / 1000, 4))
        look.fact("elapsed_s", tot.get("elapsed_s"))
        look.line(stats_line("All tracks together", tot) + (f"; bounding box lat {tot['bbox'][0]:.5f}..{tot['bbox'][2]:.5f}, lon {tot['bbox'][1]:.5f}..{tot['bbox'][3]:.5f}" if tot.get("bbox") else ""), 96, "totals")
    if len(trks) > 1 or (trks and len(trks[0][1]) > 1):
        rows = []
        for i, (name, segs) in enumerate(trks, 1):
            rows.append(stats_line(f"Track {i} {name or ''}".strip(), track_stats(segs)))
            if len(segs) > 1:
                for j, s in enumerate(segs, 1):
                    rows.append("  " + stats_line(f"segment {j}", track_stats([s])))
        look.line("Per track and segment:\n" + "\n".join(rows[:60]), 92, "tracks")
    elif trks:
        look.line(f"Track name: {trks[0][0]}", 90)
    for i, (name, segs) in enumerate(rtes, 1):
        look.line(stats_line(f"Route {i} {name or ''}".strip(), track_stats(segs)), 88)
    if wpts:
        look.line(f"Waypoints ({len(wpts)}): " + "; ".join(f"{n or '(no name)'} ({la}, {lo}" + (f", {e} m" if e else "") + ")" for n, la, lo, e in wpts[:60]), 93, "waypoints")
    if meta:
        look.line("GPX metadata: " + "; ".join(f"{k} {v}" for k, v in meta.items()) + (f"; creator {root.get('creator')}" if root.get("creator") else ""), 90)
    elif root.get("creator"):
        look.line(f"GPX creator: {root.get('creator')}", 70)
    look.step("track totals", "stdlib")


def look_kml(look, root):
    marks = [el for el in root.iter() if _local(el.tag) == "Placemark"]
    kinds, rows, total = Counter(), [], 0.0
    for el in marks:
        name = next((c.text for c in el.iter() if _local(c.tag) == "name" and c.text), "(no name)")
        for g in el.iter():
            gt = _local(g.tag)
            if gt not in ("Point", "LineString", "Polygon", "LinearRing", "Track"):
                continue
            if gt == "LinearRing":
                continue
            kinds[gt] += 1
            coords = []
            for c in g.iter():
                if _local(c.tag) == "coordinates" and c.text:
                    for tup in c.text.split():
                        xs = tup.split(",")
                        try:
                            coords.append((float(xs[1]), float(xs[0])))
                        except (ValueError, IndexError):
                            pass
            ln = sum(haversine(a[0], a[1], b[0], b[1]) for a, b in zip(coords, coords[1:])) if gt == "LineString" else 0.0
            total += ln
            rows.append(f"{name}: {gt}, {len(coords)} coordinates" + (f", length {km(ln)}" if ln else "") + (f" at {coords[0][0]:.5f}, {coords[0][1]:.5f}" if gt == "Point" and coords else ""))
    folders = sum(1 for el in root.iter() if _local(el.tag) == "Folder")
    look.headline = f"KML: {len(marks)} placemarks"
    P.counts(look, [("placemarks", len(marks)), ("folders", folders or None)] + [(f"{k} geometries", v) for k, v in kinds.most_common()] + [("line length km", round(total / 1000, 3) if total else None)], 97)
    look.line(f"Placemarks ({len(marks)}):\n" + "\n".join(rows[:60]), 93, "placemarks")


# ================================================================= GeoJSON
def is_geojson(v):
    t = v.get("type") if isinstance(v, dict) else None
    return t in ("FeatureCollection", "Feature", "GeometryCollection", "Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon")


def ring_area(ring):
    """Spherical polygon ring area in m^2 (the formula GIS tools use: Chamberlain and Duquette)."""
    if len(ring) < 3:
        return 0.0
    a = 0.0
    n = len(ring)
    for i in range(n):
        lon1, lat1 = ring[i][0], ring[i][1]
        lon2, lat2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        a += math.radians(lon2 - lon1) * (2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
    return abs(a * R_EARTH * R_EARTH / 2)


def geom_measures(g):
    """-> (type, vertices, length m, area m2, [(lon, lat)])."""
    t = g.get("type") if isinstance(g, dict) else None
    c = g.get("coordinates") if isinstance(g, dict) else None
    pts, length, area = [], 0.0, 0.0
    try:
        if t == "Point":
            pts = [c]
        elif t in ("MultiPoint",):
            pts = list(c)
        elif t == "LineString":
            pts = list(c)
            length = sum(haversine(a[1], a[0], b[1], b[0]) for a, b in zip(c, c[1:]))
        elif t == "MultiLineString":
            for line in c:
                pts += line
                length += sum(haversine(a[1], a[0], b[1], b[0]) for a, b in zip(line, line[1:]))
        elif t == "Polygon":
            for k, ring in enumerate(c):
                pts += ring
                area += ring_area(ring) * (1 if k == 0 else -1)
        elif t == "MultiPolygon":
            for poly in c:
                for k, ring in enumerate(poly):
                    pts += ring
                    area += ring_area(ring) * (1 if k == 0 else -1)
        elif t == "GeometryCollection":
            for sub in g.get("geometries") or []:
                _, _, l2, a2, p2 = geom_measures(sub)
                length += l2
                area += a2
                pts += p2
    except (TypeError, IndexError, ValueError):
        pass
    pts = [p for p in pts if isinstance(p, (list, tuple)) and len(p) >= 2 and all(isinstance(x, (int, float)) for x in p[:2])]
    return t, len(pts), length, area, pts


def geojson_facts(look, v, pri=97):
    feats = v.get("features") if v.get("type") == "FeatureCollection" else [v] if v.get("type") == "Feature" else [{"type": "Feature", "properties": {}, "geometry": v}]
    feats = [f for f in feats or [] if isinstance(f, dict)]
    kinds, verts, rows = Counter(), 0, []
    bb = [None, None, None, None]
    at = [None, None, None, None]
    tot_len = tot_area = 0.0
    longest = largest = None
    for i, f in enumerate(feats):
        props = f.get("properties") or {}
        name = next((str(props[k]) for k in ("name", "NAME", "title", "label", "id") if k in props and props[k] not in (None, "")), None) or str(f.get("id") if f.get("id") is not None else f"#{i}")
        t, nv, ln, ar, pts = geom_measures(f.get("geometry"))
        kinds[t or "null geometry"] += 1
        verts += nv
        tot_len += ln
        tot_area += ar
        if ln and (longest is None or ln > longest[0]):
            longest = (ln, name, i)
        if ar and (largest is None or ar > largest[0]):
            largest = (ar, name, i)
        for p in pts:
            x, y = p[0], p[1]
            for k, val, better in ((0, x, lambda a, b: a < b), (1, y, lambda a, b: a < b), (2, x, lambda a, b: a > b), (3, y, lambda a, b: a > b)):
                if bb[k] is None or better(val, bb[k]):
                    bb[k], at[k] = val, name
        desc = f"[{i}] {name}: {t}" + (f" ({p0[1]:.5f}, {p0[0]:.5f})" if t == "Point" and pts and (p0 := pts[0]) else f", {nv} vertices") + (f", length {km(ln)}" if ln else "") + (f", area {ar / 1e6:.4f} km2" if ar else "")
        rows.append(desc)
    look.headline = f"GeoJSON: {len(feats):,} features (" + ", ".join(f"{k} {v}" for k, v in kinds.most_common()) + ")"
    look.fact("features", len(feats))
    look.fact("geometry_types", dict(kinds))
    P.counts(look, [("features", len(feats))] + [(f"{k} features", n) for k, n in kinds.most_common()] + [("vertices", verts), ("total line length km", round(tot_len / 1000, 4) if tot_len else None),
                                                                                                       ("total polygon area km2", round(tot_area / 1e6, 6) if tot_area else None)], pri)
    if bb[0] is not None:
        look.line(f"Bounding box (lon, lat): west {bb[0]} ({at[0]}), south {bb[1]} ({at[1]}), east {bb[2]} ({at[2]}), north {bb[3]} ({at[3]})"
                  + (f"; longest line {longest[1]} {km(longest[0])}" if longest else "") + (f"; largest polygon {largest[1]} {largest[0] / 1e6:.4f} km2" if largest else "")
                  + (f"; collection name {v.get('name')}" if v.get("name") else "") + (f"; crs {v.get('crs', {}).get('properties', {}).get('name')}" if isinstance(v.get("crs"), dict) else ""), pri - 1, "geo")
    look.line(f"Features ({len(feats)}; index, name, geometry, measures):\n" + "\n".join(rows[:40]), pri - 3 if len(feats) <= 40 else pri - 8, "features")
    for k in range(40, min(len(rows), 4000), 60):
        look.line(f"Features {k}-{min(len(rows), k + 60) - 1}:\n" + "\n".join(rows[k:k + 60]), 25, "features")
    props = [(i, f.get("properties") or {}) for i, f in enumerate(feats)]
    p, extra = P.profile(props, False, "feature")
    if p.fields:
        P.emit(look, p, extra, "Feature properties (index from 0)", pri - 4, 30, 30)
