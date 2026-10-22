"""SigmaDeepLook: the full container and stream metadata of a video or audio file (fix round 4), exact numbers.

One ffprobe call (-show_format -show_streams -show_chapters, plus -count_packets for an exact frame count when the container does
not store one): duration to the millisecond, frame count, frame rates as fractions, bit rates, every stream's codec, profile,
pixel format (alpha or not), colour, channels and layout, sample rate and format, every container and stream tag (encoder, title,
creation time, language, handler) and disposition, chapters with times.
"""
import json

import dl_prof as P

ALPHA_FMTS = ("yuva", "rgba", "argb", "bgra", "abgr", "gbrap", "ya8", "ya16", "pal8")


def fraction(s):
    try:
        a, b = str(s).split("/")
        a, b = float(a), float(b)
        return a / b if b else None
    except (ValueError, TypeError):
        return None


def secs(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def hms(t):
    if t is None:
        return "?"
    ms = int(round(t * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return (f"{h}:{m:02d}" if h else f"{m}") + f":{s:02d}.{ms:03d}"


def probe_full(look, count=True):
    fp = look.tool("ffprobe")
    if not fp:
        return None
    args = [fp, "-v", "error", "-show_format", "-show_streams", "-show_chapters", "-show_programs", "-of", "json"]
    if count:
        args.insert(3, "-count_packets")
    r, out, _ = look.run_text(args + [str(look.path)])
    if r is None or not out.strip().startswith("{"):
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def media_meta(look, pri=93):
    """Adds the metadata facts to the look; returns the probe dict (or None)."""
    j = probe_full(look, count=not look.quick)
    if not j:
        return None
    fmt = j.get("format", {})
    streams = j.get("streams", [])
    chapters = j.get("chapters", [])
    dur = secs(fmt.get("duration"))
    kinds = {}
    for s in streams:
        kinds.setdefault(s.get("codec_type", "?"), []).append(s)
    v = next((s for s in kinds.get("video", []) if not s.get("disposition", {}).get("attached_pic")), None)
    a = (kinds.get("audio") or [None])[0]
    pairs = [("duration", f"{dur:.3f} s ({hms(dur)})" if dur is not None else None), ("streams", len(streams))]
    pairs += [(f"{k} streams", len(x)) for k, x in sorted(kinds.items())]
    if v:
        frames = v.get("nb_frames") or v.get("nb_read_packets")
        fr = fraction(v.get("r_frame_rate"))
        afr = fraction(v.get("avg_frame_rate"))
        pairs += [("video frames", int(frames) if frames and str(frames).isdigit() else None), ("frame rate", f"{v.get('avg_frame_rate')} = {afr:.3f} fps" if afr else None),
                  ("base frame rate", f"{v.get('r_frame_rate')}" if v.get("r_frame_rate") != v.get("avg_frame_rate") else None),
                  ("size", f"{v.get('width')}x{v.get('height')}")]
    if a:
        pairs += [("audio channels", a.get("channels")), ("channel layout", a.get("channel_layout")), ("sample rate", f"{a.get('sample_rate')} Hz" if a.get("sample_rate") else None)]
    pairs += [("overall bit rate", f"{int(fmt['bit_rate']):,} b/s" if str(fmt.get("bit_rate", "")).isdigit() else None), ("chapters", len(chapters) or None)]
    P.counts(look, pairs, pri + 2, "Media counts")
    tags = fmt.get("tags", {})
    look.line(f"Container: {fmt.get('format_long_name') or fmt.get('format_name')} ({fmt.get('format_name')}); start {fmt.get('start_time')} s; size {int(fmt.get('size', 0)):,} B"
              + (f"; tags: " + "; ".join(f"{k} = {P.short(x, 80)}" for k, x in tags.items()) if tags else "; no container tags"), pri, "props")
    progs = j.get("programs") or []
    if progs and (fmt.get("format_name") == "mpegts" or any(p.get("tags") for p in progs)):
        rows = []
        for p in progs:
            t = p.get("tags") or {}
            rows.append(f"program {p.get('program_num', p.get('program_id'))}: " + ("; ".join(f"{k} = {P.short(v, 60)}" for k, v in t.items()) or "no service tags")
                        + f"; {p.get('nb_streams', len(p.get('streams', [])))} streams, PMT pid {p.get('pmt_pid')}, PCR pid {p.get('pcr_pid')}")
        look.line(f"Programs in the stream ({len(progs)}): " + " | ".join(rows), pri - 1, "props")
        look.fact("programs", len(progs))
    for s in streams:
        bits = [f"#{s.get('index')} {s.get('codec_type')}: {s.get('codec_name')}" + (f" ({s.get('profile')})" if s.get("profile") else "")]
        if s.get("codec_type") == "video":
            pf = s.get("pix_fmt", "")
            alpha = any(pf.startswith(x) for x in ALPHA_FMTS) or (s.get("tags", {}).get("alpha_mode") == "1")
            bits.append(f"{s.get('width')}x{s.get('height')}, pix_fmt {pf} ({'has alpha' if alpha else 'no alpha'})")
            for k in ("sample_aspect_ratio", "display_aspect_ratio", "field_order", "color_range", "color_space", "color_primaries", "color_transfer", "bits_per_raw_sample", "level"):
                if s.get(k) not in (None, "unknown", "N/A"):
                    bits.append(f"{k} {s[k]}")
            bits.append(f"r_frame_rate {s.get('r_frame_rate')}, avg_frame_rate {s.get('avg_frame_rate')}")
            for k in ("nb_frames", "nb_read_packets"):
                if s.get(k):
                    bits.append(f"{k} {int(s[k]):,}" if str(s[k]).isdigit() else f"{k} {s[k]}")
        elif s.get("codec_type") == "audio":
            for k in ("sample_rate", "channels", "channel_layout", "sample_fmt", "bits_per_sample", "bits_per_raw_sample", "nb_frames"):
                if s.get(k) not in (None, 0, "0", "N/A", ""):
                    bits.append(f"{k} {s[k]}")
        for k in ("bit_rate", "duration", "start_time", "time_base"):
            if s.get(k) not in (None, "N/A"):
                bits.append(f"{k} {int(s[k]):,}" if k == "bit_rate" and str(s[k]).isdigit() else f"{k} {s[k]}")
        disp = [k for k, x in s.get("disposition", {}).items() if x]
        if disp:
            bits.append("disposition " + ", ".join(disp))
        st = s.get("tags", {})
        if st:
            bits.append("tags " + "; ".join(f"{k} = {P.short(x, 60)}" for k, x in st.items()))
        look.line("Stream " + ", ".join(bits), pri - 3 if s is v or s is a else pri - 12, "props")
    if chapters:
        look.line(f"Chapters ({len(chapters)}): " + "; ".join(f"{c.get('tags', {}).get('title', '#' + str(i))} {hms(secs(c.get('start_time')))}-{hms(secs(c.get('end_time')))}" for i, c in enumerate(chapters, 1)), pri - 5)
    look.fact("probe_full", {"format": {k: fmt.get(k) for k in ("format_name", "duration", "bit_rate", "size")}, "streams": len(streams)})
    return j
