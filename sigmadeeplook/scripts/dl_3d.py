"""SigmaDeepLook: 3D files (glb, gltf, stl, obj, ply, usd, fbx, blend). Stdlib parsers; a Pillow software renderer makes the pictures.

The renderer is flat-shaded and orthographic: it shows shape and proportion, not materials. Blender and USD tools are not run.
"""
import base64
import json
import math
import os
import re
import struct
from pathlib import Path

import dl_core as core

MAX_TRIS_RENDER = 200000
MAX_TRIS_PARSE = 2000000
COMP = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def parse_glb(b):
    magic, ver, length = struct.unpack_from("<4sII", b, 0)
    off, js, binchunk = 12, None, b""
    while off + 8 <= len(b):
        clen, ctype = struct.unpack_from("<I4s", b, off)
        data = b[off + 8: off + 8 + clen]
        if ctype == b"JSON":
            js = json.loads(data.decode("utf-8"))
        elif ctype == b"BIN\0":
            binchunk = data
        off += 8 + clen
    return js, binchunk, ver


def load_buffers(js, binchunk, base_dir):
    bufs = []
    for i, bf in enumerate(js.get("buffers", [])):
        uri = bf.get("uri")
        if uri is None:
            bufs.append(binchunk)
        elif uri.startswith("data:"):
            bufs.append(base64.b64decode(uri.split(",", 1)[1]))
        else:
            p = (Path(base_dir) / uri).resolve()
            if p.is_file() and str(p).startswith(str(Path(base_dir).resolve())):
                bufs.append(p.read_bytes())
            else:
                bufs.append(b"")
    return bufs


def read_accessor(js, bufs, idx):
    a = js["accessors"][idx]
    bv = js["bufferViews"][a["bufferView"]]
    fmt, size = COMP[a["componentType"]]
    n = NCOMP[a["type"]]
    stride = bv.get("byteStride") or size * n
    base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    buf = bufs[bv["buffer"]]
    out = []
    for i in range(a["count"]):
        out.append(struct.unpack_from("<" + fmt * n, buf, base + i * stride))
    return out


def gltf_mesh(look, js, bufs):
    """-> (triangles as list of 3 vertex tuples, stats). Node transforms are ignored."""
    tris, prims, bad = [], 0, 0
    for m in js.get("meshes", []):
        for p in m.get("primitives", []):
            if p.get("mode", 4) != 4 or "POSITION" not in p.get("attributes", {}):
                continue
            prims += 1
            try:
                pos = read_accessor(js, bufs, p["attributes"]["POSITION"])
                idx = [i[0] for i in read_accessor(js, bufs, p["indices"])] if "indices" in p else list(range(len(pos)))
            except (KeyError, struct.error, IndexError) as e:
                bad += 1
                look.flag("GLTF-INVALID", "accessor", f"{type(e).__name__}: {e}"[:80], "an accessor points outside its buffer")
                continue
            for i in range(0, len(idx) - 2, 3):
                try:
                    tris.append((pos[idx[i]], pos[idx[i + 1]], pos[idx[i + 2]]))
                except IndexError:
                    bad += 1
                    break
            if len(tris) > MAX_TRIS_PARSE:
                break
    return tris, {"primitives": prims, "invalid": bad}


