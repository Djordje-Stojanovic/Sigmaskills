"""SigmaDeepLook: small families and adapters that wait for a package.

Avro, Windows event logs (EVTX) and Photoshop (PSD) files get their header facts from the standard library; the content (records,
events, layers) waits for fastavro, python-evtx and psd-tools. VBA macro analysis (oletools), glTF validation (the Khronos
validator), mesh checks (trimesh) and a second opinion on the file type (Magika) are adapters with a parser tested on canned
output. A missing package is one 'Not looked at' row with its install line.
"""
import datetime as dt
import json
import os
import re
import struct
from collections import Counter

import dl_core as core


# ================================================================= Avro
def zz(b, i):
    """Avro varint (zig-zag long) -> (value, next index)."""
    n = s = 0
    while True:
        x = b[i]
        i += 1
        n |= (x & 0x7F) << s
        if not x & 0x80:
            break
        s += 7
    return (n >> 1) ^ -(n & 1), i


def avro_header(b):
    """-> (meta dict str->bytes, sync marker, offset after the header)."""
    if b[:4] != b"Obj\x01":
        raise ValueError("no Avro magic")
    i, meta = 4, {}
    while True:
        cnt, i = zz(b, i)
        if cnt == 0:
            break
        if cnt < 0:
            _, i = zz(b, i)
            cnt = -cnt
        for _ in range(cnt):
            kl, i = zz(b, i)
            k = b[i:i + kl].decode("utf-8", "replace")
            i += kl
            vl, i = zz(b, i)
            meta[k] = bytes(b[i:i + vl])
            i += vl
    return meta, bytes(b[i:i + 16]), i + 16


def avro_fields(schema):
    if isinstance(schema, dict) and schema.get("type") == "record":
        return [(f.get("name"), json.dumps(f.get("type"))[:60]) for f in schema.get("fields", [])]
    return []


def look_avro(look):
    with open(look.path, "rb") as f:
        head = f.read(1 << 20)
        meta, sync, off = avro_header(head)
        try:
            schema = json.loads(meta.get("avro.schema", b"{}").decode("utf-8", "replace"))
        except ValueError:
            schema = {}
        codec = meta.get("avro.codec", b"null").decode()
        records = blocks = 0
        pos = off
        while blocks < 200000 and pos < look.size:
            f.seek(pos)
            chunk = f.read(20)
            try:
                n, i = zz(chunk, 0)
                size, i = zz(chunk, i)
            except IndexError:
                break
            records += n
            blocks += 1
            nxt = pos + i + size + 16
            if nxt > look.size:
                look.flag("TRUNCATED", "last block", "a block runs past the end of the file", "the file is cut short")
                break
            pos = nxt
    fields = avro_fields(schema)
    look.headline = f"Avro, {records} records, {len(fields)} fields, codec {codec}"
    look.dims = f"{records} records"
    look.fact("rows", records)
    look.line(f"Avro container: {records} records in {blocks} blocks, codec {codec}; record {schema.get('name', '?')} with {len(fields)} fields.", 90)
    if fields:
        look.line("Fields: " + ", ".join(f"{n} ({t})" for n, t in fields[:20]) + (f" (+{len(fields) - 20})" if len(fields) > 20 else ""), 80)
    import dl_colmeta as CM
    kv = {k: (v.decode("utf-8", "replace") if isinstance(v, (bytes, bytearray)) else str(v)) for k, v in meta.items() if k not in ("avro.schema",)}
    look.fact("file_metadata", kv)
    look.line(CM.kv_line(kv, "Header key/value metadata (avro.schema left out: see schema.json)"), 94, "props")
    look.write_text("schema.json", json.dumps(schema, indent=1), "the Avro schema", "json", value=4)
    fa = look.mod("fastavro")
    if not fa:
        look.skip("record values (sample rows)", "python package fastavro not importable" if not look.no_tools else "disabled by --no-tools", "fastavro")
        return
    try:
        with open(look.path, "rb") as f:
            rows = []
            for i, rec in enumerate(fa.reader(f)):
                rows.append(rec)
                if i >= 4:
                    break
        look.write_text("sample.json", json.dumps(rows, indent=1, default=str)[:20000], "the first 5 records", "json", value=6)
        look.step("sample records", "fastavro")
        if not look.quick and records:
            import dl_data as D
            names = [n for n, _t in fields]

            def rowsgen():
                with open(look.path, "rb") as f2:
                    for k, rec in enumerate(fa.reader(f2), 1):
                        yield k, [json.dumps(rec.get(n), default=str, sort_keys=True) if isinstance(rec.get(n), (list, dict)) else rec.get(n) for n in names]
            D.table_profile(look, "Records", names, rowsgen, "record", records, 84, 28)
    except Exception as e:
        look.fail("record values", "fastavro", e)


