"""Fix round 5 fixtures: synthesised files for the 12 generic failure categories, each with ground truth worked out here,
independently of the tool. Every builder returns (path, truth). Seeded random; nothing is downloaded or executed.
No file of any held-out set is used or imitated: the families come from the category list only.
"""
import gzip
import json
import math
import random
import re
import struct
import zipfile
from pathlib import Path

CITIES = ["München", "Zürich", "Köln", "Graz", "Wien", "Linz"]


# ---------------------------------------------------------------- 1. delimited text that is not UTF-8 comma CSV
def de_number(x):
    """12345.6 -> '12.345,60' (German style)."""
    s = f"{x:,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def semicolon_rows(n, seed):
    rnd = random.Random(seed)
    rows, t = [], {"rows": n, "sum_amount": 0.0, "max_amount": None, "max_line": None, "city_counts": {}, "sum_qty": 0}
    for i in range(n):
        city = rnd.choice(CITIES)
        amount = round(rnd.uniform(1, 4000), 2)
        if i == 77:
            amount = 98765.43
        qty = rnd.randint(1, 50)
        rows.append([f"K{i:04d}", city, de_number(amount), str(qty), f"{rnd.randint(1, 28):02d}.0{rnd.randint(1, 9)}.2025"])
        t["sum_amount"] += amount
        t["sum_qty"] += qty
        t["city_counts"][city] = t["city_counts"].get(city, 0) + 1
        if t["max_amount"] is None or amount > t["max_amount"]:
            t["max_amount"], t["max_line"] = amount, i + 2
    t["sum_amount"] = round(t["sum_amount"], 2)
    return ["Kunde", "Stadt", "Betrag", "Menge", "Datum"], rows, t


def csv_semicolon_cp1252(d, n=400):
    head, rows, t = semicolon_rows(n, 51)
    p = Path(d) / "umsatz.csv"
    p.write_bytes(("\r\n".join(";".join(r) for r in [head] + rows) + "\r\n").encode("cp1252"))
    t["columns"] = len(head)
    return p, t


def tsv_utf16(d, n=250):
    head, rows, t = semicolon_rows(n, 52)
    p = Path(d) / "export.txt"
    p.write_bytes(("\r\n".join("\t".join(r) for r in [head] + rows) + "\r\n").encode("utf-16"))   # with a BOM
    t["columns"] = len(head)
    return p, t


def csv_gz(d, n=300):
    head, rows, t = semicolon_rows(n, 53)
    p = Path(d) / "werte.csv.gz"
    p.write_bytes(gzip.compress(("\n".join(";".join(r) for r in [head] + rows) + "\n").encode("utf-8"), mtime=0))
    t["columns"] = len(head)
    return p, t


# ---------------------------------------------------------------- 2. nested JSON
def nested_json(d, seed=54):
    rnd = random.Random(seed)
    t = {"stores": 0, "orders": 0, "items": 0, "sum_qty": 0, "max_price": 0.0, "max_price_path": "", "cancelled": 0, "sum_total": 0.0}
    regions = []
    for ri, name in enumerate(["north", "south", "east"]):
        stores = []
        for si in range(rnd.randint(2, 4)):
            orders = []
            for oi in range(rnd.randint(1, 5)):
                items = []
                for ii in range(rnd.randint(1, 4)):
                    price = round(rnd.uniform(1, 300), 2)
                    qty = rnd.randint(1, 9)
                    items.append({"sku": f"P{rnd.randint(1, 60):03d}", "qty": qty, "price": price})
                    t["items"] += 1
                    t["sum_qty"] += qty
                    if price > t["max_price"]:
                        t["max_price"] = price
                        t["max_price_path"] = f"regions[{ri}].stores[{si}].orders[{oi}].items[{ii}]"
                status = rnd.choice(["paid", "paid", "shipped", "cancelled"])
                t["cancelled"] += status == "cancelled"
                total = round(sum(x["qty"] * x["price"] for x in items), 2)
                t["sum_total"] += total
                orders.append({"order_id": f"{name[0].upper()}{si}-{oi}", "status": status, "total": total, "items": items})
                t["orders"] += 1
            stores.append({"store_id": f"{name}-{si}", "manager": {"name": f"M{ri}{si}", "since": 2010 + si}, "orders": orders})
            t["stores"] += 1
        regions.append({"name": name, "stores": stores})
    doc = {"company": "Acme Test", "generated": "2026-01-02", "regions": regions, "meta": {"schema": 3, "tags": ["a", "b"]}}
    t["sum_total"] = round(t["sum_total"], 2)
    p = Path(d) / "sales_tree.json"
    p.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return p, t


