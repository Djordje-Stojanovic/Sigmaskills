"""SigmaDeepLook: facts the first print must carry, and the `--ask` routes that answer them (fix round 14, ticket 83 P0.14b.H5). Standard library.

- The text encoding a file declares by a code number (SAS): the encoding name and the Windows code page, with `--ask "code page"`.
- The spatial reference system of the feature layers of a GeoPackage: layer, geometry type, srs id, authority code and name, with `--ask "which EPSG code"`.
- Small text members of an archive (a checksum list, an index, a log): quoted in the print, and `--ask "line of <member> for <word>"` shows the matching lines.
Every figure is exact over the whole file; what is not decoded is said so, never guessed.
"""
import re
import sqlite3
import time
from pathlib import Path

import dl_core as core

# ---------------------------------------------------------------- text encodings declared by number
WINDOWS_PAGES = {874: "Thai", 932: "Japanese", 936: "Simplified Chinese", 949: "Korean", 950: "Traditional Chinese", 1250: "Central European", 1251: "Cyrillic",
                 1252: "Western European", 1253: "Greek", 1254: "Turkish", 1255: "Hebrew", 1256: "Arabic", 1257: "Baltic", 1258: "Vietnamese"}
DOS_PAGES = {437: "DOS US", 720: "DOS Arabic", 737: "DOS Greek", 775: "DOS Baltic", 850: "DOS Western European", 852: "DOS Central European", 857: "DOS Turkish",
             858: "DOS Western European with euro", 860: "DOS Portuguese", 862: "DOS Hebrew", 863: "DOS Canadian French", 864: "DOS Arabic", 865: "DOS Nordic",
             866: "DOS Cyrillic", 869: "DOS Greek"}
ISO = {"latin1": "ISO 8859-1", "latin2": "ISO 8859-2", "latin3": "ISO 8859-3", "latin4": "ISO 8859-4", "cyrillic": "ISO 8859-5", "arabic": "ISO 8859-6",
       "greek": "ISO 8859-7", "hebrew": "ISO 8859-8", "latin5": "ISO 8859-9", "latin6": "ISO 8859-10", "latin8": "ISO 8859-14", "latin9": "ISO 8859-15"}
# SAS encoding byte (header offset 70) -> Python codec name; the same list pandas keeps in pandas.io.sas.sas_constants.encoding_names
SAS_CODES = {0: "default", 20: "utf-8", 28: "us-ascii", 29: "latin1", 30: "latin2", 31: "latin3", 32: "latin4", 33: "cyrillic", 34: "arabic", 35: "greek",
             36: "hebrew", 37: "latin5", 38: "latin6", 39: "cp874", 40: "latin9", 41: "cp437", 42: "cp850", 43: "cp852", 44: "cp857", 45: "cp858", 46: "cp862",
             47: "cp864", 48: "cp865", 49: "cp866", 50: "cp869", 51: "cp874", 55: "cp720", 56: "cp737", 57: "cp775", 58: "cp860", 59: "cp863", 60: "cp1250",
             61: "cp1251", 62: "cp1252", 63: "cp1253", 64: "cp1254", 65: "cp1255", 66: "cp1256", 67: "cp1257", 68: "cp1258", 118: "cp950", 123: "big5",
             125: "gb2312", 126: "cp936", 134: "euc_jp", 136: "cp932", 138: "shift_jis", 140: "euc-kr", 141: "cp949", 227: "latin8"}


def encoding_info(name):
    """A codec name -> dict(name, page, label): the Windows or DOS code page number when the name is one, with its script."""
    low = (name or "").lower()
    m = re.fullmatch(r"(?:cp|windows-?|ibm)(\d{3,4})", low)
    page = int(m.group(1)) if m else {"utf-8": 65001, "us-ascii": 20127, "big5": 950, "gb2312": 936, "shift_jis": 932}.get(low)
    script = WINDOWS_PAGES.get(page) or DOS_PAGES.get(page)
    if m and page in WINDOWS_PAGES and page >= 1250:
        shown = f"windows-{page}"
    elif low in ISO:
        shown = f"{low}"
    else:
        shown = low
    bits = []
    if page:
        bits.append(f"code page {page}" + (f", {script}" if script else ""))
    if low in ISO:
        bits.append(ISO[low])
    return {"name": shown, "page": page, "label": shown + (f" ({', '.join(bits)})" if bits else "")}


def sas_encoding(code):
    """SAS encoding byte -> dict(code, name, page, label); `label` reads 'windows-1254 (code page 1254, Turkish), SAS code 64'."""
    name = SAS_CODES.get(code)
    if name is None:
        try:   # a newer pandas may know a code this table does not
            from pandas.io.sas import sas_constants
            name = sas_constants.encoding_names.get(code)
        except Exception:
            name = None
    if name is None:
        return {"code": code, "name": None, "page": None, "label": f"unknown encoding, SAS code {code}"}
    if name == "default":
        return {"code": code, "name": None, "page": None, "label": f"not declared (the system default), SAS code {code}"}
    info = encoding_info(name)
    return {"code": code, "name": info["name"], "page": info["page"], "label": f"{info['label']}, SAS code {code}"}


