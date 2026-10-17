"""SigmaDeepLook: network captures, pcap and pcapng (fix round 5). Stdlib only (struct): no tshark, no scapy.

Reads every packet (classic pcap in either byte order, micro- or nanosecond stamps; pcapng with any number of sections and
interfaces, per-interface time resolution, enhanced, simple and obsolete packet blocks) and decodes Ethernet (with VLAN tags),
Linux cooked (SLL, SLL2), BSD loopback and raw IP link layers, ARP, IPv4, IPv6 (with extension headers), TCP, UDP, ICMP and
ICMPv6, then DNS (queries, answers, NXDOMAIN; UDP and TCP), HTTP/1.x (request line, Host, status), TLS ClientHello SNI and DHCP.

The look prints exact counts: packets, bytes, the time range in UTC, protocols at each layer, hosts and conversations with
packets and bytes, ports, TCP flags, DNS names, HTTP hosts and requests, TLS server names; packets.csv holds one row per packet.
"""
import csv
import datetime as dt
import io
import socket
import struct
from collections import Counter, defaultdict

import dl_prof as P

PCAP_MAGIC = {b"\xd4\xc3\xb2\xa1": ("<", 1e-6), b"\xa1\xb2\xc3\xd4": (">", 1e-6), b"\x4d\x3c\xb2\xa1": ("<", 1e-9), b"\xa1\xb2\x3c\x4d": (">", 1e-9)}
PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"
LINKTYPES = {0: "BSD loopback", 1: "Ethernet", 101: "raw IP", 12: "raw IP", 14: "raw IP", 108: "OpenBSD loopback", 113: "Linux cooked (SLL)",
             276: "Linux cooked (SLL2)", 228: "raw IPv4", 229: "raw IPv6", 105: "802.11", 127: "802.11 radiotap", 9: "PPP"}
IP_PROTO = {1: "ICMP", 2: "IGMP", 6: "TCP", 17: "UDP", 41: "IPv6-in-IPv4", 47: "GRE", 50: "ESP", 51: "AH", 58: "ICMPv6", 89: "OSPF", 132: "SCTP"}
ETHERTYPES = {0x0800: "IPv4", 0x86DD: "IPv6", 0x0806: "ARP", 0x8100: "VLAN", 0x88CC: "LLDP", 0x888E: "EAPOL", 0x8863: "PPPoE-discovery", 0x8864: "PPPoE", 0x88A8: "VLAN"}
SERVICES = {20: "ftp-data", 21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 67: "dhcp", 68: "dhcp", 69: "tftp", 80: "http", 110: "pop3", 123: "ntp",
            137: "netbios-ns", 138: "netbios-dgm", 139: "netbios", 143: "imap", 161: "snmp", 389: "ldap", 443: "https", 445: "smb", 465: "smtps", 514: "syslog",
            587: "submission", 636: "ldaps", 993: "imaps", 995: "pop3s", 1883: "mqtt", 1900: "ssdp", 3306: "mysql", 3389: "rdp", 5353: "mdns", 5355: "llmnr",
            5432: "postgres", 6379: "redis", 8080: "http-alt", 8443: "https-alt", 27017: "mongodb"}
DNS_TYPES = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR", 15: "MX", 16: "TXT", 28: "AAAA", 33: "SRV", 64: "SVCB", 65: "HTTPS", 255: "ANY"}
HTTP_METHODS = (b"GET ", b"POST ", b"PUT ", b"DELETE ", b"HEAD ", b"OPTIONS ", b"PATCH ", b"CONNECT ", b"TRACE ")
MAX_PACKETS = 20_000_000
TABLE_ROWS = 200_000


# ---------------------------------------------------------------- readers
def packets(path, info):
    """Yield (timestamp seconds or None, linktype, frame bytes, original length). Fills info (format, linktypes, notes)."""
    with open(path, "rb") as f:
        head = f.read(4)
        f.seek(0)
        if head in PCAP_MAGIC:
            yield from _pcap(f, info)
        elif head == PCAPNG_MAGIC:
            yield from _pcapng(f, info)