# ---------------------------------------------------------------- 3. network captures
def mac(i):
    return bytes([0x02, 0, 0, 0, 0, i])


def ip4(s):
    return bytes(int(x) for x in s.split("."))


def ipv4(src, dst, proto, payload, ident=1):
    h = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(payload), ident, 0, 64, proto, 0, ip4(src), ip4(dst))
    return h + payload


def udp(sp, dp, data):
    return struct.pack(">HHHH", sp, dp, 8 + len(data), 0) + data


def tcp(sp, dp, flags, data=b"", seq=1):
    return struct.pack(">HHIIBBHHH", sp, dp, seq, 0, 5 << 4, flags, 65535, 0, 0) + data


def eth(src, dst, etype, payload):
    return mac(dst) + mac(src) + struct.pack(">H", etype) + payload


def qname(name):
    return b"".join(bytes([len(x)]) + x.encode() for x in name.split(".")) + b"\0"


def dns_query(ident, name):
    return struct.pack(">HHHHHH", ident, 0x0100, 1, 0, 0, 0) + qname(name) + struct.pack(">HH", 1, 1)


def dns_answer(ident, name, ip):
    return (struct.pack(">HHHHHH", ident, 0x8180, 1, 1, 0, 0) + qname(name) + struct.pack(">HH", 1, 1)
            + struct.pack(">HHHIH", 0xC00C, 1, 1, 300, 4) + ip4(ip))


def client_hello(sni):
    name = sni.encode()
    ext_sni = struct.pack(">HHHBH", 0, len(name) + 5, len(name) + 3, 0, len(name)) + name
    body = b"\x03\x03" + bytes(32) + b"\x00" + struct.pack(">H", 2) + b"\x13\x01" + b"\x01\x00" + struct.pack(">H", len(ext_sni)) + ext_sni
    hs = b"\x01" + struct.pack(">I", len(body))[1:] + body
    return b"\x16\x03\x01" + struct.pack(">H", len(hs)) + hs


