"""SigmaDeepLook: structure readers for Java class files and WebAssembly modules (stdlib only, the input is never run).

Both formats are a tagged table of sections: the reader walks the table, counts what each section holds and names the public surface
(imports, exports, fields, methods), because the bytes of the code themselves answer almost no question.
"""
import struct

JAVA_RELEASE = {45: "1.1", 46: "1.2", 47: "1.3", 48: "1.4", 49: "5", 50: "6", 51: "7", 52: "8"}
CLASS_FLAGS = ((0x1, "public"), (0x10, "final"), (0x20, "super"), (0x200, "interface"), (0x400, "abstract"), (0x1000, "synthetic"), (0x2000, "annotation"), (0x4000, "enum"), (0x8000, "module"))
MEMBER_FLAGS = ((0x1, "public"), (0x2, "private"), (0x4, "protected"), (0x8, "static"), (0x10, "final"), (0x20, "synchronized"), (0x40, "volatile"), (0x80, "transient"),
                (0x100, "native"), (0x400, "abstract"), (0x800, "strictfp"), (0x1000, "synthetic"))
PRIM = {"B": "byte", "C": "char", "D": "double", "F": "float", "I": "int", "J": "long", "S": "short", "Z": "boolean", "V": "void"}


def release_of(major):
    return JAVA_RELEASE.get(major, str(major - 44) if major > 52 else "?")


def flags_text(v, table):
    return " ".join(n for bit, n in table if v & bit)


def _type(d, i=0):
    dims = 0
    while d[i] == "[":
        dims += 1
        i += 1
    if d[i] == "L":
        j = d.index(";", i)
        t, i = d[i + 1:j].replace("/", ".").rsplit(".", 1)[-1], j + 1
    else:
        t, i = PRIM.get(d[i], d[i]), i + 1
    return t + "[]" * dims, i


def descriptor(d):
    """'(JLjava/lang/String;)V' -> ('long, String', 'void')"""
    try:
        if d.startswith("("):
            i, args = 1, []
            while d[i] != ")":
                t, i = _type(d, i)
                args.append(t)
            return ", ".join(args), _type(d, i + 1)[0]
        return "", _type(d)[0]
    except (IndexError, ValueError):
        return "", d