def _pcap(f, info):
    gh = f.read(24)
    e, unit = PCAP_MAGIC[gh[:4]]
    vmaj, vmin, _tz, _sig, snap, link = struct.unpack(e + "HHiIII", gh[4:24])
    link &= 0xFFFF
    info.update(format=f"pcap {vmaj}.{vmin}", resolution="nanoseconds" if unit < 1e-6 else "microseconds", snaplen=snap)
    info["linktypes"][link] += 0
    rec = struct.Struct(e + "IIII")
    while True:
        h = f.read(16)
        if len(h) < 16:
            if h:
                info["notes"].append("the last packet header is cut off")
            return
        sec, frac, incl, orig = rec.unpack(h)
        if incl > 1 << 26:
            info["notes"].append(f"a packet length of {incl} bytes at offset {f.tell() - 16}: the file is damaged from there")
            return
        data = f.read(incl)
        if len(data) < incl:
            info["notes"].append("the last packet is cut off")
        yield sec + frac * unit, link, data, orig


def _pcapng(f, info):
    info.update(format="pcapng")
    e = "<"
    ifaces = []
    while True:
        h = f.read(8)
        if len(h) < 8:
            return
        btype_raw = h[:4]
        if btype_raw == PCAPNG_MAGIC:
            bom = f.read(4)
            e = "<" if bom == b"\x4d\x3c\x2b\x1a" else ">"
            blen = struct.unpack(e + "I", h[4:8])[0]
            f.read(max(0, blen - 12))
            ifaces = []
            info["sections"] = info.get("sections", 0) + 1
            continue
        btype, blen = struct.unpack(e + "II", h)
        if blen < 12 or blen > 1 << 27:
            info["notes"].append(f"a block of length {blen} at offset {f.tell() - 8}: the file is damaged from there")
            return
        body = f.read(blen - 8)
        if len(body) < blen - 8:
            info["notes"].append("the last block is cut off")
            return
        body = body[:-4]
        if btype == 1:   # interface description
            link, _r, snap = struct.unpack(e + "HHI", body[:8])
            res = 1e-6
            i = 8
            while i + 4 <= len(body):
                code, ln = struct.unpack(e + "HH", body[i:i + 4])
                if code == 0:
                    break
                if code == 9 and ln >= 1:
                    v = body[i + 4]
                    res = 2 ** -(v & 0x7F) if v & 0x80 else 10 ** -v
                i += 4 + ln + (-ln % 4)
            ifaces.append((link, res))
            info["linktypes"][link] += 0
            info["interfaces"] = info.get("interfaces", 0) + 1
            info["resolution"] = "nanoseconds" if res < 1e-6 else "microseconds" if res == 1e-6 else f"{res:g} s"
        elif btype == 6 and len(body) >= 20:   # enhanced packet
            iid, hi, lo, cap, orig = struct.unpack(e + "IIIII", body[:20])
            link, res = ifaces[iid] if iid < len(ifaces) else (1, 1e-6)
            yield ((hi << 32) | lo) * res, link, body[20:20 + cap], orig
        elif btype == 3 and len(body) >= 4:   # simple packet: no time stamp
            orig = struct.unpack(e + "I", body[:4])[0]
            link = ifaces[0][0] if ifaces else 1
            yield None, link, body[4:4 + orig], orig
        elif btype == 2 and len(body) >= 20:   # obsolete packet block
            iid, _drops, hi, lo, cap, orig = struct.unpack(e + "HHIIII", body[:20])
            link, res = ifaces[iid] if iid < len(ifaces) else (1, 1e-6)
            yield ((hi << 32) | lo) * res, link, body[20:20 + cap], orig
        else:
            info["other_blocks"][btype] += 1


# ---------------------------------------------------------------- decoders
def ip_str(b):
    try:
        return socket.inet_ntop(socket.AF_INET6 if len(b) == 16 else socket.AF_INET, b)
    except (OSError, ValueError):
        return b.hex()


def mac_str(b):
    return ":".join(f"{x:02x}" for x in b)