def capture_packets():
    """-> [(ts_seconds_float, frame bytes)], truth."""
    t0 = 1_760_000_000.0   # 2025-10-09 08:53:20 UTC
    pk = []
    client, server, dns_srv, web2 = "10.0.0.5", "93.184.216.34", "10.0.0.1", "151.101.1.69"
    names = ["example.com", "news.example.org", "cdn.example.net", "example.com"]
    ts = t0
    for k, n in enumerate(names):
        ts += 0.5
        pk.append((ts, eth(5, 1, 0x0800, ipv4(client, dns_srv, 17, udp(50000 + k, 53, dns_query(100 + k, n))))))
        ts += 0.01
        pk.append((ts, eth(1, 5, 0x0800, ipv4(dns_srv, client, 17, udp(53, 50000 + k, dns_answer(100 + k, n, server))))))
    for flags in (0x02, 0x12, 0x10):   # handshake
        ts += 0.02
        a, b, sp, dp = (client, server, 51000, 80) if flags != 0x12 else (server, client, 80, 51000)
        pk.append((ts, eth(5 if a == client else 9, 9 if a == client else 5, 0x0800, ipv4(a, b, 6, tcp(sp, dp, flags)))))
    for path, host in (("/index.html", "example.com"), ("/api/v1/items?id=7", "api.example.com")):
        ts += 0.1
        req = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: test\r\n\r\n".encode()
        pk.append((ts, eth(5, 9, 0x0800, ipv4(client, server, 6, tcp(51000, 80, 0x18, req)))))
        ts += 0.05
        pk.append((ts, eth(9, 5, 0x0800, ipv4(server, client, 6, tcp(80, 51000, 0x18, b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")))))
    ts += 0.3
    pk.append((ts, eth(5, 7, 0x0800, ipv4(client, web2, 6, tcp(52000, 443, 0x18, client_hello("secure.example.net"))))))
    for k in range(3):
        ts += 1.0
        pk.append((ts, eth(5, 1, 0x0800, ipv4(client, "8.8.8.8", 1, struct.pack(">BBHHH", 8, 0, 0, 1, k) + b"ping"))))
    ts += 0.2
    arp = struct.pack(">HHBBH6s4s6s4s", 1, 0x0800, 6, 4, 1, mac(5), ip4(client), bytes(6), ip4(dns_srv))
    pk.append((ts, eth(5, 0xFF, 0x0806, arp)))
    ts += 0.2
    v6 = struct.pack(">IHBB16s16s", 0x60000000, 8 + 4, 17, 64, bytes(15) + b"\x01", bytes(15) + b"\x02") + udp(5353, 5353, b"abcd")
    pk.append((ts, eth(5, 6, 0x86DD, v6)))
    truth = {"packets": len(pk), "first": pk[0][0], "last": pk[-1][0], "duration": round(pk[-1][0] - pk[0][0], 3),
             "bytes": sum(len(f) for _, f in pk), "dns_names": sorted(set(names)), "dns_queries": len(names), "http_hosts": ["api.example.com", "example.com"],
             "sni": "secure.example.net", "tcp": 3 + 4 + 1, "udp": 2 * len(names) + 1, "icmp": 3, "arp": 1, "ipv6": 1,
             "top_src": client, "ports": {53, 80, 443, 5353}}
    return pk, truth


def pcap_file(d):
    pk, t = capture_packets()
    out = [struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)]
    for ts, f in pk:
        sec = int(ts)
        us = int(round((ts - sec) * 1e6))
        out.append(struct.pack("<IIII", sec, us, len(f), len(f)) + f)
    p = Path(d) / "trace.pcap"
    p.write_bytes(b"".join(out))
    return p, t


def pcapng_file(d):
    pk, t = capture_packets()

    def block(btype, body):
        body += bytes((-len(body)) % 4)
        n = 12 + len(body)
        return struct.pack("<II", btype, n) + body + struct.pack("<I", n)
    out = [block(0x0A0D0D0A, struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1)), block(1, struct.pack("<HHI", 1, 0, 65535))]
    for ts, f in pk:
        u = int(round(ts * 1e6))
        out.append(block(6, struct.pack("<IIIII", 0, u >> 32, u & 0xFFFFFFFF, len(f), len(f)) + f))
    p = Path(d) / "trace.pcapng"
    p.write_bytes(b"".join(out))
    return p, t


# ---------------------------------------------------------------- 4. INI and simple config
def ini_file(d):
    secs = {"server": {"host": "0.0.0.0", "port": "8443", "workers": "12", "timeout_s": "30"},
            "database": {"engine": "postgres", "host": "db.internal", "port": "5432", "name": "orders", "pool_size": "20", "password": "hunter2-not-real"},
            "cache": {"backend": "redis", "ttl": "600"},
            "logging": {"level": "WARNING", "file": "/var/log/app.log", "rotate": "daily", "keep": "14", "format": "%(asctime)s %(message)s"},
            "feature.flags": {"new_ui": "true", "beta_export": "false", "dark_mode": "true"},
            "paths": {"data": "/srv/data", "tmp": "/tmp/app", "uploads": "/srv/uploads"},
            "mail": {"smtp": "smtp.example.org", "from": "noreply@example.org"}}
    lines = ["; generated config", "# second comment style", ""]
    for s, kv in secs.items():
        lines.append(f"[{s}]")
        for k, v in kv.items():
            lines.append(f"{k} = {v}")
        lines.append("")
    p = Path(d) / "service.ini"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p, {"sections": list(secs), "keys": {s: len(kv) for s, kv in secs.items()}, "total": sum(len(kv) for kv in secs.values()), "values": secs}


def properties_file(d):
    kv = {f"app.module{i}.enabled": "true" if i % 3 else "false" for i in range(9)}
    kv.update({"app.name": "Ledger", "app.version": "4.2.0", "db.url": "jdbc:postgresql://db:5432/x", "db.pool.max": "40"})
    p = Path(d) / "app.properties"
    p.write_text("# props\n" + "\n".join(f"{k}={v}" for k, v in kv.items()) + "\n", encoding="utf-8")
    return p, {"keys": len(kv), "values": kv}


# ---------------------------------------------------------------- 5. rich documents
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
CT = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>{}</Types>')


def docx_rich(d):
    body, heads, paras = [], [], 0
    for ch in range(1, 7):
        title = f"Section {ch}: Topic {chr(64 + ch)}"
        heads.append(title)
        body.append(f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>{title}</w:t></w:r></w:p>')
        for sub in range(2 if ch % 2 else 1):
            body.append(f'<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Part {ch}.{sub + 1}</w:t></w:r></w:p>')
        for k in range(3):
            body.append(f"<w:p><w:r><w:t>Body text {ch}-{k} with several plain words in it.</w:t></w:r></w:p>")
            paras += 1
    body.append("<w:tbl>" + "".join("<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{r}{c}</w:t></w:r></w:p></w:tc>" for c in "abc") + "</w:tr>" for r in range(4)) + "</w:tbl>")
    body.append('<w:p><w:commentRangeStart w:id="0"/><w:r><w:t>Reviewed text.</w:t></w:r><w:commentRangeEnd w:id="0"/><w:r><w:commentReference w:id="0"/></w:r></w:p>')
    body.append('<w:p><w:ins w:id="5" w:author="Lena Ortiz" w:date="2026-03-04T10:00:00Z"><w:r><w:t>added clause</w:t></w:r></w:ins>'
                '<w:del w:id="6" w:author="Lena Ortiz" w:date="2026-03-04T10:01:00Z"><w:r><w:delText>old clause</w:delText></w:r></w:del>'
                '<w:ins w:id="7" w:author="Tom Reyes" w:date="2026-03-05T09:00:00Z"><w:r><w:t>another</w:t></w:r></w:ins></w:p>')
    doc = f'<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body>' + "".join(body) + "<w:sectPr/></w:body></w:document>"
    comments = (f'<?xml version="1.0" encoding="UTF-8"?><w:comments {W}>'
                '<w:comment w:id="0" w:author="Lena Ortiz" w:date="2026-03-04T11:00:00Z"><w:p><w:r><w:t>Check the figures.</w:t></w:r></w:p></w:comment>'
                '<w:comment w:id="1" w:author="Tom Reyes" w:date="2026-03-05T12:00:00Z"><w:p><w:r><w:t>Agreed.</w:t></w:r></w:p></w:comment></w:comments>')
    core = ('<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>Annual Plan</dc:title><dc:creator>Iris Calder</dc:creator><cp:lastModifiedBy>Tom Reyes</cp:lastModifiedBy><cp:revision>9</cp:revision>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">2026-02-01T08:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-03-05T12:30:00Z</dcterms:modified></cp:coreProperties>')
    p = Path(d) / "plan.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", CT.format('<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'))
        z.writestr("word/document.xml", doc)
        z.writestr("word/comments.xml", comments)
        z.writestr("docProps/core.xml", core)
    return p, {"h1": 6, "h2": 9, "headings": heads, "tables": 1, "comments": 2, "insertions": 2, "deletions": 1, "author": "Iris Calder",
               "last_by": "Tom Reyes", "title": "Annual Plan", "created": "2026-02-01", "revision": "9", "comment_authors": {"Lena Ortiz", "Tom Reyes"}}


ODF_NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
          'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:dc="http://purl.org/dc/elements/1.1/" '
          'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"')


def odf_zip(p, mimetype, content, meta):
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), mimetype)
        z.writestr("content.xml", content)
        z.writestr("meta.xml", meta)
        z.writestr("META-INF/manifest.xml", '<?xml version="1.0"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>')