# ================================================================= EVTX
def filetime(v):
    try:
        return dt.datetime(1601, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(microseconds=v // 10)
    except (OverflowError, ValueError):
        return None


def evtx_header(b):
    if b[:8] != b"ElfFile\x00":
        raise ValueError("no ElfFile magic")
    first, last, next_id = struct.unpack_from("<QQQ", b, 8)
    minor, major, hsize, chunks, = struct.unpack_from("<HHHH", b, 36)
    flags = struct.unpack_from("<I", b, 120)[0]
    return {"first_chunk": first, "last_chunk": last, "next_record": next_id, "version": f"{major}.{minor}", "chunks": chunks, "dirty": bool(flags & 1), "full": bool(flags & 2), "header_size": hsize}


def evtx_span(f, h):
    """First and last record timestamps from the first and last chunk headers."""
    def stamp(chunk_no, last):
        base = 4096 + chunk_no * 65536
        f.seek(base)
        hdr = f.read(512)
        if hdr[:8] != b"ElfChnk\x00":
            return None
        off = 512 if not last else struct.unpack_from("<I", hdr, 44)[0]
        f.seek(base + off)
        rec = f.read(24)
        if len(rec) < 24 or struct.unpack_from("<I", rec, 0)[0] != 0x2A2A:
            return None
        return filetime(struct.unpack_from("<Q", rec, 16)[0])
    return stamp(0, False), stamp(max(0, h["chunks"] - 1), True)


def raw_records(path, max_chunks=100000):
    """Every record header of an EVTX file, read straight from the chunks (stdlib): -> [(record id, datetime or None, size)].
    Works when python-evtx is missing or fails on a record."""
    out = []
    with open(path, "rb") as f:
        f.seek(4096)
        for _ in range(max_chunks):
            blk = f.read(65536)
            if len(blk) < 512 or blk[:8] != b"ElfChnk\x00":
                break
            pos = 512
            while pos + 24 <= len(blk):
                sig, size = struct.unpack_from("<II", blk, pos)
                if sig != 0x2A2A or size < 24 or pos + size > len(blk):
                    break
                rid, ts = struct.unpack_from("<QQ", blk, pos + 8)
                out.append((rid, filetime(ts), size))
                pos += size
    return out


LEVEL_NAMES = {"0": "LogAlways", "1": "Critical", "2": "Error", "3": "Warning", "4": "Information", "5": "Verbose"}
EV_FIELDS = {"id": re.compile(r"<EventID[^>]*>(\d+)</EventID>"), "level": re.compile(r"<Level>(\d+)</Level>"),
             "provider": re.compile(r'<Provider Name="([^"]+)"'), "channel": re.compile(r"<Channel>([^<]*)</Channel>"),
             "computer": re.compile(r"<Computer>([^<]*)</Computer>"), "time": re.compile(r'<TimeCreated SystemTime="([^"]+)"'),
             "user": re.compile(r'<Security UserID="([^"]+)"')}


def evtx_counts_only(look, records, h, days):
    import dl_prof as P
    P.counts(look, [("records", records), ("chunks", h["chunks"]), ("days", len(days) or None)], 94, "Event log counts")


def look_evtx(look):
    """EVTX: the header, then every record (exact count, record ids, first and last time, per day) from the raw chunks; then, with
    python-evtx, each event's id, level, provider, channel and data. A record python-evtx cannot render is counted, never fatal."""
    import time as _t
    import dl_prof as P
    with open(look.path, "rb") as f:
        h = evtx_header(f.read(4096))
    raw, seen = [], set()
    for r in raw_records(look.path):   # a chunk can hold a stale copy of a record: one per record id
        if r[0] not in seen:
            seen.add(r[0])
            raw.append(r)
    times = [t for _, t, _ in raw if t]
    ids = [r for r, _, _ in raw]
    t0, t1 = (min(times), max(times)) if times else (None, None)
    est = max(0, h["next_record"] - 1)
    exact = bool(raw) and (est <= 0 or len(raw) >= 0.9 * est)
    records = len(raw) if exact else max(est, len(raw))
    if not exact:   # the record walk broke off (damaged or unusual chunks): the header's count and the chunk headers' times
        with open(look.path, "rb") as f:
            s0, s1 = evtx_span(f, h)
        t0, t1 = s0 or t0, s1 or t1
        look.flag("PARTIAL", "record walk", f"{len(raw):,} records walked, the header says about {est:,}", "counts below are from the header: an estimate")
    look.headline = f"Windows event log, {'' if exact else 'about '}{records:,} records" + (f", {t0:%Y-%m-%d %H:%M} to {t1:%Y-%m-%d %H:%M} UTC" if t0 and t1 else "")
    look.dims = f"{records:,} records"
    look.fact("records", records)
    look.line(f"Windows event log (EVTX {h['version']}): {records:,} records in {h['chunks']} chunks ({'counted record by record' if exact else 'about: from the header'})"
              + (f", from {t0:%Y-%m-%d %H:%M:%S} to {t1:%Y-%m-%d %H:%M:%S} UTC" if t0 and t1 else "")
              + (f"; record ids {min(ids):,} to {max(ids):,}" if ids else "") + ".", 92)
    if h["dirty"]:
        look.flag("DIRTY-LOG", "header", "the log was not closed cleanly", "the last records may be missing or incomplete")
    days = Counter(t.strftime("%Y-%m-%d") for t in times)
    if days:
        look.line("Records per day (UTC): " + "; ".join(f"{d} {n:,}" for d, n in sorted(days.items())), 70, "timeline")
    if ids and max(ids) - min(ids) + 1 != len(set(ids)):
        look.line(f"Record ids are not contiguous: {max(ids) - min(ids) + 1 - len(set(ids)):,} ids missing between {min(ids):,} and {max(ids):,} (a filtered export or cleared records).", 60)
    if not look.mod("Evtx"):
        look.skip("events: ids, providers, levels and messages", "python package python-evtx not importable" if not look.no_tools else "disabled by --no-tools", "Evtx")
        return evtx_counts_only(look, records, h, days)
    c = {k: Counter() for k in EV_FIELDS if k != "time"}
    pair_n, first, last = Counter(), {}, {}
    lvl_first, lvl_last = {}, {}
    rows, data_vals = [], Counter()
    failed = done = 0
    partial = False
    start = _t.time()
    try:
        from Evtx.Evtx import Evtx as EvtxFile
        with EvtxFile(str(look.path)) as log:
            for rec in log.records():
                if _t.time() - start > (300 if look.deep else 90):
                    partial = True
                    break
                try:
                    x = rec.xml()
                except Exception:   # python-evtx cannot render some templates (TypeError and others): count it, go on
                    failed += 1
                    continue
                done += 1
                got = {}
                for k, rx in EV_FIELDS.items():
                    m = rx.search(x)
                    got[k] = m.group(1) if m else "?"
                    if k != "time":
                        c[k][got[k]] += 1
                key = (got["provider"], got["id"])
                pair_n[key] += 1
                tm = got["time"][:19].replace("T", " ")
                first.setdefault(key, tm)
                last[key] = tm
                lvl_first.setdefault(got["level"], tm)
                lvl_last[got["level"]] = tm
                for nm, val in re.findall(r'<Data Name="([^"]+)">([^<]{1,80})</Data>', x)[:8]:
                    data_vals[f"{nm}={val}"] += 1
                if len(rows) < 3000:
                    msg = " | ".join(re.findall(r"<Data[^>]*>([^<]{1,200})</Data>", x)[:4])
                    rows.append(f"{tm} {LEVEL_NAMES.get(got['level'], got['level'])} {got['provider']} {got['id']}: {P.short(msg, 140)}")
    except Exception as e:
        look.fail("events (python-evtx)", "Evtx", e)
    if failed:
        look.flag("PARTIAL", "events", f"{failed:,} of {records:,} records could not be rendered by python-evtx", "their headers (count, ids, times) are still counted above")
    if partial:
        look.flag("PARTIAL", "events", f"time cap: {done:,} of {records:,} events read", "run --tier deep for more")
    if not done:
        return evtx_counts_only(look, records, h, days)
    lv = c["level"]
    P.counts(look, [("records", records), ("events read", done), ("events not renderable", failed or None), ("chunks", h["chunks"]), ("days", len(days) or None),
                    ("distinct event ids", len(c["id"])), ("providers", len(c["provider"])), ("channels", len(c["channel"])), ("computers", len(c["computer"]))]
             + [(f"{LEVEL_NAMES.get(k, k)} events", lv[k]) for k in sorted(lv)], 95, "Event log counts")
    look.line("Levels (count, first and last time): " + "; ".join(f"{LEVEL_NAMES.get(k, k)} ({k}) {n:,} ({lvl_first[k]} .. {lvl_last[k]})" for k, n in sorted(lv.items())), 91)
    look.line("Event ids: " + ", ".join(f"{k} x{v:,}" for k, v in c["id"].most_common(20)) + (f"; +{len(c['id']) - 20} more ids" if len(c["id"]) > 20 else ""), 89)
    look.line("Providers: " + ", ".join(f"{k} x{v:,}" for k, v in c["provider"].most_common(12)) + (f"; +{len(c['provider']) - 12} more" if len(c["provider"]) > 12 else "")
              + "; channels: " + ", ".join(f"{k} x{v:,}" for k, v in c["channel"].most_common(5)) + "; computers: " + ", ".join(f"{k} x{v:,}" for k, v in c["computer"].most_common(5)), 84)
    prow = [f"{p} {i} x{n:,} ({first[(p, i)]} .. {last[(p, i)]})" for (p, i), n in pair_n.most_common()]
    for k in range(0, min(len(prow), 600), 60):
        look.line("Provider + event id (count, first .. last time): " + "; ".join(prow[k:k + 60]), 34 - min(8, k // 60), "aggregates")
    if c["user"]:
        look.line("Security user ids: " + ", ".join(f"{k} x{v:,}" for k, v in c["user"].most_common(10)), 38)
    if data_vals:
        look.line("Most frequent event data values: " + ", ".join(f"{k} x{v:,}" for k, v in data_vals.most_common(30)), 32, "values")
    look.write_text("events.txt", "\n".join(rows), "rendered events in file order: time, level, provider, id, first data values (up to 3,000)", value=1)
    look.step("event ids, levels, providers", "python-evtx")


# ================================================================= PSD
PSD_MODES = {0: "bitmap", 1: "grayscale", 2: "indexed", 3: "RGB", 4: "CMYK", 7: "multichannel", 8: "duotone", 9: "Lab"}


def psd_header(b):
    if b[:4] != b"8BPS":
        raise ValueError("no 8BPS magic")
    ver, _, ch, h, w, depth, mode = struct.unpack_from(">H6sHIIHH", b, 4)
    return {"version": ver, "channels": ch, "height": h, "width": w, "depth": depth, "mode": PSD_MODES.get(mode, str(mode))}


def psd_extras(look):
    with open(look.path, "rb") as f:
        h = psd_header(f.read(32))
    look.line(f"Photoshop {'big ' if h['version'] == 2 else ''}document: {h['width']}x{h['height']}, {h['depth']} bits, {h['mode']}, {h['channels']} channels. The picture shown is the flattened preview; layers, text and smart objects need psd-tools.", 88)
    look.fact("psd", h)
    pt = look.mod("psd_tools")
    if not pt:
        look.skip("layers, hidden layers, text layers and smart objects", "python package psd-tools not importable" if not look.no_tools else "disabled by --no-tools", "psd_tools")
        return
    try:
        psd = pt.PSDImage.open(str(look.path))
        layers = list(psd.descendants())
        hidden = [ly.name for ly in layers if not ly.is_visible()]
        text = [ly.name for ly in layers if getattr(ly, "kind", "") == "type"]
        look.line(f"Layers: {len(layers)} ({len(hidden)} hidden, {len(text)} text). Hidden: {', '.join(hidden[:8])}.", 78)
        if hidden:
            look.flag("HIDDEN-LAYER", "psd", f"{len(hidden)} hidden layer(s): {', '.join(hidden[:4])}", "content not visible in the flattened picture")
        look.step("layers", "psd-tools")
    except Exception as e:
        look.fail("layers", "psd_tools", e)


# ================================================================= macros: oletools
def summarize_olevba(results):
    """olevba analyze_macros() rows (type, keyword, description) -> {'AutoExec': [...], 'Suspicious': [...], 'IOC': [...]}. Other kinds are counted."""
    out = {}
    for t, k, d in results:
        out.setdefault(t, []).append(k)
    return out


def olevba_facts(look, data, name):
    m = look.mod("oletools")
    if not m:   # the standard-library reader: decompresses the VBA modules itself
        import dl_vba
        if not dl_vba.vba_facts(look, data, name):
            look.skip("macro source: full oletools analysis", "python package oletools not importable" if not look.no_tools else "disabled by --no-tools", "oletools")
        return
    try:
        from oletools.olevba import VBA_Parser
        vp = VBA_Parser(name, data=data)
        if not vp.detect_vba_macros():
            look.line("oletools found no VBA macro source in the project.", 70)
            return
        res = vp.analyze_macros()
        s = summarize_olevba(res)
        auto = s.get("AutoExec", [])
        sus = s.get("Suspicious", [])
        if auto:
            look.flag("AUTO-EXEC-MACRO", name, ", ".join(sorted(set(auto))[:6]), "runs by itself when the file is opened (macro security permitting); never open it to see")
        if sus:
            look.flag("SUSPICIOUS-MACRO", name, ", ".join(sorted(set(sus))[:8]), "calls that download, run or write files")
        look.line(f"Macros (oletools): auto-run {sorted(set(auto)) or 'none'}; suspicious {sorted(set(sus))[:8] or 'none'}; indicators {sorted(set(s.get('IOC', [])))[:4] or 'none'}.", 88)
        look.step("macro analysis", "oletools")
    except Exception as e:
        look.fail("macro analysis", "oletools", e)
        import dl_vba
        dl_vba.vba_facts(look, data, name)


# ================================================================= glTF validator
def parse_gltf_report(doc):
    """gltf_validator JSON -> {'errors': n, 'warnings': n, 'infos': n, 'messages': [(severity, code, pointer)]}."""
    if isinstance(doc, str):
        doc = json.loads(doc)
    iss = doc.get("issues", {})
    msgs = [({0: "error", 1: "warning", 2: "info", 3: "hint"}.get(m.get("severity"), "?"), m.get("code", ""), m.get("pointer", "")) for m in iss.get("messages", [])]
    return {"errors": iss.get("numErrors", 0), "warnings": iss.get("numWarnings", 0), "infos": iss.get("numInfos", 0), "messages": msgs}


def run_gltf_validator(look):
    t = look.tool("gltf-validator") or look.tool("gltf_validator")
    if not t:
        look.skip("glTF specification validation (Khronos validator)", "gltf-validator not found" if not look.no_tools else "disabled by --no-tools", "gltf-validator")
        return
    r, out, _ = look.run_text([t, str(look.path), "-o"])
    if r is None or not out.strip():
        return
    try:
        p = parse_gltf_report(out[out.index("{"):])
    except (ValueError, json.JSONDecodeError) as e:
        look.fail("glTF validation", "gltf-validator", e)
        return
    look.line(f"glTF validator: {p['errors']} errors, {p['warnings']} warnings, {p['infos']} infos." + (" First: " + "; ".join(f"{s} {c} at {ptr}" for s, c, ptr in p["messages"][:4]) if p["messages"] else ""), 82)
    if p["errors"]:
        look.flag("INVALID-GLTF", "validator", f"{p['errors']} error(s): {p['messages'][0][1] if p['messages'] else ''}", "viewers may refuse or render it wrongly")
    look.step("glTF validation", "gltf-validator")


# ================================================================= trimesh
def trimesh_facts(look):
    tm = look.mod("trimesh")
    if not tm:
        look.skip("mesh quality: watertight, volume, holes, scale", "python package trimesh not importable" if not look.no_tools else "disabled by --no-tools", "trimesh")
        return
    try:
        mesh = tm.load(str(look.path), force="mesh")
        wt = bool(mesh.is_watertight)
        ext = [round(float(x), 3) for x in mesh.extents]
        vol = float(mesh.volume) if wt else None
        look.line(f"Mesh (trimesh): {len(mesh.vertices)} vertices, {len(mesh.faces)} faces, extents {ext}, watertight {wt}" + (f", volume {vol:.3f}" if vol is not None else "") + f", {len(mesh.split(only_watertight=False)) if len(mesh.faces) < 200000 else '?'} separate bodies.", 74)
        if not wt:
            look.flag("NOT-WATERTIGHT", "mesh", "the surface has holes or non-manifold edges", "not printable as is; volume is meaningless")
        look.step("mesh checks", "trimesh")
    except Exception as e:
        look.fail("mesh checks", "trimesh", e)


# ================================================================= Magika
def magika_second_opinion(look):
    mk = look.mod("magika")
    if not mk:
        look.skip("second opinion on the file type (Magika)", "python package magika not importable" if not look.no_tools else "disabled by --no-tools", "magika")
        return
    try:
        res = mk.Magika().identify_path(look.path)
        out = res.output if hasattr(res, "output") else res
        label = getattr(out, "label", None) or getattr(out, "ct_label", "?")
        look.line(f"Magika (a content-type model) calls this {label} (score {getattr(res, 'score', '?')}); the header-based detector said {look.type}/{look.subtype}.", 70)
        look.step("second opinion on type", "magika")
    except Exception as e:
        look.fail("second opinion on type", "magika", e)


# ================================================================= header detector and content model disagree
MODEL_READERS = {"csv": ("data", "csv"), "tsv": ("data", "tsv"), "json": ("data", "json"), "jsonl": ("data", "jsonl"), "xml": ("data", "xml"), "yaml": ("data", "yaml"),
                 "toml": ("data", "toml"), "ini": ("data", "ini"), "html": ("web", "html"), "sqlite": ("data", "sqlite"), "parquet": ("data", "parquet"),
                 "pdf": ("pdf", "pdf"), "zip": ("archive", "zip"), "gzip": ("archive", "gzip"), "tar": ("archive", "tar"), "png": ("image", "png"), "jpeg": ("image", "jpeg"),
                 "gif": ("image", "gif"), "pcap": ("data", "pcap"), "ics": ("email", "ics"), "vcf": ("email", "vcf"), "svg": ("image", "svg"), "ttf": ("font", "ttf")}


def reclassify(look):
    """The header detector found no signature (unknown/binary), but a content model (Magika) or `file -b` names a type. Try the reader for that type
    instead of stopping at an unknown-type exit: a name with a reader switches look.type/subtype; text-like content is read as lenient text.
    -> True when the type was switched."""
    label, score, is_text, source = None, 0.0, False, ""
    mk = look.mod("magika")
    if mk:
        try:
            res = mk.Magika().identify_path(look.path)
            out = res.output if hasattr(res, "output") else res
            label = getattr(out, "label", None) or getattr(out, "ct_label", None)
            score, is_text, source = float(getattr(res, "score", 0) or 0), bool(getattr(out, "is_text", False)), "Magika"
        except Exception as e:
            look.fail("second opinion on type", "magika", e)
    if not label:
        fb = look.tool("file")
        if fb:
            r, out_, _ = look.run_text([fb, "-b", str(look.path)])
            said = (out_ or "").strip() if r is not None and r.returncode == 0 else ""
            low = said.lower()
            if said and "text" in low and "data" not in low.split(",")[0]:
                label, score, is_text, source = "txt", 0.5, True, "`file -b`"
    if not label or label in ("unknown", "undefined", "randombytes", "empty"):
        return False
    if label in MODEL_READERS and score >= 0.5:
        t, st = MODEL_READERS[label]
    elif is_text and score >= 0.3:
        t, st = "code", "text"
        look.fact("text_by_content_model", True)
    else:
        return False
    look.line(f"The header detector found no known signature, but {source} calls this {label} (score {score:.2f}), so it is read as {t}/{st} instead of stopping as unknown.", 70)
    look.fact("reclassified_from", f"unknown/binary -> {t}/{st} ({source} {label})")
    look.type, look.subtype = t, st
    look.detector["magic"] = f"{source}: {label}"
    look.step("second opinion on type", source)
    return True