def dns_name(buf, off, depth=0):
    """-> (name, next offset). Follows compression pointers (bounded)."""
    labels = []
    jumped, end = False, off
    for _ in range(128):
        if off >= len(buf):
            break
        n = buf[off]
        if n == 0:
            off += 1
            break
        if n & 0xC0 == 0xC0:
            if off + 1 >= len(buf) or depth > 10:
                break
            ptr = ((n & 0x3F) << 8) | buf[off + 1]
            if not jumped:
                end = off + 2
            jumped = True
            off = ptr
            depth += 1
            continue
        labels.append(buf[off + 1:off + 1 + n].decode("latin-1", "replace"))
        off += 1 + n
    return ".".join(labels), (end if jumped else off)


def parse_dns(p):
    """-> dict(id, qr, rcode, questions [(name, type)], answers [(name, type, value)]) or None."""
    if len(p) < 12:
        return None
    ident, flags, qd, an, _ns, _ar = struct.unpack(">HHHHHH", p[:12])
    if qd > 50 or an > 500:
        return None
    off, qs, ans = 12, [], []
    try:
        for _ in range(qd):
            name, off = dns_name(p, off)
            qt = struct.unpack(">H", p[off:off + 2])[0]
            off += 4
            qs.append((name, DNS_TYPES.get(qt, str(qt))))
        for _ in range(an):
            name, off = dns_name(p, off)
            t, _c, _ttl, rdl = struct.unpack(">HHIH", p[off:off + 10])
            off += 10
            rd = p[off:off + rdl]
            if t in (1, 28) and len(rd) in (4, 16):
                val = ip_str(rd)
            elif t in (5, 2, 12):
                val = dns_name(p, off)[0]
            else:
                val = f"{len(rd)} bytes"
            ans.append((name, DNS_TYPES.get(t, str(t)), val))
            off += rdl
    except (struct.error, IndexError):
        pass
    return {"id": ident, "qr": flags >> 15, "rcode": flags & 0xF, "questions": qs, "answers": ans}


def tls_sni(p):
    """The server name of a TLS ClientHello at the start of a TCP payload, else None."""
    try:
        if len(p) < 44 or p[0] != 0x16 or p[5] != 1:
            return None
        i = 9 + 2 + 32
        i += 1 + p[i]
        i += 2 + struct.unpack(">H", p[i:i + 2])[0]
        i += 1 + p[i]
        end = i + 2 + struct.unpack(">H", p[i:i + 2])[0]
        i += 2
        while i + 4 <= min(end, len(p)):
            et, el = struct.unpack(">HH", p[i:i + 4])
            if et == 0:
                n = struct.unpack(">H", p[i + 7:i + 9])[0]
                return p[i + 9:i + 9 + n].decode("ascii", "replace")
            i += 4 + el
    except (struct.error, IndexError):
        return None
    return None