def parse_class(b):
    """-> dict with version, flags, names, fields, methods, attributes; raises ValueError on a malformed file."""
    if b[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError("not a class file")
    minor, major, n = struct.unpack(">HHH", b[4:10])
    pool, i, k = [None] * n, 10, 1
    while k < n:
        tag = b[i]
        i += 1
        if tag == 1:
            ln = struct.unpack(">H", b[i:i + 2])[0]
            pool[k] = ("utf8", b[i + 2:i + 2 + ln].decode("utf-8", "replace"))
            i += 2 + ln
        elif tag in (3, 4):
            pool[k] = ("int" if tag == 3 else "float", struct.unpack(">i" if tag == 3 else ">f", b[i:i + 4])[0])
            i += 4
        elif tag in (5, 6):
            pool[k] = ("long" if tag == 5 else "double", struct.unpack(">q" if tag == 5 else ">d", b[i:i + 8])[0])
            i += 8
            k += 1
        elif tag in (7, 8, 16, 19, 20):
            pool[k] = ({7: "class", 8: "string", 16: "mtype", 19: "module", 20: "package"}[tag], struct.unpack(">H", b[i:i + 2])[0])
            i += 2
        elif tag in (9, 10, 11, 12, 17, 18):
            pool[k] = ("ref", struct.unpack(">HH", b[i:i + 4]))
            i += 4
        elif tag == 15:
            pool[k] = ("mhandle", b[i])
            i += 3
        else:
            raise ValueError(f"unknown constant tag {tag}")
        k += 1

    def utf(ix):
        e = pool[ix] if 0 < ix < n else None
        return e[1] if e and e[0] == "utf8" else "?"

    def cname(ix):
        e = pool[ix] if 0 < ix < n else None
        return utf(e[1]).replace("/", ".") if e and e[0] == "class" else "?"

    def const(ix):
        e = pool[ix] if 0 < ix < n else None
        if not e:
            return "?"
        if e[0] == "string":
            return repr(utf(e[1]))
        return e[1]

    flags, this, sup, ni = struct.unpack(">HHHH", b[i:i + 8])
    i += 8
    ifaces = []
    for _ in range(ni):
        ifaces.append(cname(struct.unpack(">H", b[i:i + 2])[0]))
        i += 2

    def attrs(i, count):
        out = {}
        for _ in range(count):
            nm, ln = struct.unpack(">HI", b[i:i + 6])
            out.setdefault(utf(nm), []).append(b[i + 6:i + 6 + ln])
            i += 6 + ln
        return out, i

    def members(i):
        cnt = struct.unpack(">H", b[i:i + 2])[0]
        i += 2
        out = []
        for _ in range(cnt):
            fl, nm, ds, ac = struct.unpack(">HHHH", b[i:i + 8])
            at, i = attrs(i + 8, ac)
            out.append({"flags": fl, "name": utf(nm), "desc": utf(ds), "attrs": at})
        return out, i

    fields, i = members(i)
    methods, i = members(i)
    ac = struct.unpack(">H", b[i:i + 2])[0]
    cattrs, i = attrs(i + 2, ac)
    for f in fields:
        cv = f["attrs"].get("ConstantValue")
        f["const"] = const(struct.unpack(">H", cv[0][:2])[0]) if cv else None
    for m in methods:
        code = m["attrs"].get("Code")
        m["code"] = struct.unpack(">I", code[0][4:8])[0] if code else None
    src = cattrs.get("SourceFile")
    return {"minor": minor, "major": major, "release": release_of(major), "flags": flags, "name": cname(this), "super": cname(sup) if sup else "",
            "interfaces": ifaces, "fields": fields, "methods": methods, "pool": n - 1, "attrs": sorted(cattrs),
            "source": utf(struct.unpack(">H", src[0][:2])[0]) if src else "", "bootstrap": len(cattrs.get("BootstrapMethods", [])) and struct.unpack(">H", cattrs["BootstrapMethods"][0][:2])[0]}


def class_lines(c):
    kind = "interface" if c["flags"] & 0x200 else "enum" if c["flags"] & 0x4000 else "class"
    lines = [f"Java {kind} {c['name']}" + (f" extends {c['super']}" if c["super"] and c["super"] != "java.lang.Object" else "") + (f" implements {', '.join(c['interfaces'])}" if c["interfaces"] else "")
             + f"; class file version {c['major']}.{c['minor']} = Java {c['release']}; flags: {flags_text(c['flags'], CLASS_FLAGS) or 'none'}; {c['pool']} constant-pool entries"
             + (f"; source file {c['source']}" if c["source"] else "") + "."]
    f = []
    for x in c["fields"]:
        t = descriptor(x["desc"])[1]
        f.append(f"{flags_text(x['flags'], MEMBER_FLAGS)} {t} {x['name']}" + (f" = {x['const']}" if x["const"] is not None else ""))
    lines.append(f"Fields ({len(f)}): " + "; ".join(f) + "." if f else "Fields (0): none.")
    m = []
    for x in c["methods"]:
        args, ret = descriptor(x["desc"])
        m.append(f"{flags_text(x['flags'], MEMBER_FLAGS)} {ret} {x['name']}({args})" + (f" [{x['code']} bytes of code]" if x["code"] is not None else ""))
    lines.append(f"Methods ({len(m)}): " + "; ".join(m) + "." if m else "Methods (0): none.")
    pub = sum(1 for x in c["methods"] if x["flags"] & 1)
    lines.append(f"Method visibility: {pub} public, {sum(1 for x in c['methods'] if x['flags'] & 4)} protected, {sum(1 for x in c['methods'] if x['flags'] & 2)} private, "
                 f"{sum(1 for x in c['methods'] if x['flags'] & 8)} static; {sum(1 for x in c['methods'] if x['flags'] & 0x1000)} synthetic (compiler-made, e.g. lambdas).")
    if c["attrs"]:
        lines.append("Class attributes: " + ", ".join(c["attrs"]) + (f"; {c['bootstrap']} bootstrap methods (lambdas or string concatenation)" if c["bootstrap"] else "") + ".")
    return lines


# ---- WebAssembly
WASM_SECTIONS = {0: "custom", 1: "type", 2: "import", 3: "function", 4: "table", 5: "memory", 6: "global", 7: "export", 8: "start", 9: "element", 10: "code", 11: "data", 12: "datacount", 13: "tag"}
WASM_KINDS = {0: "function", 1: "table", 2: "memory", 3: "global", 4: "tag"}
WASM_TYPES = {0x7F: "i32", 0x7E: "i64", 0x7D: "f32", 0x7C: "f64", 0x7B: "v128", 0x70: "funcref", 0x6F: "externref"}


def leb(b, i):
    r = s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        s += 7
        if not x & 0x80:
            return r, i


def _name(b, i):
    n, i = leb(b, i)
    return b[i:i + n].decode("utf-8", "replace"), i + n


def _limits(b, i):
    fl, i = leb(b, i)
    mn, i = leb(b, i)
    mx = None
    if fl & 1:
        mx, i = leb(b, i)
    return (mn, mx), i


def parse_wasm(b):
    if b[:4] != b"\0asm":
        raise ValueError("not a wasm module")
    ver = struct.unpack("<I", b[4:8])[0]
    i, secs, imports, exports, customs = 8, [], [], [], []
    info = {"version": ver, "sections": secs, "imports": imports, "exports": exports, "customs": customs, "types": 0, "functions": 0, "tables": 0, "memories": [],
            "globals": 0, "start": None, "data": 0, "elements": 0, "code": 0, "imported_funcs": 0, "names": 0, "producers": ""}
    while i < len(b):
        sid, i = b[i], i + 1
        ln, i = leb(b, i)
        body, end = i, i + ln
        nm = WASM_SECTIONS.get(sid, f"unknown{sid}")
        count = None
        try:
            if sid in (1, 2, 3, 4, 5, 6, 7, 9, 10, 11):
                count, j = leb(b, body)
                if sid == 1:
                    info["types"] = count
                elif sid == 2:
                    for _ in range(count):
                        mod, j = _name(b, j)
                        fld, j = _name(b, j)
                        kind = b[j]
                        j += 1
                        if kind == 0:
                            _, j = leb(b, j)
                            info["imported_funcs"] += 1
                        elif kind == 1:
                            j += 1
                            _, j = _limits(b, j)
                        elif kind == 2:
                            lim, j = _limits(b, j)
                            info["memories"].append(lim)
                        elif kind == 3:
                            j += 2
                        else:
                            j += 1
                            _, j = leb(b, j)
                        imports.append((mod, fld, WASM_KINDS.get(kind, str(kind))))
                elif sid == 3:
                    info["functions"] = count
                elif sid == 4:
                    info["tables"] = count
                elif sid == 5:
                    for _ in range(count):
                        lim, j = _limits(b, j)
                        info["memories"].append(lim)
                elif sid == 6:
                    info["globals"] = count
                elif sid == 7:
                    for _ in range(count):
                        en, j = _name(b, j)
                        kind = b[j]
                        j += 1
                        _, j = leb(b, j)
                        exports.append((en, WASM_KINDS.get(kind, str(kind))))
                elif sid == 9:
                    info["elements"] = count
                elif sid == 10:
                    info["code"] = count
                elif sid == 11:
                    info["data"] = count
            elif sid == 8:
                info["start"], _ = leb(b, body)
            elif sid == 12:
                info["data"], _ = leb(b, body)
            elif sid == 0:
                cn, j = _name(b, body)
                customs.append(cn)
                if cn == "producers":
                    info["producers"] = b[j:end].decode("latin-1", "replace")
        except (IndexError, struct.error):
            pass
        secs.append((nm, ln, count))
        i = end
    return info


def wasm_lines(w):
    s = ", ".join(f"{n} {ln} B" + (f" ({c} entries)" if c is not None else "") for n, ln, c in w["sections"])
    mem = "; ".join(f"min {a} pages" + (f", max {b_}" if b_ is not None else ", no max") for a, b_ in w["memories"]) or "none"
    lines = [f"WebAssembly module version {w['version']}: {w['types']} function types, {w['imported_funcs']} imported + {w['functions']} defined functions, {len(w['imports'])} imports, "
             f"{len(w['exports'])} exports, {w['tables']} tables, {w['globals']} globals, {w['data']} data segments, memory: {mem}; start function: "
             + (f"yes (index {w['start']})" if w["start"] is not None else "none") + "."]
    lines.append("Sections (id order): " + s + ".")
    if w["imports"]:
        lines.append(f"Imports ({len(w['imports'])}): " + "; ".join(f"{m}.{f} ({k})" for m, f, k in w["imports"][:40]) + (f"; +{len(w['imports']) - 40} more" if len(w["imports"]) > 40 else "") + ".")
    else:
        lines.append("Imports: none.")
    if w["exports"]:
        lines.append(f"Exports ({len(w['exports'])}): " + "; ".join(f"{n} ({k})" for n, k in w["exports"][:40]) + (f"; +{len(w['exports']) - 40} more" if len(w["exports"]) > 40 else "") + ".")
    else:
        lines.append("Exports: none.")
    if w["customs"]:
        lines.append("Custom sections: " + ", ".join(w["customs"]) + (" (a name section means function names survive)" if "name" in w["customs"] else "") + ".")
    return lines