CODEPAGE_Q = re.compile(r"\b(?:code\s*-?\s*page|codepage|encoding|charset|character\s+(?:set|encoding)|text\s+encoding)\b", re.I)


def try_ask_encoding(q, lj):
    """-> the answer text for a code page / encoding question about a file whose look recorded a declared encoding, else None."""
    d = (lj.get("facts") or {}).get("declared_encoding")
    if not d or not CODEPAGE_Q.search(q):
        return None
    lines = [f"--ask {q!r}"]
    if d.get("name"):
        info = encoding_info(d["name"])
        windows = bool(info["page"]) and d["name"].startswith(("windows-", "cp"))
        if windows:
            lines.append(f"Answer: Windows code page {info['page']}: {info['label']}, declared by {d['source']}.")
        else:
            lines.append(f"Answer: {info['label']}, declared by {d['source']}" + ("" if info["page"] else "; this encoding has no Windows code page number") + ".")
    else:
        lines.append(f"Answer: not declared in a form this reader knows: {d['label']} ({d['source']}).")
    return "\n".join(lines)


# ---------------------------------------------------------------- GeoPackage: the spatial reference system of the feature layers
SRS_Q = re.compile(r"\b(?:srs|epsg|crs|projection|spatial\s+reference|coordinate\s+(?:reference\s+)?system|coordinate\s+system|reference\s+system)\b", re.I)


def gpkg_layers(con):
    """-> [dict(table, geom, srs, auth, auth_id, name, extent)] for the feature layers of gpkg_geometry_columns, or None when the file has none."""
    try:
        rows = con.execute("select g.table_name, g.geometry_type_name, g.srs_id, s.organization, s.organization_coordsys_id, s.srs_name "
                           "from gpkg_geometry_columns g left join gpkg_spatial_ref_sys s on s.srs_id = g.srs_id order by g.rowid").fetchall()
    except sqlite3.Error:
        try:   # no gpkg_spatial_ref_sys table: the layers and their srs ids still stand
            rows = [r + (None, None, None) for r in con.execute("select table_name, geometry_type_name, srs_id from gpkg_geometry_columns order by rowid")]
        except sqlite3.Error:
            return None
    ext = {}
    try:
        for t, a, b, c, d in con.execute("select table_name, min_x, min_y, max_x, max_y from gpkg_contents"):
            ext[t] = (a, b, c, d)
    except sqlite3.Error:
        pass
    return [dict(table=r[0], geom=r[1] or "?", srs=r[2], auth=r[3], auth_id=r[4], name=r[5], extent=ext.get(r[0])) for r in rows] or None


def srs_text(L):
    if L["auth"] and L["auth_id"] is not None and L["auth"].upper() != "NONE":
        return f"{L['auth'].upper()}:{L['auth_id']}" + (f", {L['name']}" if L["name"] else "")
    return (L["name"] or "no authority code")


def srs_tail(L):
    return f"srs {L['srs']} ({srs_text(L)})"


def gpkg_srs_line(layers):
    """The first-print line: every feature layer with its geometry type and srs (grouped by srs past 8 layers), and the extent of each srs."""
    if not layers:
        return None
    bysrs = {}
    for L in layers:
        bysrs.setdefault(L["srs"], []).append(L)
    if len(layers) <= 8:
        body = "; ".join(f"{L['table']} {L['geom']} {srs_tail(L)}" for L in layers)
    else:
        body = "; ".join(f"{len(ls)} layers {srs_tail(ls[0])}: " + ", ".join(f"{L['table']} {L['geom']}" for L in ls[:6]) + (f", +{len(ls) - 6} more" if len(ls) > 6 else "")
                         for ls in bysrs.values())
    ext = []
    for s, ls in bysrs.items():
        es = [L["extent"] for L in ls if L["extent"] and None not in L["extent"]]
        if es:
            ext.append(f"srs {s} x {min(e[0] for e in es):,.0f}..{max(e[2] for e in es):,.0f}, y {min(e[1] for e in es):,.0f}..{max(e[3] for e in es):,.0f}")
    return f"Feature layers (gpkg_geometry_columns, {len(layers)}): {body}" + (f". Extent (gpkg_contents): {'; '.join(ext)}" if ext else "") + "."