def decode(link, fr):
    """-> dict with l2/l3/l4 fields of one frame (best effort, never raises)."""
    d = {}
    try:
        etype, off = None, 0
        if link == 1:
            if len(fr) < 14:
                return d
            d["smac"], d["dmac"] = mac_str(fr[6:12]), mac_str(fr[0:6])
            etype, off = struct.unpack(">H", fr[12:14])[0], 14
            while etype in (0x8100, 0x88A8) and len(fr) >= off + 4:
                d["vlan"] = struct.unpack(">H", fr[off:off + 2])[0] & 0x0FFF
                etype, off = struct.unpack(">H", fr[off + 2:off + 4])[0], off + 4
        elif link in (0, 108):
            fam = struct.unpack("<I", fr[:4])[0] if fr[:2] != b"\0\0" else struct.unpack(">I", fr[:4])[0]
            etype, off = (0x0800 if fam == 2 else 0x86DD if fam in (10, 24, 28, 30) else None), 4
        elif link in (101, 12, 14, 228, 229):
            v = fr[0] >> 4 if fr else 0
            etype, off = (0x0800 if v == 4 else 0x86DD if v == 6 else None), 0
        elif link == 113:
            etype, off = struct.unpack(">H", fr[14:16])[0], 16
        elif link == 276:
            etype, off = struct.unpack(">H", fr[0:2])[0], 20
        else:
            d["l3"] = LINKTYPES.get(link, f"link {link}")
            return d
        if etype is None:
            return d
        d["l3"] = ETHERTYPES.get(etype, f"ethertype 0x{etype:04x}")
        p = fr[off:]
        if etype == 0x0806 and len(p) >= 28:
            op = struct.unpack(">H", p[6:8])[0]
            d.update(src=ip_str(p[14:18]), dst=ip_str(p[24:28]), info="ARP request" if op == 1 else "ARP reply" if op == 2 else f"ARP op {op}")
            return d
        proto, l4 = None, b""
        if etype == 0x0800 and len(p) >= 20:
            ihl = (p[0] & 0x0F) * 4
            tot = struct.unpack(">H", p[2:4])[0]
            frag = struct.unpack(">H", p[6:8])[0] & 0x1FFF
            proto = p[9]
            d.update(src=ip_str(p[12:16]), dst=ip_str(p[16:20]), ttl=p[8])
            l4 = p[ihl:tot if tot >= ihl else None]
            if frag:
                d["l4"] = IP_PROTO.get(proto, f"IP proto {proto}")
                d["info"] = "IP fragment"
                return d
        elif etype == 0x86DD and len(p) >= 40:
            proto = p[6]
            d.update(src=ip_str(p[8:24]), dst=ip_str(p[24:40]), ttl=p[7])
            i = 40
            while proto in (0, 43, 60, 44) and len(p) >= i + 8:
                nxt, ln = p[i], (p[i + 1] + 1) * 8 if proto != 44 else 8
                proto, i = nxt, i + ln
            l4 = p[i:]
        if proto is None:
            return d
        d["l4"] = IP_PROTO.get(proto, f"IP proto {proto}")
        if proto == 6 and len(l4) >= 20:
            sp, dp, _seq, _ack, offf, flags = struct.unpack(">HHIIBB", l4[:14])
            d.update(sport=sp, dport=dp, flags=flags)
            pay = l4[(offf >> 4) * 4:]
            d["payload"] = len(pay)
            if pay:
                app(d, pay, sp, dp, tcp=True)
        elif proto == 17 and len(l4) >= 8:
            sp, dp = struct.unpack(">HH", l4[:4])
            d.update(sport=sp, dport=dp)
            pay = l4[8:]
            d["payload"] = len(pay)
            app(d, pay, sp, dp, tcp=False)
        elif proto in (1, 58) and l4:
            t = l4[0]
            names = {0: "echo reply", 8: "echo request", 3: "unreachable", 11: "time exceeded"} if proto == 1 else {128: "echo request", 129: "echo reply", 135: "neighbour solicitation", 136: "neighbour advertisement", 133: "router solicitation", 134: "router advertisement"}
            d["info"] = f"{d['l4']} {names.get(t, 'type ' + str(t))}"
    except (struct.error, IndexError):
        pass
    return d


