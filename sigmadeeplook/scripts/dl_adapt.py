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


def look_evtx(look):
    with open(look.path, "rb") as f:
        h = evtx_header(f.read(4096))
        t0, t1 = evtx_span(f, h)
    records = max(0, h["next_record"] - 1)
    look.headline = f"Windows event log, about {records} records" + (f", {t0:%Y-%m-%d} to {t1:%Y-%m-%d}" if t0 and t1 else "")
    look.dims = f"{records} records"
    look.fact("records", records)
    look.line(f"Windows event log (EVTX {h['version']}): about {records} records in {h['chunks']} chunks" + (f", from {t0:%Y-%m-%d %H:%M} to {t1:%Y-%m-%d %H:%M} UTC" if t0 and t1 else "") + ".", 90)
    if h["dirty"]:
        look.flag("DIRTY-LOG", "header", "the log was not closed cleanly", "the last records may be missing or incomplete")
    ev = look.mod("evtx")
    if not ev:
        look.skip("events: ids, providers, levels and messages", "python package python-evtx not importable" if not look.no_tools else "disabled by --no-tools", "evtx")
        return
    try:
        from evtx import PyEvtxParser
        ids, levels, prov = Counter(), Counter(), Counter()
        errors = []
        p = PyEvtxParser(str(look.path))
        for i, rec in enumerate(p.records()):
            if i >= 20000:
                break
            x = rec["data"]
            m = re.search(r"<EventID[^>]*>(\d+)</EventID>", x)
            ids[m.group(1) if m else "?"] += 1
            lv = re.search(r"<Level>(\d+)</Level>", x)
            levels[lv.group(1) if lv else "?"] += 1
            pv = re.search(r'<Provider Name="([^"]+)"', x)
            prov[pv.group(1) if pv else "?"] += 1
            if lv and lv.group(1) in ("1", "2") and len(errors) < 5:
                errors.append(x[:300])
        look.line("Top event ids: " + ", ".join(f"{k} x{v}" for k, v in ids.most_common(8)) + "; providers: " + ", ".join(f"{k} x{v}" for k, v in prov.most_common(4)) + f"; level counts {dict(levels)} (1 critical, 2 error, 3 warning, 4 info).", 80)
        if errors:
            look.write_text("errors.xml", "\n".join(errors), "first error and critical events (XML)", value=6)
        look.step("event ids and levels", "python-evtx")
    except Exception as e:
        look.fail("events", "evtx", e)


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
    if not m:
        look.skip("macro source: auto-run routines, suspicious calls and addresses", "python package oletools not importable" if not look.no_tools else "disabled by --no-tools", "oletools")
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