def odt_file(d):
    parts = []
    parts.append('<text:tracked-changes><text:changed-region text:id="c1"><text:insertion><office:change-info><dc:creator>Ada Brook</dc:creator>'
                 '<dc:date>2026-04-01T10:00:00</dc:date></office:change-info></text:insertion></text:changed-region>'
                 '<text:changed-region text:id="c2"><text:deletion><office:change-info><dc:creator>Ada Brook</dc:creator><dc:date>2026-04-01T10:05:00</dc:date>'
                 '</office:change-info><text:p>removed words</text:p></text:deletion></text:changed-region></text:tracked-changes>')
    for ch in range(1, 5):
        parts.append(f'<text:h text:outline-level="1">Chapter {ch}</text:h>')
        parts.append(f'<text:h text:outline-level="2">Detail {ch}</text:h>')
        for k in range(4):
            parts.append(f"<text:p>Paragraph {ch}.{k} with ordinary prose words.</text:p>")
    parts.append('<text:p>Note here<office:annotation><dc:creator>Ada Brook</dc:creator><dc:date>2026-04-02T09:00:00</dc:date><text:p>Fix this.</text:p></office:annotation></text:p>')
    parts.append('<text:p><text:change-start text:change-id="c1"/>new words<text:change-end text:change-id="c1"/></text:p>')
    parts.append('<table:table table:name="Budget"><table:table-row><table:table-cell><text:p>x</text:p></table:table-cell></table:table-row></table:table>')
    content = f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {ODF_NS}><office:body><office:text>' + "".join(parts) + "</office:text></office:body></office:document-content>"
    meta = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-meta {ODF_NS}><office:meta><dc:title>Field Notes</dc:title><meta:initial-creator>Ada Brook</meta:initial-creator>'
            '<dc:creator>Ben Ito</dc:creator><meta:creation-date>2026-03-30T08:00:00</meta:creation-date><dc:date>2026-04-02T09:30:00</dc:date>'
            '<meta:document-statistic meta:paragraph-count="19" meta:word-count="120" meta:table-count="1"/></office:meta></office:document-meta>')
    p = Path(d) / "notes.odt"
    odf_zip(p, "application/vnd.oasis.opendocument.text", content, meta)
    return p, {"h1": 4, "h2": 4, "comments": 1, "changes": 2, "insertions": 1, "deletions": 1, "tables": 1, "title": "Field Notes", "creator": "Ada Brook", "last_by": "Ben Ito"}