def app(d, pay, sp, dp, tcp):
    ports = (sp, dp)
    if any(x in (53, 5353, 5355) for x in ports):
        body = pay[2:] if tcp and len(pay) > 2 else pay
        r = parse_dns(body)
        if r is not None and (r["questions"] or r["answers"]):
            d["app"] = "mDNS" if 5353 in ports else "LLMNR" if 5355 in ports else "DNS"
            d["dns"] = r
            q = r["questions"][0] if r["questions"] else ("?", "?")
            d["info"] = (f"{d['app']} response {q[0]} {q[1]}" + (f" -> {', '.join(a[2] for a in r['answers'][:3])}" if r["answers"] else "") + (" NXDOMAIN" if r["rcode"] == 3 else "")) if r["qr"] else f"{d['app']} query {q[0]} {q[1]}"
            return
    if tcp and pay.startswith(HTTP_METHODS):
        head = pay[:4096].split(b"\r\n\r\n", 1)[0].decode("latin-1", "replace").split("\r\n")
        parts = head[0].split(" ")
        hdr = {k.strip().lower(): v.strip() for k, _, v in (x.partition(":") for x in head[1:]) if k}
        d["app"] = "HTTP"
        d["http"] = {"method": parts[0], "path": parts[1] if len(parts) > 1 else "", "host": hdr.get("host", ""), "ua": hdr.get("user-agent", "")}
        d["info"] = f"HTTP {parts[0]} {hdr.get('host', '')}{parts[1] if len(parts) > 1 else ''}"
        return
    if tcp and pay.startswith(b"HTTP/1."):
        line = pay[:200].split(b"\r\n", 1)[0].decode("latin-1", "replace")
        bits = line.split(" ")
        d["app"] = "HTTP"
        d["http_status"] = bits[1] if len(bits) > 1 else "?"
        d["info"] = line
        return
    if tcp and pay[:1] == b"\x16":
        sni = tls_sni(pay)
        d["app"] = "TLS"
        if sni:
            d["sni"] = sni
            d["info"] = f"TLS ClientHello {sni}"
        return
    if tcp and pay[:1] in (b"\x17", b"\x15", b"\x14") and pay[1:2] == b"\x03":
        d["app"] = "TLS"
        return
    if not tcp and any(x in (67, 68) for x in ports):
        d["app"] = "DHCP"
        return
    if not tcp and 123 in ports:
        d["app"] = "NTP"
        return
    if not tcp and 1900 in ports:
        d["app"] = "SSDP"


# ---------------------------------------------------------------- the look
def utc(t):
    if t is None:
        return "?"
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"