def look_3d(look):
    st = look.subtype
    b = open(look.path, "rb").read(256 << 20)
    tris, extra = [], {}
    if st in ("glb", "gltf"):
        try:
            if st == "glb":
                js, binchunk, ver = parse_glb(b)
            else:
                js, binchunk, ver = json.loads(b.decode("utf-8", "replace")), b"", 2
            bufs = load_buffers(js, binchunk, look.path.parent)
            tris, extra = gltf_mesh(look, js, bufs)
            for k in ("nodes", "meshes", "materials", "textures", "images", "animations", "skins", "cameras"):
                look.fact(k, len(js.get(k, [])))
            look.fact("gltf_version", js.get("asset", {}).get("version"))
            look.fact("generator", js.get("asset", {}).get("generator", ""))
            look.line(f"glTF {js.get('asset', {}).get('version', '?')} ({st}): {len(js.get('nodes', []))} nodes, {len(js.get('meshes', []))} meshes, "
                      f"{len(js.get('materials', []))} materials, {len(js.get('textures', []))} textures, {len(js.get('animations', []))} animations.")
            ext_req = js.get("extensionsRequired", [])
            if ext_req:
                look.flag("EXTENSIONS-REQUIRED", "glTF", ", ".join(ext_req), "a viewer without these extensions will not show the model right")
            for im in js.get("images", []):
                if "uri" in im and not im["uri"].startswith("data:"):
                    p = (look.path.parent / im["uri"])
                    if not p.exists():
                        look.flag("MISSING-TEXTURE", im["uri"], "external image not found next to the file", "")
            validate_gltf(look, js, bufs)
        except (ValueError, KeyError, struct.error) as e:
            look.flag("PARSE-ERROR", "glTF", f"{type(e).__name__}: {e}"[:100], "")
    elif st in ("stl", "stl-ascii"):
        tris = parse_stl(b, st == "stl-ascii")
        hdr = ""
        if st != "stl-ascii":
            hdr = b[:80].split(b"\0")[0].decode("latin-1").strip()
            hdr = f" Header text: {hdr!r}." if hdr else " Empty 80-byte header."
        else:
            first = b[:200].decode("latin-1").splitlines()[0].strip()
            hdr = f" First line: {first!r}."
        look.line(f"STL ({'ASCII' if st == 'stl-ascii' else 'binary'}): {len(tris)} triangles.{hdr} STL has no units and no colour.")
    elif st == "obj":
        tris, c = parse_obj(b.decode("utf-8", "replace"))
        look.fact("vertices", c["v"])
        look.fact("faces", c["f"])
        look.line(f"OBJ: {c['v']} vertices, {c['f']} faces ({len(tris)} triangles), {c['vt']} texture coords, {c['vn']} normals; materials: {c['mtl'] or 'none'}.")
        if c["mtl"]:
            look.flag("EXTERNAL-MATERIAL", c["mtl"], "mtllib", "materials live in a separate .mtl file")
    elif st == "ply":
        tris = parse_ply(look, b)
    elif st == "usd" and b[:5] == b"#usda":
        txt = b.decode("utf-8", "replace")
        prims = re.findall(r'(?m)^\s*def\s+(\w+)\s+"([^"]+)"', txt)
        look.fact("prims", len(prims))
        look.line(f"USD (text): {len(prims)} prims. First: " + ", ".join(f"{t} {n}" for t, n in prims[:8]))
        look.skip("USD checks and renders", "USD tools (usdcat, usdchecker, usdrecord) are not run by this skill", None, "pip install usd-core")
    elif st == "fbx":
        ver = struct.unpack_from("<I", b, 23)[0] if len(b) > 27 else 0
        look.line(f"FBX binary, version {ver}. Header facts only.")
        look.fact("fbx_version", ver)
        look.skip("FBX contents and pictures", "needs Blender or an FBX SDK; not run", "blender")
    elif st == "blend":
        hdr = b[:12].decode("latin-1")
        look.line(f"Blender file, header {hdr!r}. Header facts only.")
        look.skip(".blend contents and pictures", "needs Blender (run headless with --factory-startup); not run", "blender")
    else:
        look.line(f"3D file of kind {st}; header facts only.")
        look.skip("3D contents", f"no reader for {st}", None, "")
    import dl_adapt
    if st in ("glb", "gltf"):
        dl_adapt.run_gltf_validator(look)
    if st in ("stl", "stl-ascii", "obj", "ply", "glb", "gltf"):
        dl_adapt.trimesh_facts(look)
    if tris:
        stats = mesh_stats(look, tris)
        look.fact("triangles", len(tris))
        look.fact("bbox", stats["bbox"])
        look.line(f"{len(tris)} triangles; bounding box {stats['bbox']['min']} to {stats['bbox']['max']} (size {stats['bbox']['size']}).")
        look.line(f"Mesh measures: surface area {stats['surface_area']:,.3f}, signed volume {stats['signed_volume']:,.3f} (a true volume only when watertight), "
                  + (f"centroid {stats['centroid']}, " if stats.get("centroid") else "") + f"{stats['unique_vertices']} unique vertices, {stats['degenerate_triangles']} zero-area triangles (units are those of the file).", 61)
        if stats.get("watertight") is not None:
            look.fact("watertight", stats["watertight"])
            look.line("Watertight (every edge shared by exactly two triangles): " + ("yes" if stats["watertight"] else f"NO ({stats['open_edges']} open edges)"))
            if not stats["watertight"]:
                look.flag("NOT-WATERTIGHT", "mesh", f"{stats['open_edges']} open edges", "volume, centre of mass and 3D-printing results are not meaningful")
        look.write_text("model.json", json.dumps({**stats, **extra}, indent=1), "mesh statistics", "json")
        render_views(look, tris)
    look.ask_human("What do you need from this model: a check, a fix, a conversion, or pictures?", "Is the unit metres, millimetres or inches?")