def epub_file(d):
    front = [("cover.xhtml", "Cover", "cover"), ("title.xhtml", "Title Page", "titlepage"), ("copyright.xhtml", "Copyright", "copyright-page"), ("toc.xhtml", "Contents", "toc")]
    rnd = random.Random(55)
    chapters, words = [], {}
    for i in range(1, 12):
        n = rnd.randint(300, 1500)
        if i == 7:
            n = 2600
        chapters.append((f"ch{i:02d}.xhtml", f"Chapter {i}: The Part {i}", "bodymatter", n))
        words[i] = n
    back = [("ack.xhtml", "Acknowledgments", "acknowledgments"), ("about.xhtml", "About the Author", "appendix")]
    manifest, spine, files = [], [], {}
    for k, (fn, title, typ, *rest) in enumerate(front + chapters + back):
        n = rest[0] if rest else 40
        body = f"<h1>{title}</h1>" + "".join(f"<p>{' '.join(['word'] * min(100, n - j))}</p>" for j in range(0, n, 100))
        files[f"OEBPS/{fn}"] = f'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>{title}</title></head><body epub:type="{typ}">{body}</body></html>'
        manifest.append(f'<item id="i{k}" href="{fn}" media-type="application/xhtml+xml"{" properties=\"nav\"" if fn == "toc.xhtml" else ""}/>')
        spine.append(f'<itemref idref="i{k}"/>')
    opf = ('<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           '<dc:title>The Quiet Harbour</dc:title><dc:creator>Noor Vale</dc:creator><dc:language>en</dc:language><dc:publisher>Small Press</dc:publisher>'
           '<dc:date>2024-05-17</dc:date><dc:identifier id="uid">urn:isbn:0000000000000</dc:identifier></metadata>'
           f'<manifest>{"".join(manifest)}</manifest><spine>{"".join(spine)}</spine></package>')
    p = Path(d) / "harbour.epub"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                   '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf", opf)
        for k, v in files.items():
            z.writestr(k, v)
    return p, {"chapters": 11, "spine": len(front) + 11 + len(back), "longest": 7, "longest_words": 2600, "title": "The Quiet Harbour", "author": "Noor Vale",
               "date": "2024-05-17", "language": "en", "publisher": "Small Press"}