def try_ask_srs(q, path, lj):
    """-> the answer for a spatial-reference question about a GeoPackage, or None."""
    if not SRS_Q.search(q) or (lj.get("subtype") or "") not in ("sqlite", "gpkg", "") or lj.get("type") != "data":
        return None
    try:
        uri = "file:" + str(path).replace("\\", "/").replace("%", "%25").replace("?", "%3f").replace("#", "%23") + "?mode=ro&immutable=1"
        con = sqlite3.connect(uri, uri=True)
        try:
            layers = gpkg_layers(con)
        finally:
            con.close()
    except (sqlite3.Error, OSError):
        return None
    if not layers:
        return None
    bysrs = {}
    for L in layers:
        bysrs.setdefault(L["srs"], []).append(L)
    lines = [f"--ask {q!r}"]
    if len(bysrs) == 1:
        s, ls = next(iter(bysrs.items()))
        lines.append(f"Answer: srs_id {s} ({srs_text(ls[0])}): all {len(ls)} feature layers use it (gpkg_geometry_columns joined to gpkg_spatial_ref_sys)")
    else:
        lines.append(f"Answer: {len(bysrs)} spatial reference systems are used by the {len(layers)} feature layers: " + "; ".join(f"srs_id {s} ({srs_text(ls[0])}) by {', '.join(L['table'] for L in ls)}" for s, ls in bysrs.items()))
    lines.append("Layers: " + "; ".join(f"{L['table']} {L['geom']} {srs_tail(L)}" for L in layers[:40]) + (f"; +{len(layers) - 40} more" if len(layers) > 40 else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------- small text members of an archive
SMALL_MEMBER = 4096        # a text member up to this many bytes is quoted (its first lines)
SMALL_MEMBERS = 8          # at most this many members are quoted
CHECK_NAME = re.compile(r"(?i)(?:^|[\\/._-])(?:sha\d*|md5|crc\d*|checksums?|hashes|hash|digests?|sums?)(?:$|[\\/._\d-])|sums?\.\w+$")
HEX_LINE = re.compile(r"(?i)\b[0-9a-f]{32,128}\b")
HASH_WORDS = {"sha", "sha1", "sha256", "sha512", "md5", "hash", "checksum", "digest", "crc", "sums"}
NAME_HASH = HASH_WORDS | {"sum", "checksums", "hashes", "digests", "md5sum", "sha1sum", "sha256sum", "sha512sum", "b3sum", "crc32"}   # words of a member's own name that mark a checksum list
STOP = set("the a an of in on for to is are was were what which who how many does do list lists listed say says said line lines file files member members inside cabinet "
           "archive zip tar cab folder with and or by from that this it its as at be".split())


def is_checksum_member(name, text):
    """True for a checksum list: the name says so, or most lines hold a long hex digest."""
    lines = [x for x in text.splitlines() if x.strip()]
    if not lines:
        return False
    hexy = sum(1 for x in lines if HEX_LINE.search(x))
    return hexy >= max(1, len(lines) * 0.6) and (bool(CHECK_NAME.search(name)) or len(lines) >= 3)


def quote_member(name, text, limit=600):
    """The line 'Small text member NAME: first lines' (a checksum list gets more room: its hash lines are the answer)."""
    lines = [x.strip() for x in text.strip().splitlines() if x.strip()]
    if is_checksum_member(name, text):
        take, room = 12, 1300
        tag = "Checksum list"
    else:
        take, room, tag = 8, limit, "Small text member"
    body = " | ".join(lines[:take])
    cut = len(lines) > take or len(body) > room
    body = body[:room]
    return f"{tag} {name}: {body}" + (f" ... ({len(lines)} lines in all)" if cut else ""), tag == "Checksum list"


class Members:
    """Text members of one archive read in memory for a question: zip, tar and cabinet (stored or MSZIP folders)."""
    def __init__(self, path, subtype):
        self.items = []    # (name, text)
        self.unread = []   # (name, why)
        p = Path(path)
        import zipfile
        import tarfile
        try:
            with open(p, "rb") as fh:
                magic = fh.read(4)
            if subtype == "cab" or magic == b"MSCF":
                self._cab(p)
            elif zipfile.is_zipfile(p):
                with zipfile.ZipFile(p) as z:
                    for i in z.infolist()[:5000]:
                        if i.is_dir() or i.flag_bits & 1 or i.file_size > 64 << 10:
                            continue
                        self._add(i.filename, z.open(i).read(64 << 10))
            elif tarfile.is_tarfile(p):
                with tarfile.open(p, "r:*") as t:
                    t0 = time.time()
                    for m in t:
                        if len(self.items) > 5000 or time.time() - t0 > 20:   # a long compressed stream stops at the time cap
                            break
                        if m.isfile() and m.size <= 64 << 10:
                            self._add(m.name, t.extractfile(m).read(64 << 10))
        except Exception as e:   # a damaged archive: what was read stands
            self.unread.append(("(archive)", f"{type(e).__name__}: {str(e)[:100]}"))

    def _add(self, name, data):
        text, _enc = core.decode_text(data)
        if text is not None:
            self.items.append((name, text))

    def _cab(self, p):
        import dl_cab
        cab = dl_cab.open_cab(p)
        if cab is None:
            return
        for f in cab.files:
            if f["size"] > 64 << 10:
                continue
            if not cab.readable(f):
                self.unread.append((f["name"], f"its folder is {cab.method(f['folder'])}; not decoded here (7-Zip reads it)"))
                continue
            try:
                self._add(f["name"], cab.read(f, 64 << 10) or b"")
            except Exception as e:
                self.unread.append((f["name"], f"{type(e).__name__}: {str(e)[:80]}"))


def _norm(s):
    return s.replace("\\", "/").lower()


def _name_tokens(name):
    return set(re.findall(r"[a-z]+|\d+", _norm(name).replace("/", " ").replace(".", " ").replace("_", " ")))


def _question_terms(q):
    toks = re.findall(r"[\w.\\/-]+", q.lower())
    return [t.strip(".") for t in toks if t.strip(".") and t.strip(".") not in STOP]


def archive_ask(q, path, lj):
    """A question about the text of a member of a cabinet, zip or tar: the lines of the best-matching member, or None when it is not that kind of question."""
    if lj.get("type") != "archive" or (lj.get("subtype") or "") in ("gzip", "bzip2", "xz", "zstd", "7z", "rar", "iso"):
        return None
    ql = q.lower()
    if re.search(r"\bhow\s+many\b|\bnumber\s+of\b|\bcount\b", ql):   # counts belong to the table and text routes
        return None
    if not re.search(r"\b(?:lines?|says?|said|states?|mentions?|hash|checksum|sha\s*-?\s*\d*|md5|digest|crc\d*)\b", ql):
        return None
    mem = Members(path, lj.get("subtype") or "")
    if not mem.items and not mem.unread:
        return None
    terms = _question_terms(q)
    qnorm = _norm(q)
    hashy = bool(re.search(r"\b(?:sha\s*-?\s*\d*|md5|hash|checksum|digest|crc\d*)\b", ql))
    is_named = lambda n: _norm(n).rsplit("/", 1)[-1] in qnorm   # noqa: E731
    if not hashy and not any(is_named(n) for n, _x in mem.items + mem.unread):   # without a hash word the question must name the member
        return None
    ranked = []
    for name, text in mem.items:
        base = _norm(name).rsplit("/", 1)[-1]
        named = base in qnorm or _norm(name) in qnorm
        nt = _name_tokens(name)
        hashname = bool(nt & NAME_HASH)
        name_score = (3 if hashy and hashname else 0) + (2 if named else 0) + (1 if hashy and is_checksum_member(name, text) else 0)
        # lines that hold a search term: a term that is also a word of the member's own name does not count (it asks for the member, not the line)
        own = nt | {base}
        search = [t for t in terms if t not in own and t not in HASH_WORDS and not re.fullmatch(r"sha-?\d*|crc\d*", t) and len(t) >= 2]
        hits = []
        for no, ln in enumerate(text.splitlines(), 1):
            low = _norm(ln)
            got = sum(1 for t in search if _norm(t) in low)
            if got:
                hits.append((got, no, ln.strip()))
        ranked.append((bool(hits), name_score, max((h[0] for h in hits), default=0), name, text, hits))
    ranked.sort(key=lambda r: (r[0], r[1], r[2]), reverse=True)
    lines = [f"--ask {q!r}"]
    if not ranked or (not ranked[0][0] and ranked[0][1] == 0):
        if mem.unread:
            named = [(n, why) for n, why in mem.unread if is_named(n)] or mem.unread
            lines.append("Answer: not found in the members read; not read: " + "; ".join(f"{n} ({why})" for n, why in named[:4]))
            return "\n".join(lines)
        return None
    top = ranked[0]
    if top[0]:
        best = [h for h in top[5] if h[0] == top[2]][:6]
        lines.append(f"Answer: {best[0][2]}")
        lines.append(f"Member {top[3]}, " + " | ".join(f"line {h[1]}: {h[2][:300]}" for h in best))
    else:   # the member is named, but no search word is in it: its whole text up to a short limit
        body = [x.strip() for x in top[4].splitlines() if x.strip()]
        lines.append(f"Answer: member {top[3]} has {len(body)} lines; no line holds a word of the question. First lines: " + " | ".join(body[:12]))
    for r in ranked[1:4]:
        if r[0]:
            h = [x for x in r[5] if x[0] == r[2]][0]
            lines.append(f"Also in {r[3]} (line {h[1]}): {h[2][:200]}")
    if mem.unread:
        lines.append("Not read: " + "; ".join(f"{n} ({why})" for n, why in mem.unread[:4]))
    return "\n".join(lines)