def validate_gltf(look, js, bufs):
    problems = []
    for i, a in enumerate(js.get("accessors", [])):
        bv = js.get("bufferViews", [])
        if "bufferView" not in a or a["bufferView"] >= len(bv):
            continue
        v = bv[a["bufferView"]]
        fmt, size = COMP.get(a["componentType"], ("B", 1))
        need = a.get("byteOffset", 0) + (v.get("byteStride") or size * NCOMP[a["type"]]) * (a["count"] - 1) + size * NCOMP[a["type"]]
        if need > v["byteLength"]:
            problems.append(f"accessor {i} needs {need} bytes, view has {v['byteLength']}")
        if v["buffer"] < len(bufs) and v.get("byteOffset", 0) + v["byteLength"] > len(bufs[v["buffer"]]) > 0:
            problems.append(f"bufferView {a['bufferView']} runs past its buffer")
    out = {"checked": "accessor and bufferView bounds only (not the full Khronos validator)", "problems": problems}
    look.write_text("validate.json", json.dumps(out, indent=1), "basic glTF bounds check", "json")
    for p in problems[:5]:
        look.flag("GLTF-INVALID", "bounds", p, "")


def parse_stl(b, ascii_):
    tris = []
    if ascii_:
        vs = re.findall(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", b)
        v = [tuple(float(x) for x in t) for t in vs]
        return [tuple(v[i:i + 3]) for i in range(0, len(v) - 2, 3)]
    n = struct.unpack_from("<I", b, 80)[0]
    for i in range(min(n, MAX_TRIS_PARSE)):
        d = struct.unpack_from("<12f", b, 84 + 50 * i)
        tris.append((d[3:6], d[6:9], d[9:12]))
    return tris


def parse_obj(text):
    v, c, tris = [], {"v": 0, "f": 0, "vt": 0, "vn": 0, "mtl": ""}, []
    faces = []
    for line in text.splitlines():
        if line.startswith("v "):
            p = line.split()
            v.append((float(p[1]), float(p[2]), float(p[3])))
            c["v"] += 1
        elif line.startswith("vt "):
            c["vt"] += 1
        elif line.startswith("vn "):
            c["vn"] += 1
        elif line.startswith("mtllib "):
            c["mtl"] = line.split(None, 1)[1].strip()
        elif line.startswith("f "):
            c["f"] += 1
            faces.append([int(x.split("/")[0]) for x in line.split()[1:]])
    for f in faces:
        idx = [i - 1 if i > 0 else len(v) + i for i in f]
        for k in range(1, len(idx) - 1):
            try:
                tris.append((v[idx[0]], v[idx[k]], v[idx[k + 1]]))
            except IndexError:
                pass
    return tris, c


def parse_ply(look, b):
    end = b.find(b"end_header")
    head = b[:end].decode("latin-1")
    nv = int(re.search(r"element vertex (\d+)", head).group(1)) if "element vertex" in head else 0
    nf = int(re.search(r"element face (\d+)", head).group(1)) if "element face" in head else 0
    fmt = re.search(r"format (\S+)", head).group(1) if "format" in head else "?"
    look.fact("vertices", nv)
    look.fact("faces", nf)
    look.line(f"PLY ({fmt}): {nv} vertices, {nf} faces.")
    if fmt != "ascii":
        look.skip("PLY geometry and pictures", f"only ASCII PLY is parsed (this one is {fmt})", None, "")
        return []
    body = b[end:].split(b"\n")[1:]
    verts = [tuple(float(x) for x in ln.split()[:3]) for ln in body[:nv]]
    tris = []
    for ln in body[nv:nv + nf]:
        p = ln.split()
        idx = [int(x) for x in p[1:1 + int(p[0])]]
        for k in range(1, len(idx) - 1):
            tris.append((verts[idx[0]], verts[idx[k]], verts[idx[k + 1]]))
    return tris


def mesh_stats(look, tris):
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    mn = [round(min(xs), 4), round(min(ys), 4), round(min(zs), 4)]
    mx = [round(max(xs), 4), round(max(ys), 4), round(max(zs), 4)]
    out = {"triangles": len(tris), "bbox": {"min": mn, "max": mx, "size": [round(a - b, 4) for a, b in zip(mx, mn)]}}
    area = vol = 0.0
    cx = cy = cz = 0.0
    degenerate = 0
    for a, b, c in tris:
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        ar = 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)
        if ar < 1e-12:
            degenerate += 1
        area += ar
        d = (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
        vol += d
        cx += d * (a[0] + b[0] + c[0]) / 4.0
        cy += d * (a[1] + b[1] + c[1]) / 4.0
        cz += d * (a[2] + b[2] + c[2]) / 4.0
    out["surface_area"] = round(area, 4)
    out["signed_volume"] = round(vol, 4)
    out["centroid"] = [round(cx / vol, 4), round(cy / vol, 4), round(cz / vol, 4)] if abs(vol) > 1e-12 else None
    out["degenerate_triangles"] = degenerate
    out["unique_vertices"] = len({(round(v[0] * 1e5), round(v[1] * 1e5), round(v[2] * 1e5)) for t in tris for v in t}) if len(tris) <= MAX_TRIS_PARSE else None
    if len(tris) <= MAX_TRIS_PARSE:
        q = lambda v: (round(v[0] * 1e5), round(v[1] * 1e5), round(v[2] * 1e5))
        edges = {}
        for t in tris:
            k = [q(v) for v in t]
            for a, c in ((0, 1), (1, 2), (2, 0)):
                e = (k[a], k[c]) if k[a] <= k[c] else (k[c], k[a])
                edges[e] = edges.get(e, 0) + 1
        open_edges = sum(1 for n in edges.values() if n != 2)
        out["watertight"] = open_edges == 0
        out["open_edges"] = open_edges
    return out


VIEWS = [("front", 0, 0), ("right", 90, 0), ("back", 180, 0), ("left", 270, 0), ("top", 0, 89), ("iso", 35, 30)]


def render_views(look, tris):
    """Six fixed views with a software painter's algorithm. Needs Pillow; numpy makes it fast."""
    Image = None
    pil = look.mod("PIL")
    if not pil:
        look.skip("pictures of the model", "Pillow not importable" if not look.no_tools else "disabled by --no-tools", "PIL")
        return
    from PIL import Image, ImageDraw
    if len(tris) > MAX_TRIS_RENDER:
        step = len(tris) // MAX_TRIS_RENDER + 1
        tris = tris[::step]
        look.flag("SAMPLED", "render", f"every {step}th triangle", "the render shows a sample of a very dense mesh")
    np = look.mod("numpy")
    S = 640
    allv = [v for t in tris for v in t]
    cx = [(min(v[i] for v in allv) + max(v[i] for v in allv)) / 2 for i in range(3)]
    rad = max(max(abs(v[i] - cx[i]) for v in allv) for i in range(3)) or 1.0
    thumbs = []
    for name, az, el in VIEWS:
        a, e = math.radians(az), math.radians(el)
        ca, sa, ce, se = math.cos(a), math.sin(a), math.cos(e), math.sin(e)

        def tf(v):
            x, y, z = v[0] - cx[0], v[1] - cx[1], v[2] - cx[2]
            x2, z2 = x * ca + z * sa, -x * sa + z * ca     # yaw around Y (Y up)
            y3, z3 = y * ce - z2 * se, y * se + z2 * ce     # pitch around X
            return x2, y3, z3
        proj = [tuple(tf(v) for v in t) for t in tris]
        proj.sort(key=lambda t: (t[0][2] + t[1][2] + t[2][2]))
        im = Image.new("RGB", (S, S), (245, 245, 245))
        d = ImageDraw.Draw(im)
        k = S * 0.42 / rad
        for t in proj:
            ax, ay, az_ = (t[1][i] - t[0][i] for i in range(3))
            bx, by, bz = (t[2][i] - t[0][i] for i in range(3))
            nx, ny, nz = ay * bz - az_ * by, az_ * bx - ax * bz, ax * by - ay * bx
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            lum = abs(nz / ln) * 0.7 + abs(ny / ln) * 0.2 + 0.1
            c = int(60 + 170 * min(1.0, lum))
            d.polygon([(S / 2 + p[0] * k, S / 2 - p[1] * k) for p in t], fill=(c, c, int(c * 0.95)), outline=(c - 25, c - 25, c - 25))
        d.text((8, 6), name, fill=(20, 20, 20))
        p = look.path_for(f"views/{name}.png")
        im.save(p)
        thumbs.append(im)
    sheet = Image.new("RGB", (S * 3, S * 2), "white")
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % 3) * S, (i // 3) * S))
    # the sheet is 1920 x 1280: inside the 2000 px budget
    p = look.path_for("sheet-views.jpg")
    sheet.save(p, quality=88)
    look.add(p, "image", "six fixed views (front, right, back, left, top, iso), flat shaded, orthographic")
    for name, _, _ in VIEWS:
        look.add(look.out / "views" / f"{name}.png", "internal", f"view {name}")
    look.step("software render (Pillow)", "Pillow")