# ---------------------------------------------------------------- 6. calendar, track and geo
def ics_file(d):
    ev = [("Standup", "20260105T090000Z", "20260105T091500Z", "RRULE:FREQ=WEEKLY;COUNT=10", None, "Room 1"),
          ("Board review", "20260112T140000Z", "20260112T160000Z", None, None, "HQ"),
          ("Offsite", "VALUE=DATE:20260120", "VALUE=DATE:20260122", None, None, "Lake House"),
          ("Cancelled sync", "20260115T100000Z", "20260115T103000Z", None, "CANCELLED", "Online"),
          ("Monthly report", "20260201T080000Z", "20260201T083000Z", "RRULE:FREQ=MONTHLY;COUNT=6", None, None),
          ("Dentist", "20260303T073000Z", "20260303T080000Z", None, None, "Clinic"),
          ("Launch", "20260318T170000Z", "20260318T190000Z", None, "TENTATIVE", "Main hall")]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//r5//test//EN", "X-WR-CALNAME:Team"]
    for i, (s, a, b, rr, st, loc) in enumerate(ev):
        lines += ["BEGIN:VEVENT", f"UID:e{i}@r5", f"SUMMARY:{s}", f"DTSTART;{a}" if a.startswith("VALUE") else f"DTSTART:{a}",
                  f"DTEND;{b}" if b.startswith("VALUE") else f"DTEND:{b}", "ORGANIZER:mailto:lead@example.org"]
        if rr:
            lines.append(rr)
        if st:
            lines.append(f"STATUS:{st}")
        if loc:
            lines.append(f"LOCATION:{loc}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    p = Path(d) / "team.ics"
    p.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    return p, {"events": len(ev), "recurring": 2, "all_day": 1, "cancelled": 1, "tentative": 1, "first": "2026-01-05", "last_start": "2026-03-18",
               "occurrences": 10 + 6 + 5, "longest": "Offsite"}


def haversine(a, b):
    r = 6371008.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def gpx_file(d):
    rnd = random.Random(56)
    segs, lat, lon, ele, t = [], 47.07, 15.43, 350.0, 1_760_000_000
    for s in range(2):
        pts = []
        for i in range(150):
            lat += rnd.uniform(0.0001, 0.0004)
            lon += rnd.uniform(-0.0002, 0.0004)
            ele += rnd.uniform(-2.0, 3.0)
            t += 10
            pts.append((round(lat, 6), round(lon, 6), round(ele, 1), t))
        t += 600   # a pause between segments
        segs.append(pts)
    dist = sum(haversine(a[:2], b[:2]) for pts in segs for a, b in zip(pts, pts[1:]))
    eles = [p[2] for pts in segs for p in pts]
    gain = sum(max(0, b[2] - a[2]) for pts in segs for a, b in zip(pts, pts[1:]))
    import datetime as dt
    iso = lambda x: dt.datetime.fromtimestamp(x, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = ['<?xml version="1.0"?>', '<gpx version="1.1" creator="r5" xmlns="http://www.topografix.com/GPX/1/1">', "<metadata><name>Hill loop</name></metadata>"]
    for i, (la, lo, nm) in enumerate([(47.071, 15.431, "Start"), (47.09, 15.45, "Summit cafe"), (47.1, 15.47, "Viewpoint")]):
        out.append(f'<wpt lat="{la}" lon="{lo}"><name>{nm}</name></wpt>')
    out.append("<trk><name>Morning ride</name>")
    for pts in segs:
        out.append("<trkseg>" + "".join(f'<trkpt lat="{a}" lon="{b}"><ele>{e}</ele><time>{iso(tt)}</time></trkpt>' for a, b, e, tt in pts) + "</trkseg>")
    out.append("</trk></gpx>")
    p = Path(d) / "ride.gpx"
    p.write_text("\n".join(out), encoding="utf-8")
    first, last = segs[0][0][3], segs[-1][-1][3]
    return p, {"points": 300, "segments": 2, "tracks": 1, "waypoints": 3, "distance_km": dist / 1000, "ele_min": min(eles), "ele_max": max(eles),
               "gain": gain, "duration_s": last - first, "moving_s": 2 * 149 * 10, "start": iso(first), "end": iso(last)}


def geojson_file(d):
    rnd = random.Random(57)
    feats, pops = [], []
    for i in range(14):
        pop = rnd.randint(1000, 90000)
        pops.append((pop, f"Town {i}"))
        feats.append({"type": "Feature", "properties": {"name": f"Town {i}", "kind": rnd.choice(["city", "village"]), "population": pop},
                      "geometry": {"type": "Point", "coordinates": [round(9 + rnd.random() * 8, 4), round(46 + rnd.random() * 3, 4)]}})
    feats.append({"type": "Feature", "properties": {"name": "River A", "kind": "river"}, "geometry": {"type": "LineString", "coordinates": [[10, 47], [10.5, 47.2], [11, 47.3]]}})
    feats.append({"type": "Feature", "properties": {"name": "Park", "kind": "park"}, "geometry": {"type": "Polygon", "coordinates": [[[12, 46.5], [12.2, 46.5], [12.2, 46.7], [12, 46.7], [12, 46.5]]]}})
    xs = [f["geometry"]["coordinates"][0] for f in feats[:14]] + [10, 10.5, 11, 12, 12.2]
    ys = [f["geometry"]["coordinates"][1] for f in feats[:14]] + [47, 47.2, 47.3, 46.5, 46.7]
    p = Path(d) / "places.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "name": "places", "features": feats}), encoding="utf-8")
    top = max(pops)
    return p, {"features": 16, "points": 14, "lines": 1, "polygons": 1, "sum_pop": sum(x for x, _ in pops), "max_pop": top[0], "max_name": top[1],
               "bbox": (min(xs), min(ys), max(xs), max(ys)), "river_km": (haversine((47, 10), (47.2, 10.5)) + haversine((47.2, 10.5), (47.3, 11))) / 1000}


# ---------------------------------------------------------------- 7. open-document spreadsheet
def ods_file(d):
    rows = [("Item", "Qty", "Price", "Total")]
    rnd = random.Random(58)
    for i in range(12):
        q, pr = rnd.randint(1, 20), round(rnd.uniform(2, 80), 2)
        rows.append((f"Item {i}", q, pr, round(q * pr, 2)))

    def cell(v, formula=None):
        if isinstance(v, (int, float)):
            f = f' table:formula="{formula}"' if formula else ""
            return f'<table:table-cell office:value-type="float" office:value="{v}"{f}><text:p>{v}</text:p></table:table-cell>'
        return f'<table:table-cell office:value-type="string"><text:p>{v}</text:p></table:table-cell>'
    t1 = []
    for r, row in enumerate(rows):
        cells = [cell(v, f"of:=[.B{r + 1}]*[.C{r + 1}]" if c == 3 and r else None) for c, v in enumerate(row)]
        t1.append("<table:table-row>" + "".join(cells) + "</table:table-row>")
    t1.append('<table:table-row table:number-rows-repeated="3"><table:table-cell table:number-columns-repeated="4"/></table:table-row>')
    t2 = ["<table:table-row>" + cell("Region") + cell("Target") + "</table:table-row>"] + [f"<table:table-row>{cell(f'R{k}')}{cell(100 * k)}</table:table-row>" for k in range(1, 6)]
    content = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {ODF_NS}><office:body><office:spreadsheet>'
               f'<table:table table:name="Orders">{"".join(t1)}</table:table><table:table table:name="Targets">{"".join(t2)}</table:table>'
               '</office:spreadsheet></office:body></office:document-content>')
    meta = f'<?xml version="1.0" encoding="UTF-8"?><office:document-meta {ODF_NS}><office:meta><dc:creator>Ola Finn</dc:creator></office:meta></office:document-meta>'
    p = Path(d) / "orders.ods"
    odf_zip(p, "application/vnd.oasis.opendocument.spreadsheet", content, meta)
    tot = [r[3] for r in rows[1:]]
    return p, {"sheets": ["Orders", "Targets"], "rows_orders": 12, "sum_qty": sum(r[1] for r in rows[1:]), "sum_total": round(sum(tot), 2),
               "max_total": max(tot), "max_item": rows[1:][tot.index(max(tot))][0], "formulas": 12, "sum_target": 1500}


# ---------------------------------------------------------------- 9. text PDF with page-level facts
def pdf_text(d):
    pages = [["Quarterly Report", "Prepared by the finance team", "Summary of results for the quarter."],
             ["Sales by product", "Product   Units   Revenue", "Alpha     120     2,400.00", "Beta      75      3,150.50", "Gamma     40      980.25"],
             ["Costs", "Rent and utilities were stable.", "The audit committee met twice.", "Staff costs rose by 4 percent."],
             ["Outlook", "Total revenue: 6,530.75", "The warehouse lease ends in June 2027.", "Net margin was 12.5 percent."]]
    objs = []
    kids = []
    for i, lines in enumerate(pages):
        parts = []
        for k, x in enumerate(lines):   # every line at its own place; table cells (split on 3 spaces) in their own columns
            y = 720 - 20 * k
            for c, cell in enumerate(re.split(r"\s{3,}", x)):
                parts.append(f"BT /F1 12 Tf 1 0 0 1 {72 + 150 * c} {y} Tm ({cell}) Tj ET")
        ops = " ".join(parts)
        objs.append(("content", ops))
    # object layout: 1 catalog, 2 pages, 3 font, then (page, content) pairs
    body = []
    n_obj = 3 + 2 * len(pages)
    for i in range(len(pages)):
        kids.append(f"{4 + 2 * i} 0 R")
    body.append("<< /Type /Catalog /Pages 2 0 R >>")
    body.append(f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>")
    body.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, (_, ops) in enumerate(objs):
        body.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>")
        body.append(f"<< /Length {len(ops)} >>\nstream\n{ops}\nendstream")
    out = b"%PDF-1.4\n"
    offs = []
    for k, b in enumerate(body, 1):
        offs.append(len(out))
        out += f"{k} 0 obj\n{b}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {n_obj + 1}\n0000000000 65535 f \n".encode() + "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
    out += f"trailer\n<< /Size {n_obj + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    p = Path(d) / "report.pdf"
    p.write_bytes(out)
    return p, {"pages": 4, "lease_page": 4, "audit_page": 3, "total_revenue": "6,530.75", "beta_revenue": "3,150.50", "table_page": 2}


# ---------------------------------------------------------------- 10. spreadsheet formulas per sheet
def xlsx_formulas(d):
    S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    rnd = random.Random(59)
    sheets = {}
    truth = {"sheets": {}}
    for name, n in (("Jan", 9), ("Feb", 14)):
        rows = ['<row r="1"><c r="A1" t="inlineStr"><is><t>Name</t></is></c><c r="B1" t="inlineStr"><is><t>Hours</t></is></c><c r="C1" t="inlineStr"><is><t>Rate</t></is></c><c r="D1" t="inlineStr"><is><t>Pay</t></is></c></row>']
        pays = []
        for r in range(2, n + 2):
            h, rate = rnd.randint(5, 40), rnd.randint(15, 60)
            pays.append(h * rate)
            rows.append(f'<row r="{r}"><c r="A{r}" t="inlineStr"><is><t>P{r}</t></is></c><c r="B{r}"><v>{h}</v></c><c r="C{r}"><v>{rate}</v></c>'
                        f'<c r="D{r}"><f>B{r}*C{r}</f><v>{h * rate}</v></c></row>')
        tr = n + 2
        rows.append(f'<row r="{tr}"><c r="A{tr}" t="inlineStr"><is><t>Total</t></is></c><c r="D{tr}"><f>SUM(D2:D{n + 1})</f><v>{sum(pays)}</v></c></row>')
        sheets[name] = f'<?xml version="1.0" encoding="UTF-8"?><worksheet {S}><sheetData>{"".join(rows)}</sheetData></worksheet>'
        truth["sheets"][name] = {"formulas": n + 1, "total": sum(pays), "max_pay": max(pays), "rows": n + 1}
    wb = (f'<?xml version="1.0" encoding="UTF-8"?><workbook {S} {R}><sheets>' + "".join(f'<sheet name="{nm}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, nm in enumerate(sheets))
          + "</sheets></workbook>")
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>' for i in range(len(sheets)))
            + "</Relationships>")
    p = Path(d) / "payroll.xlsx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", CT.format('<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'))
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        for i, nm in enumerate(sheets):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", sheets[nm])
    return p, truth


# ---------------------------------------------------------------- 8. columnar metadata (needs pyarrow to write; the reader must not)
def parquet_meta(d):
    import pyarrow as pa
    import pyarrow.parquet as pq
    t = pa.table({"sensor": ["a", "b", "c", "a"], "value": [1.5, 2.0, 3.25, 4.0]})
    t = t.replace_schema_metadata({"source_system": "plant-7", "pipeline_version": "3.1.4", "owner": "ops-team"})
    p = Path(d) / "readings.parquet"
    pq.write_table(t, p)
    return p, {"keys": {"source_system": "plant-7", "pipeline_version": "3.1.4", "owner": "ops-team"}, "rows": 4, "sum_value": 10.75}


# ---------------------------------------------------------------- 7. image with text (needs PIL to draw; the reader needs an OCR tool)
def text_image(d):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGB", (900, 300), "white")
    dr = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arial.ttf", 44)
    except OSError:
        font = ImageFont.load_default()
    dr.text((30, 40), "INVOICE NUMBER 4471", fill="black", font=font)
    dr.text((30, 150), "TOTAL DUE 812.40 EUR", fill="black", font=font)
    p = Path(d) / "scan.png"
    im.save(p)
    return p, {"words": ["INVOICE", "4471", "812.40"]}