def look_pcap(look):
    import time
    info = {"linktypes": Counter(), "notes": [], "other_blocks": Counter()}
    t0 = time.time()
    n = cap_bytes = wire_bytes = cut = 0
    first = last = None
    l3, l4, appc = Counter(), Counter(), Counter()
    host_pk, host_by, src_pk, dst_pk = Counter(), Counter(), Counter(), Counter()
    conv = defaultdict(lambda: [0, 0, None, None])
    tcp_dport, udp_dport, flags = Counter(), Counter(), Counter()
    dns_q, dns_types, nx, dns_ans = Counter(), Counter(), Counter(), defaultdict(set)
    dns_resp = 0
    http_req, http_hosts, http_status, uas = [], Counter(), Counter(), Counter()
    sni = Counter()
    macs, vlans = set(), Counter()
    sizes_lo = sizes_hi = None
    big_at = None
    rows = []
    out_of_order = 0
    prev_t = None
    for ts, link, fr, orig in packets(look.path, info):
        n += 1
        cap_bytes += len(fr)
        wire_bytes += orig
        cut += orig > len(fr)
        if ts is not None:
            first = ts if first is None or ts < first else first
            last = ts if last is None or ts > last else last
            if prev_t is not None and ts < prev_t:
                out_of_order += 1
            prev_t = ts
        if sizes_lo is None or orig < sizes_lo:
            sizes_lo = orig
        if sizes_hi is None or orig > sizes_hi:
            sizes_hi, big_at = orig, n
        info["linktypes"][link] += 1
        d = decode(link, fr)
        l3[d.get("l3", "unknown")] += 1
        if "l4" in d:
            l4[d["l4"]] += 1
        if "app" in d:
            appc[d["app"]] += 1
        for k in ("smac", "dmac"):
            if k in d:
                macs.add(d[k])
        if "vlan" in d:
            vlans[d["vlan"]] += 1
        s, t = d.get("src"), d.get("dst")
        if s and t:
            src_pk[s] += 1
            dst_pk[t] += 1
            for h in (s, t):
                host_pk[h] += 1
                host_by[h] += orig
            a, b = (s, d.get("sport")), (t, d.get("dport"))
            key = (d.get("l4") or d.get("l3"),) + tuple(sorted([a, b], key=lambda x: (x[0], x[1] or 0)))
            c = conv[key]
            c[0] += 1
            c[1] += orig
            c[2] = c[2] if c[2] is not None else n
            c[3] = n
        if d.get("l4") == "TCP":
            f = d.get("flags", 0)
            if f & 0x02 and not f & 0x10:
                flags["SYN (connection attempts)"] += 1
                tcp_dport[d.get("dport")] += 1
            elif f & 0x02:
                flags["SYN-ACK"] += 1
            if f & 0x04:
                flags["RST"] += 1
            if f & 0x01:
                flags["FIN"] += 1
            if d.get("payload"):
                flags["segments with data"] += 1
        elif d.get("l4") == "UDP":
            udp_dport[d.get("dport")] += 1
        r = d.get("dns")
        if r:
            if r["qr"]:
                dns_resp += 1
                if r["rcode"] == 3:
                    for q in r["questions"]:
                        nx[q[0]] += 1
                for name, typ, val in r["answers"]:
                    if typ in ("A", "AAAA", "CNAME"):
                        dns_ans[name].add(val)
            else:
                for q in r["questions"]:
                    dns_q[q[0]] += 1
                    dns_types[q[1]] += 1
        if "http" in d:
            h = d["http"]
            http_hosts[h["host"] or "(no Host header)"] += 1
            if h["ua"]:
                uas[h["ua"]] += 1
            if len(http_req) < 500:
                http_req.append((n, ts, h["method"], h["host"], h["path"]))
        if "http_status" in d:
            http_status[d["http_status"]] += 1
        if "sni" in d:
            sni[d["sni"]] += 1
        if len(rows) < TABLE_ROWS:
            rows.append([n, f"{ts - first:.6f}" if ts is not None and first is not None else "", utc(ts)[:-4] if ts is not None else "", s or d.get("smac", ""), t or d.get("dmac", ""),
                         d.get("app") or d.get("l4") or d.get("l3", ""), d.get("sport", ""), d.get("dport", ""), orig, d.get("info", "")])
        if n >= MAX_PACKETS or time.time() - t0 > 240:
            look.flag("PARTIAL", "packets", f"stopped after {n:,} packets", "cap reached: counts are lower bounds")
            break
    look.subtype = "pcapng" if info.get("format") == "pcapng" else "pcap"
    dur = (last - first) if first is not None and last is not None else None
    look.headline = f"network capture ({info.get('format', '?')}), {n:,} packets" + (f", {P.fmt(round(dur, 3))} s" if dur is not None else "")
    look.dims = f"{n:,} packets"
    links = ", ".join(f"{LINKTYPES.get(k, 'link ' + str(k))} ({v:,})" for k, v in info["linktypes"].items())
    look.fact("packets", n)
    look.fact("bytes_on_wire", wire_bytes)
    look.fact("first_packet_utc", utc(first))
    look.fact("last_packet_utc", utc(last))
    look.fact("duration_s", round(dur, 6) if dur is not None else None)
    P.counts(look, [("packets", n), ("bytes captured", cap_bytes), ("bytes on the wire", wire_bytes), ("packets cut by the snap length", cut or None),
                    ("duration s", round(dur, 3) if dur is not None else None), ("distinct IP hosts", len(host_pk)), ("conversations", len(conv)),
                    ("MAC addresses", len(macs) or None), ("DNS queries", sum(dns_q.values()) or None), ("HTTP requests", sum(http_hosts.values()) or None),
                    ("TLS server names", sum(sni.values()) or None)], 97)
    look.line(f"Capture: {info.get('format', '?')} ({info.get('resolution', '?')} stamps), link {links}; first packet {utc(first)}, last {utc(last)}"
              + (f", span {P.fmt(round(dur, 3))} s, {P.fmt(round(n / dur, 2)) if dur else '?'} packets/s" if dur is not None else "")
              + f"; packet size {sizes_lo}..{sizes_hi} bytes (largest: packet {big_at}), mean {P.fmt(round(wire_bytes / max(1, n), 1))}."
              + (f" {out_of_order} packets out of time order." if out_of_order else ""), 96, "capture")
    look.line("Protocols (packets): link/network " + ", ".join(f"{k} {v:,}" for k, v in l3.most_common()) + "; transport " + (", ".join(f"{k} {v:,}" for k, v in l4.most_common()) or "none")
              + "; application " + (", ".join(f"{k} {v:,}" for k, v in appc.most_common()) or "none recognised"), 95, "protocols")
    if host_pk:
        look.line(f"Hosts ({len(host_pk)}; packets sent / received, bytes): " + "; ".join(f"{h} {src_pk[h]:,}/{dst_pk[h]:,}, {P.fmt(host_by[h])} B" for h, _ in host_pk.most_common(15))
                  + (f"; +{len(host_pk) - 15} more" if len(host_pk) > 15 else "") + f". Most packets sent: {src_pk.most_common(1)[0][0]}.", 94, "hosts")
    if conv:
        top = sorted(conv.items(), key=lambda kv: (-kv[1][0], kv[1][2]))[:12]

        def ep(x):
            return f"{x[0]}:{x[1]}" if x[1] is not None else x[0]
        look.line(f"Conversations ({len(conv)}; protocol, the two ends, packets, bytes, first..last packet number): "
                  + "; ".join(f"{k[0]} {ep(k[1])} <-> {ep(k[2])} {v[0]:,} pk {P.fmt(v[1])} B #{v[2]}..#{v[3]}" for k, v in top), 90, "conversations")
    if tcp_dport or udp_dport:
        def pl(c):
            return ", ".join(f"{p}{'/' + SERVICES[p] if p in SERVICES else ''} {v:,}" for p, v in c.most_common(15))
        look.line("Ports: TCP connection attempts (SYN) by destination port: " + (pl(tcp_dport) or "none") + "; UDP packets by destination port: " + (pl(udp_dport) or "none")
                  + ("; TCP flags: " + ", ".join(f"{k} {v:,}" for k, v in flags.items()) if flags else ""), 93, "ports")
    if dns_q or dns_resp:
        look.line(f"DNS: {sum(dns_q.values()):,} queries for {len(dns_q)} distinct names, {dns_resp:,} responses"
                  + (f", {sum(nx.values())} NXDOMAIN ({', '.join(nx)})" if nx else "") + "; query types " + ", ".join(f"{k} {v}" for k, v in dns_types.most_common())
                  + ". Names (queries): " + ", ".join(f"{k} {v}" for k, v in dns_q.most_common(30)) + (f" (+{len(dns_q) - 30} more)" if len(dns_q) > 30 else ""), 92, "dns")
        if dns_ans:
            look.line("DNS answers (name -> addresses): " + "; ".join(f"{k} -> {', '.join(sorted(v)[:4])}" for k, v in list(dns_ans.items())[:30]), 70, "dns")
    if http_hosts or http_status:
        look.line("HTTP: requests by Host " + ", ".join(f"{k} {v}" for k, v in http_hosts.most_common(20)) + ("; status codes " + ", ".join(f"{k} {v}" for k, v in http_status.most_common()) if http_status else "")
                  + ("; user agents " + ", ".join(f"{P.short(k, 50)} {v}" for k, v in uas.most_common(5)) if uas else ""), 91, "http")
        if http_req:
            look.line("HTTP requests (packet, time, method, host+path):\n" + "\n".join(f"#{k} {utc(t)[11:23]} {m} {h}{P.short(p, 90)}" for k, t, m, h, p in http_req[:40]), 80, "http")
    if sni:
        look.line("TLS server names (ClientHello SNI): " + ", ".join(f"{k} {v}" for k, v in sni.most_common(30)), 90, "tls")
    if vlans:
        look.line("VLAN tags: " + ", ".join(f"{k} {v:,}" for k, v in vlans.most_common()), 60)
    for note in info["notes"]:
        look.flag("CORRUPT", "capture", note, "the counts cover the packets before the damage")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["no", "rel_time_s", "time_utc", "src", "dst", "protocol", "sport", "dport", "length", "info"])
    w.writerows(rows)
    look.write_text("packets.csv", buf.getvalue(), f"one row per packet ({min(n, TABLE_ROWS):,} of {n:,}): time, hosts, protocol, ports, length, info", value=2,
                    inline=None if n <= 400 else False)
    look.cmd("--grep REGEX", "packets matching a host, port, name or protocol (searches packets.csv)", None)
    look.step("packet decode", "stdlib struct")
