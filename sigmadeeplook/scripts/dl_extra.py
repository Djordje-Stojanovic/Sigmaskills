"""SigmaDeepLook: certificates and keys, ML model files, disk and VM images, git bundles, EPUB.

Nothing here executes the input. Model files are never loaded (a pickle is only scanned with pickletools.genops), a private key is
flagged and never printed, a git bundle is cloned bare without a checkout (no hooks run), an image is never mounted.
"""
import base64
import hashlib
import io
import json
import mmap
import os
import pickletools
import re
import shutil
import struct
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import dl_core as core
import dl_util as U

NOW = lambda: datetime.now(timezone.utc)   # noqa: E731


# ================================================================= certificates and keys
def pem_blocks(text):
    return [(m.group(1), m.group(0)) for m in re.finditer(r"-----BEGIN ([A-Z0-9 ]+)-----.*?-----END \1-----", text, re.S)]


def _name(n, oid_names=("commonName", "organizationName")):
    out = []
    for a in n:
        if a.oid._name in oid_names:
            out.append(str(a.value))
    return " / ".join(out) or (n.rfc4514_string()[:80] if n else "")


def cert_facts(c):
    """-> dict of public facts from a cryptography x509 certificate."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, ed448, rsa
    pub = c.public_key()
    if isinstance(pub, rsa.RSAPublicKey):
        key = f"RSA {pub.key_size}"
    elif isinstance(pub, ec.EllipticCurvePublicKey):
        key = f"EC {pub.curve.name}"
    elif isinstance(pub, ed25519.Ed25519PublicKey):
        key = "Ed25519"
    elif isinstance(pub, ed448.Ed448PublicKey):
        key = "Ed448"
    else:
        key = type(pub).__name__
    try:
        nb, na = c.not_valid_before_utc, c.not_valid_after_utc
    except AttributeError:
        nb, na = c.not_valid_before.replace(tzinfo=timezone.utc), c.not_valid_after.replace(tzinfo=timezone.utc)
    sans = []
    try:
        ext = c.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        sans = [str(d.value) for d in ext]
    except Exception:
        pass
    ca = False
    try:
        ca = c.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    except Exception:
        pass
    sig = getattr(c.signature_algorithm_oid, "_name", str(c.signature_algorithm_oid))
    return {"subject": _name(c.subject), "issuer": _name(c.issuer), "self_signed": c.subject == c.issuer, "key": key, "sig": sig,
            "not_before": nb, "not_after": na, "sans": sans, "ca": ca, "sha256": c.fingerprint(hashes.SHA256()).hex()[:16],
            "subject_raw": c.subject, "issuer_raw": c.issuer}


def cert_line(f):
    now = NOW()
    state = "expired" if f["not_after"] < now else "not yet valid" if f["not_before"] > now else "valid now"
    days = (f["not_after"] - now).days
    s = f"{f['subject'] or '(no subject)'} <- issued by {f['issuer'] or '?'}{' (self-signed)' if f['self_signed'] else ''}; {f['key']}, {f['sig']}; {f['not_before']:%Y-%m-%d} to {f['not_after']:%Y-%m-%d} ({state}" + (f", {days} days left" if state == "valid now" else "") + ")"
    if f["sans"]:
        s += f"; names: {', '.join(f['sans'][:6])}" + (f" (+{len(f['sans']) - 6})" if len(f["sans"]) > 6 else "")
    return s, state


def ssh_pub(line):
    parts = line.split()
    try:
        blob = base64.b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
    except Exception:
        return None
    kt_len = struct.unpack(">I", blob[:4])[0]
    kt = blob[4:4 + kt_len].decode("ascii", "replace")
    bits = None
    if kt == "ssh-rsa":
        pos = 4 + kt_len
        e_len = struct.unpack(">I", blob[pos:pos + 4])[0]
        pos += 4 + e_len
        n_len = struct.unpack(">I", blob[pos:pos + 4])[0]
        n = blob[pos + 4:pos + 4 + n_len].lstrip(b"\0")
        bits = len(n) * 8 - (8 - n[0].bit_length()) if n else None
    elif kt == "ssh-ed25519":
        bits = 256
    fp = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    return kt, bits, "SHA256:" + fp


def look_cert(look):
    raw = look.path.read_bytes()[:4 << 20]
    st = look.subtype
    facts, lines = [], []
    if st == "sshpub":
        r = ssh_pub(raw.decode("ascii", "replace").strip().splitlines()[0])
        if r:
            look.headline = f"OpenSSH public key, {r[0]}" + (f" {r[1]} bits" if r[1] else "")
            look.line(f"{r[0]}{' ' + str(r[1]) + ' bits' if r[1] else ''}, fingerprint {r[2][:30]}... (the comment, which may hold an address, is not printed)", 95)
        return
    if st == "jks":
        look.headline = "Java keystore (password protected)"
        look.line("Java KeyStore: certificates and keys are inside a password-protected container.", 95)
        look.skip("keystore entries", "needs the password; not opened here", None, "keytool -list -keystore FILE (you enter the password)")
        look.flag("PRIVATE-KEY", "keystore", "may hold private keys", "never print or upload it")
        return
    certs = []
    text = None
    if st == "pem":
        text = raw.decode("ascii", "replace")
        blocks = pem_blocks(text)
        kinds = Counter(k for k, _ in blocks)
        look.fact("blocks", dict(kinds))
        priv = [k for k in kinds if "PRIVATE KEY" in k]
        if priv:
            enc = any("ENCRYPTED" in k for k in priv) or "Proc-Type: 4,ENCRYPTED" in text
            look.flag("PRIVATE-KEY", "file", f"{sum(kinds[k] for k in priv)} private key block(s)" + (" (encrypted)" if enc else " (NOT encrypted)"),
                      "a secret: never print, paste or upload it; it is not shown here")
        for k, b in blocks:
            if k in ("CERTIFICATE", "TRUSTED CERTIFICATE"):
                certs.append(("pem", b.encode()))
    elif st == "der":
        certs.append(("der", raw))
    elif st == "pkcs12":
        look.flag("PRIVATE-KEY", "file", "PKCS#12 bundles usually hold a private key", "a secret container; not printed")
        if core.have_module("cryptography"):
            try:
                from cryptography.hazmat.primitives.serialization import pkcs12
                key, cert, extra = pkcs12.load_key_and_certificates(raw, None)
                if cert is not None:
                    certs.append(("obj", cert))
                certs += [("obj", c) for c in (extra or [])]
                look.line("PKCS#12 opened without a password (it has none).", 80)
            except Exception:
                look.line("PKCS#12 bundle, password protected: not opened.", 90)
                look.skip("certificates inside the .p12", "needs the password; not opened here", None, "openssl pkcs12 -info -in FILE (you enter the password)")
        else:
            look.skip("certificates inside the .p12", "python package cryptography not importable" if not look.no_tools else "disabled by --no-tools", "cryptography")
    parsed = []
    if certs:
        if core.have_module("cryptography") and not look.no_tools:
            from cryptography import x509
            for kind, data in certs[:20]:
                try:
                    c = data if kind == "obj" else (x509.load_pem_x509_certificate(data) if kind == "pem" else x509.load_der_x509_certificate(data))
                    parsed.append(cert_facts(c))
                except Exception as e:
                    look.flag("CERT-PARSE", "certificate", f"{type(e).__name__}: {e}"[:100], "")
            look.tools_used.add("cryptography")
        elif look.tool("openssl"):
            parsed = openssl_certs(look, certs)
        else:
            look.skip("certificate fields (subject, issuer, validity, key)", "cryptography and openssl not found" if not look.no_tools else "disabled by --no-tools", "cryptography")
    if parsed:
        look.headline = f"certificate{'s' if len(parsed) > 1 else ''}: {parsed[0]['subject'] or parsed[0]['issuer']}" + (f" (+{len(parsed) - 1} more in the chain)" if len(parsed) > 1 else "")
        look.fact("certificates", len(parsed))
        rows = []
        for i, f in enumerate(parsed[:8]):
            s, state = cert_line(f)
            rows.append(f"{i + 1}. {s}")
            if state == "expired":
                look.flag("EXPIRED", f"certificate {i + 1}", f"expired {f['not_after']:%Y-%m-%d}", "clients refuse it")
            elif state == "not yet valid":
                look.flag("EXPIRED", f"certificate {i + 1}", f"not valid before {f['not_before']:%Y-%m-%d}", "clients refuse it for now")
            if f["self_signed"] and not f["ca"] and len(parsed) == 1:
                look.flag("SELF-SIGNED", f"certificate {i + 1}", "issuer is the subject", "browsers will not trust it unless added by hand")
            if "md5" in f["sig"].lower() or "sha1" in f["sig"].lower():
                look.flag("WEAK-SIGNATURE", f"certificate {i + 1}", f["sig"], "SHA-1 or MD5 signatures are rejected by current clients")
        look.line("\n".join(rows), 95, "certificates")
        if len(parsed) > 1:
            ok = all(a.get("issuer_raw") == b.get("subject_raw") for a, b in zip(parsed, parsed[1:]) if "issuer_raw" in a and "subject_raw" in b)
            look.line("Chain order: " + ("each certificate is issued by the next one" if ok else "NOT in leaf-to-root order, or a link is missing"), 80)
        look.dims = f"{len(parsed)} certificate(s)"
    if not parsed and not look.headline:
        look.headline = f"{st} key or certificate file"
    look.step("certificate parse", "cryptography" if core.have_module("cryptography") and not look.no_tools else "openssl")


def openssl_certs(look, certs):
    """Fallback when cryptography is missing: `openssl x509 -text` on each block. Never prints key material."""
    sx = look.tool("openssl")
    out = []
    for kind, data in certs[:8]:
        tmp = look.path_for("_cert.tmp")
        tmp.write_bytes(data if isinstance(data, bytes) else b"")
        r, txt, _ = look.run_text([sx, "x509", "-in", str(tmp), "-noout", "-subject", "-issuer", "-dates", "-text", "-inform", "PEM" if kind == "pem" else "DER"])
        tmp.unlink(missing_ok=True)
        if r is None or r.returncode != 0:
            continue
        g = lambda rx: (re.search(rx, txt) or [None, ""])[1].strip()   # noqa: E731
        nb = g(r"notBefore=(.+)")
        na = g(r"notAfter=(.+)")

        def dt(s):
            try:
                return datetime.strptime(s, "%b %d %H:%M:%S %Y GMT").replace(tzinfo=timezone.utc)
            except ValueError:
                return NOW()
        subj, iss = g(r"subject=(.+)"), g(r"issuer=(.+)")
        cn = lambda s: (re.search(r"CN\s*=\s*([^,/]+)", s) or [None, s])[1].strip()   # noqa: E731
        out.append({"subject": cn(subj), "issuer": cn(iss), "self_signed": subj == iss, "key": g(r"Public-Key: \((.+?)\)") or "?", "sig": g(r"Signature Algorithm: (\S+)"),
                    "not_before": dt(nb), "not_after": dt(na), "sans": re.findall(r"DNS:([^,\s]+)", txt)[:20], "ca": "CA:TRUE" in txt, "sha256": ""})
    return out


# ================================================================= ML model files (never loaded)
GGML_TYPES = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K", 12: "Q4_K", 13: "Q5_K", 14: "Q6_K",
              15: "Q8_K", 16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS", 19: "IQ1_S", 20: "IQ4_NL", 21: "IQ3_S", 22: "IQ2_S", 23: "IQ4_XS", 24: "I8", 25: "I16",
              26: "I32", 27: "I64", 28: "F64", 29: "IQ1_M", 30: "BF16", 34: "TQ1_0", 35: "TQ2_0"}
GGUF_FILE_TYPES = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 7: "Q8_0", 8: "Q5_0", 9: "Q5_1", 10: "Q2_K", 11: "Q3_K_S", 12: "Q3_K_M", 13: "Q3_K_L", 14: "Q4_K_S",
                   15: "Q4_K_M", 16: "Q5_K_S", 17: "Q5_K_M", 18: "Q6_K", 19: "IQ2_XXS", 20: "IQ2_XS", 21: "Q2_K_S", 22: "IQ3_XS", 23: "IQ3_XXS", 24: "IQ1_S",
                   25: "IQ4_NL", 26: "IQ3_S", 27: "IQ3_M", 28: "IQ2_S", 29: "IQ2_M", 30: "IQ4_XS", 31: "IQ1_M", 32: "BF16"}
GGUF_SCALAR = {0: ("<B", 1), 1: ("<b", 1), 2: ("<H", 2), 3: ("<h", 2), 4: ("<I", 4), 5: ("<i", 4), 6: ("<f", 4), 7: ("<?", 1), 10: ("<Q", 8), 11: ("<q", 8), 12: ("<d", 8)}
QUANT_IN_NAME = re.compile(r"(?<![A-Za-z0-9])((?:IQ|Q)\d(?:_[0-9A-Za-z]+)*|BF16|F16|F32)(?![A-Za-z0-9])", re.I)


class Reader:
    def __init__(self, f):
        self.f = f

    def u(self, fmt, n):
        b = self.f.read(n)
        if len(b) < n:
            raise EOFError
        return struct.unpack(fmt, b)[0]

    def string(self, lenfmt="<Q", n=8):
        ln = self.u(lenfmt, n)
        if ln > 1 << 28:
            raise ValueError("string too long")
        return self.f.read(ln).decode("utf-8", "replace")

    def value(self, t, keep=True):
        if t in GGUF_SCALAR:
            fmt, n = GGUF_SCALAR[t]
            return self.u(fmt, n)
        if t == 8:
            return self.string()
        if t == 9:
            et = self.u("<I", 4)
            cnt = self.u("<Q", 8)
            if et in GGUF_SCALAR:
                fmt, n = GGUF_SCALAR[et]
                self.f.seek(cnt * n, 1)
                return f"<array of {cnt}>"
            if et == 8:
                for _ in range(cnt):
                    ln = self.u("<Q", 8)
                    self.f.seek(ln, 1)
                return f"<array of {cnt} strings>"
            raise ValueError("nested array")
        raise ValueError(f"unknown gguf value type {t}")


def parse_gguf(path):
    with open(path, "rb") as f:
        r = Reader(f)
        if f.read(4) != b"GGUF":
            raise ValueError("no GGUF magic")
        ver = r.u("<I", 4)
        ntensors = r.u("<Q", 8) if ver >= 2 else r.u("<I", 4)
        nkv = r.u("<Q", 8) if ver >= 2 else r.u("<I", 4)
        kv = {}
        for _ in range(nkv):
            k = r.string()
            t = r.u("<I", 4)
            kv[k] = r.value(t)
        tensors = []
        for _ in range(min(ntensors, 200000)):
            name = r.string()
            nd = r.u("<I", 4)
            dims = [r.u("<Q", 8) for _ in range(nd)]
            tt = r.u("<I", 4)
            r.u("<Q", 8)
            tensors.append((name, dims, tt))
    return {"version": ver, "tensor_count": ntensors, "kv": kv, "tensors": tensors}


def look_model(look):
    st = look.subtype
    fn = {"gguf": model_gguf, "safetensors": model_safetensors, "onnx": model_onnx, "pickle": model_pickle, "torch-zip": model_pickle, "hdf5": model_hdf5}.get(st)
    if fn is None:
        look.line(f"Model file of kind {st}.", 90)
        return
    fn(look)
    look.flag("NOT-LOADED", "file", "never loaded or run", "weights were not read into memory; a model file is code if it is a pickle") if st in ("pickle", "torch-zip") else None


def human_params(n):
    return f"{n / 1e9:.2f}B" if n >= 1e9 else f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}K" if n >= 1e3 else str(n)


def model_gguf(look):
    try:
        g = parse_gguf(look.path)
    except (ValueError, EOFError, struct.error, OSError) as e:
        look.flag("CORRUPT", "header", f"GGUF header unreadable: {e}", "truncated or not a GGUF file")
        return
    kv = g["kv"]
    arch = kv.get("general.architecture", "?")
    params = sum(U_prod(d) for _, d, _ in g["tensors"])
    types = Counter()
    for _, d, tt in g["tensors"]:
        types[GGML_TYPES.get(tt, str(tt))] += U_prod(d)
    dom = types.most_common(1)[0][0] if types else "?"
    ft = kv.get("general.file_type")
    label = GGUF_FILE_TYPES.get(ft, None) if isinstance(ft, int) else None
    ctx = kv.get(f"{arch}.context_length")
    emb = kv.get(f"{arch}.embedding_length")
    blocks = kv.get(f"{arch}.block_count")
    heads = kv.get(f"{arch}.attention.head_count")
    tmpl = kv.get("tokenizer.chat_template")
    look.headline = f"GGUF {kv.get('general.name', look.path.stem)}: {arch}, {human_params(params)} params, {label or dom}"
    look.dims = f"{human_params(params)} params"
    look.fact("architecture", arch)
    look.fact("parameters", params)
    look.fact("quant", label or dom)
    look.line(f"Architecture {arch}; {human_params(params)} parameters in {g['tensor_count']} tensors; weights mostly {dom} (file type {label or '?'}); GGUF v{g['version']}.", 98)
    bits = [f"context length {ctx}" if ctx else "", f"embedding {emb}" if emb else "", f"{blocks} blocks" if blocks else "", f"{heads} attention heads" if heads else "",
            f"tokenizer {kv['tokenizer.ggml.model']}" if kv.get("tokenizer.ggml.model") else "",
            f"{len(str(tmpl))}-character chat template" if tmpl else "no chat template", f"license field: {kv.get('general.license', 'none')}"]
    look.line("Model shape: " + "; ".join(x for x in bits if x) + ".", 92)
    mix = ", ".join(f"{k} {100 * v / max(1, params):.0f} %" for k, v in types.most_common(4))
    look.line(f"Tensor types by parameters: {mix}.", 70)
    m = QUANT_IN_NAME.findall(look.path.stem)
    if m and label and all(x.upper() != label.upper() and x.upper() not in label.upper() for x in m):
        look.flag("QUANT-MISMATCH", "file name", f"name says {m[0]}, header says {label}", "the file name does not describe the weights; trust the header")
    look.write_text("model.json", json.dumps({"kv": {k: v for k, v in kv.items() if not isinstance(v, str) or len(v) < 400}, "tensor_types": dict(types), "params": params}, indent=1, default=str),
                    "GGUF metadata (key-value pairs) and tensor type totals", "json", value=2, inline=False)
    look.step("GGUF header and tensor table", "stdlib")


def U_prod(dims):
    p = 1
    for d in dims:
        p *= d
    return p


def model_safetensors(look):
    with open(look.path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        hdr = json.loads(f.read(n).decode("utf-8", "replace"))
    meta = hdr.pop("__metadata__", {})
    dts, params, last = Counter(), 0, 0
    names = list(hdr)
    for k, v in hdr.items():
        sz = U_prod(v.get("shape", []))
        params += sz
        dts[v.get("dtype", "?")] += sz
        last = max(last, v.get("data_offsets", [0, 0])[1])
    layers = 0
    for k in names:
        m = re.search(r"(?:layers|blocks|h)\.(\d+)\.", k)
        if m:
            layers = max(layers, int(m.group(1)) + 1)
    expected = 8 + n + last
    look.headline = f"safetensors: {len(names)} tensors, {human_params(params)} params, {dts.most_common(1)[0][0] if dts else '?'}"
    look.dims = f"{human_params(params)} params"
    look.fact("parameters", params)
    look.line(f"{len(names)} tensors, {human_params(params)} parameters; dtypes by parameters: " + ", ".join(f"{k} {100 * v / max(1, params):.0f} %" for k, v in dts.most_common(4)) + (f"; about {layers} repeated layers" if layers else "") + ".", 98)
    if meta:
        look.line("Metadata: " + "; ".join(f"{k}={str(v)[:60]}" for k, v in list(meta.items())[:6]), 70)
    if expected > look.size:
        look.flag("TRUNCATED", "file", f"the header needs {core.human(expected)}, the file has {core.human(look.size)}", "the download was cut short")
    prefixes = Counter(k.split(".")[0] for k in names)
    look.line("Top tensor groups: " + ", ".join(f"{k} ({v})" for k, v in prefixes.most_common(6)), 60)
    look.write_text("model.json", json.dumps({"metadata": meta, "tensors": {k: hdr[k] for k in names[:2000]}}, indent=1), "tensor names, dtypes and shapes (first 2000)", "json", value=2, inline=False)
    look.step("safetensors header", "stdlib")


# --- ONNX: a minimal protobuf reader (field walk over an mmap; initializer bytes are never copied)
def varint(b, i):
    r = s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        if not x & 0x80:
            return r, i
        s += 7


def pb(b, start, end):
    """Yield (field, wiretype, value|(a, z)) over b[start:end]. Length-delimited fields give (a, z) offsets, not bytes."""
    i = start
    while i < end:
        key, i = varint(b, i)
        f, w = key >> 3, key & 7
        if w == 0:
            v, i = varint(b, i)
            yield f, 0, v
        elif w == 2:
            ln, i = varint(b, i)
            yield f, 2, (i, i + ln)
            i += ln
        elif w == 1:
            yield f, 1, (i, i + 8)
            i += 8
        elif w == 5:
            yield f, 5, (i, i + 4)
            i += 4
        else:
            raise ValueError("bad wire type")


ONNX_DTYPES = {1: "float32", 2: "uint8", 3: "int8", 4: "uint16", 5: "int16", 6: "int32", 7: "int64", 8: "string", 9: "bool", 10: "float16", 11: "float64", 12: "uint32", 13: "uint64", 16: "bfloat16"}


def parse_onnx(path):
    with open(path, "rb") as f:
        m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            info = {"opsets": {}, "ops": Counter(), "inputs": [], "outputs": [], "params": 0, "dtypes": Counter(), "external": False, "producer": "", "nodes": 0, "initializers": 0, "ir": None}
            for f1, w, v in pb(m, 0, len(m)):
                if f1 == 1 and w == 0:
                    info["ir"] = v
                elif f1 in (2, 3) and w == 2:
                    info["producer"] += (" " if info["producer"] else "") + bytes(m[v[0]:v[1]]).decode("utf-8", "replace")
                elif f1 == 8 and w == 2:
                    dom, ver = "", 0
                    for g, gw, gv in pb(m, *v):
                        if g == 1:
                            dom = bytes(m[gv[0]:gv[1]]).decode("utf-8", "replace") or "ai.onnx"
                        elif g == 2:
                            ver = gv
                    info["opsets"][dom or "ai.onnx"] = ver
                elif f1 == 7 and w == 2:
                    for g, gw, gv in pb(m, *v):
                        if g == 1 and gw == 2:
                            info["nodes"] += 1
                            for h, hw, hv in pb(m, *gv):
                                if h == 4 and hw == 2:
                                    info["ops"][bytes(m[hv[0]:hv[1]]).decode("utf-8", "replace")] += 1
                        elif g == 5 and gw == 2:
                            info["initializers"] += 1
                            dims, dt = [], 0
                            for h, hw, hv in pb(m, *gv):
                                if h == 1:
                                    if hw == 0:
                                        dims.append(hv)
                                    else:
                                        i = hv[0]
                                        while i < hv[1]:
                                            d, i = varint(m, i)
                                            dims.append(d)
                                elif h == 2 and hw == 0:
                                    dt = hv
                                elif h == 14 and hw == 0 and hv == 1:
                                    info["external"] = True
                            n = U_prod(dims) if dims else 1
                            info["params"] += n
                            info["dtypes"][ONNX_DTYPES.get(dt, str(dt))] += n
                        elif g in (11, 12) and gw == 2:
                            name, shape, et = "", [], 0
                            for h, hw, hv in pb(m, *gv):
                                if h == 1:
                                    name = bytes(m[hv[0]:hv[1]]).decode("utf-8", "replace")
                                elif h == 2:
                                    for t1, tw, tv in pb(m, *hv):
                                        if t1 == 1:
                                            for t2, t2w, t2v in pb(m, *tv):
                                                if t2 == 1 and t2w == 0:
                                                    et = t2v
                                                elif t2 == 2 and t2w == 2:
                                                    for d1, d1w, d1v in pb(m, *t2v):
                                                        if d1 == 1 and d1w == 2:
                                                            dd = "?"
                                                            for d2, d2w, d2v in pb(m, *d1v):
                                                                dd = d2v if d2 == 1 and d2w == 0 else bytes(m[d2v[0]:d2v[1]]).decode("utf-8", "replace") if d2 == 2 else dd
                                                            shape.append(dd)
                            (info["inputs"] if g == 11 else info["outputs"]).append((name, ONNX_DTYPES.get(et, str(et)), shape))
            return info
        finally:
            m.close()


def model_onnx(look):
    try:
        i = parse_onnx(look.path)
    except (ValueError, IndexError, OSError) as e:
        look.flag("CORRUPT", "protobuf", f"ONNX unreadable: {e}", "not a valid ONNX file or truncated")
        return
    ins = [x for x in i["inputs"] if x[0] not in ()][:6]
    look.headline = f"ONNX model, {i['nodes']} nodes, {human_params(i['params'])} weights, {i['producer'] or 'unknown producer'}"
    look.dims = f"{human_params(i['params'])} weights"
    look.fact("parameters", i["params"])
    look.line(f"{i['nodes']} nodes, {i['initializers']} weight tensors, {human_params(i['params'])} parameters ({', '.join(f'{k} {100 * v / max(1, i['params']):.0f} %' for k, v in i['dtypes'].most_common(3))}); opset {', '.join(f'{k} {v}' for k, v in i['opsets'].items())}; IR {i['ir']}.", 98)
    look.line("Inputs: " + "; ".join(f"{n} {d} {s}" for n, d, s in ins) + ". Outputs: " + "; ".join(f"{n} {d} {s}" for n, d, s in i["outputs"][:6]) + ".", 92)
    look.line("Operators: " + ", ".join(f"{k} x{v}" for k, v in i["ops"].most_common(10)), 70)
    if i["external"]:
        look.flag("EXTERNAL-WEIGHTS", "initializers", "some weights live in a separate file", "the .onnx alone is incomplete; keep the data file next to it")
    look.step("ONNX graph walk (protobuf)", "stdlib")


def model_hdf5(look):
    look.headline = f"HDF5 weights file, {core.human(look.size)}"
    look.line(f"HDF5 container ({core.human(look.size)}), usually Keras weights.", 95)
    h5 = look.mod("h5py")
    if not h5:
        look.skip("layers, shapes and attributes of the HDF5 file", "python package h5py not importable" if not look.no_tools else "disabled by --no-tools", "h5py")
        return
    try:
        rows, params = [], 0
        with h5.File(str(look.path), "r") as f:
            def visit(name, obj):
                nonlocal params
                if isinstance(obj, h5.Dataset):
                    n = 1
                    for d in obj.shape:
                        n *= d
                    params += n
                    if len(rows) < 400:
                        rows.append(f"{name}: {obj.shape} {obj.dtype}")
            f.visititems(visit)
            attrs = {k: str(v)[:80] for k, v in list(f.attrs.items())[:8]}
        look.line(f"{len(rows)} arrays, {human_params(params)} values. Attributes: {attrs}.", 92)
        look.write_text("tensors.txt", chr(10).join(rows), "dataset names, shapes and dtypes (first 400)", value=3)
        look.step("HDF5 tree", "h5py")
    except Exception as e:
        look.fail("HDF5 tree", "h5py", e)


DANGEROUS_MODULES = {"os", "posix", "nt", "subprocess", "sys", "socket", "shutil", "runpy", "importlib", "webbrowser", "ctypes", "pty", "commands", "asyncio",
                     "multiprocessing", "requests", "urllib", "urllib2", "http", "ftplib", "smtplib", "marshal", "code", "codeop", "timeit", "platform", "tempfile",
                     "pickle", "dill", "cloudpickle", "shelve", "pathlib", "io", "builtins_exec"}
DANGEROUS_BUILTINS = {"eval", "exec", "compile", "open", "__import__", "getattr", "setattr", "input", "breakpoint", "globals", "locals", "vars", "delattr", "execfile"}
SAFE_PREFIXES = ("torch", "numpy", "collections", "_codecs", "copyreg", "__builtin__", "builtins", "functools", "transformers", "pytorch_lightning", "omegaconf", "argparse", "typing")


def scan_pickle(data):
    """pickletools.genops over the bytes: never unpickles. -> (globals list of 'module.name', strings that look like tensor names)."""
    globs, names = [], []
    recent = []
    memo = {}
    try:
        for op, arg, pos in pickletools.genops(io.BytesIO(data)):
            n = op.name
            if n in ("GLOBAL", "INST") and isinstance(arg, str):
                mod, _, name = arg.partition(" ")
                globs.append(f"{mod}.{name}")
            elif n in ("SHORT_BINUNICODE", "BINUNICODE", "UNICODE", "BINUNICODE8", "SHORT_BINSTRING", "BINSTRING", "STRING"):
                s = arg if isinstance(arg, str) else arg.decode("latin-1", "replace")
                recent.append(s)
                recent = recent[-4:]
                if re.search(r"\.(weight|bias|running_mean|running_var)$|^model\.|state_dict", s) and len(names) < 5000:
                    names.append(s)
            elif n == "MEMOIZE":
                memo[len(memo)] = recent[-1] if recent else ""
            elif n in ("BINPUT", "LONG_BINPUT", "PUT"):
                memo[arg] = recent[-1] if recent else ""
            elif n in ("BINGET", "LONG_BINGET", "GET"):
                recent.append(memo.get(arg, ""))
                recent = recent[-4:]
            elif n == "STACK_GLOBAL" and len(recent) >= 2:
                globs.append(f"{recent[-2]}.{recent[-1]}")
    except Exception:
        pass
    return globs, names


def classify_globals(globs):
    bad, unknown = [], []
    for g in dict.fromkeys(globs):
        mod, _, name = g.rpartition(".")
        top = mod.split(".")[0]
        if top in ("builtins", "__builtin__"):
            if name in DANGEROUS_BUILTINS:
                bad.append(g)
            continue
        if top in DANGEROUS_MODULES:
            bad.append(g)
        elif not g.startswith(SAFE_PREFIXES):
            unknown.append(g)
    return bad, unknown


def model_pickle(look):
    data = b""
    members = 0
    storage = 0
    if look.subtype == "torch-zip" or zipfile.is_zipfile(look.path):
        with zipfile.ZipFile(look.path) as z:
            infos = z.infolist()
            pk = next((i for i in infos if i.filename.endswith("data.pkl")), None)
            members = len(infos)
            storage = sum(i.file_size for i in infos if "/data/" in i.filename)
            if pk and pk.file_size < 400 << 20:
                data = z.read(pk)
    else:
        data = look.path.read_bytes()[:200 << 20]
    globs, names = scan_pickle(data)
    bad, unknown = classify_globals(globs)
    look.headline = f"{'PyTorch checkpoint' if look.subtype == 'torch-zip' else 'pickle file'}: {len(set(globs))} imported callables, {'CODE EXECUTION ON LOAD' if bad else 'no dangerous imports found'}"
    look.fact("pickle_globals", len(set(globs)))
    look.line(f"Scanned with pickletools (never loaded). Imports: {len(set(globs))} distinct callables" + (f"; tensor storage {core.human(storage)} in {members} zip members" if storage else "") + f"; about {len(names)} weight-like names.", 98)
    if bad:
        look.flag("PICKLE-EXEC", "pickle imports", f"{', '.join(bad[:6])}" + (f" (+{len(bad) - 6})" if len(bad) > 6 else ""),
                  "loading this file would run code (os/subprocess/eval...): do not torch.load or pickle.load it; use safetensors")
    if unknown:
        look.flag("PICKLE-UNKNOWN-IMPORT", "pickle imports", ", ".join(unknown[:8]), "classes outside torch/numpy/collections: loading imports that code")
    if names:
        look.line("Weight-like names (first 12): " + ", ".join(names[:12]), 60)
    look.write_text("imports.txt", "\n".join(dict.fromkeys(globs)) or "(none)", "every global the pickle imports (module.name), dangerous ones first", value=6)
    look.step("pickle opcode scan", "pickletools")


# ================================================================= disk and VM images
GUID_MD = "8B7CA206-4790-4B9A-B8FE-575F050F886E"
GUID_SIZE = "2FA54224-CD1B-4876-B211-5DBED83BF4B8"
GUID_BLOCK = "CAA16737-FA36-4D43-B3B6-33F0AA44E76B"
PART_TYPES = {0x01: "FAT12", 0x04: "FAT16", 0x06: "FAT16", 0x07: "NTFS/exFAT", 0x0B: "FAT32", 0x0C: "FAT32 LBA", 0x82: "Linux swap", 0x83: "Linux", 0xEE: "GPT protective", 0xEF: "EFI system", 0xFD: "Linux RAID"}
GPT_TYPES = {"C12A7328-F81F-11D2-BA4B-00A0C93EC93B": "EFI system", "EBD0A0A2-B9E5-4433-87C0-68B6B72699C7": "Microsoft basic data", "0FC63DAF-8483-4772-8E79-3D69D8477DE4": "Linux filesystem",
             "E3C9E316-0B5C-4DB8-817D-F92DF00215AE": "Microsoft reserved", "DE94BBA4-06D1-4D40-A16A-BFD50179D6AC": "Windows recovery", "21686148-6449-6E6F-744E-656564454649": "BIOS boot"}


def partitions(f, base=0):
    """MBR and GPT partition tables of a raw disk (stdlib). -> list of (type, start_lba, sectors, name)."""
    import uuid
    f.seek(base)
    s0 = f.read(512)
    if len(s0) < 512 or s0[510:512] != b"\x55\xaa":
        return []
    out = []
    for i in range(4):
        e = s0[446 + 16 * i:462 + 16 * i]
        t, lba, n = e[4], struct.unpack("<I", e[8:12])[0], struct.unpack("<I", e[12:16])[0]
        if t and n:
            out.append((PART_TYPES.get(t, f"type 0x{t:02x}"), lba, n, ""))
    if any(p[0] == "GPT protective" for p in out):
        f.seek(base + 512)
        h = f.read(92)
        if h[:8] == b"EFI PART":
            lba, n, sz = struct.unpack("<Q", h[72:80])[0], struct.unpack("<I", h[80:84])[0], struct.unpack("<I", h[84:88])[0]
            f.seek(base + lba * 512)
            out = []
            for _ in range(min(n, 128)):
                e = f.read(sz)
                if len(e) < 128 or e[:16] == b"\0" * 16:
                    continue
                guid = str(uuid.UUID(bytes_le=e[:16])).upper()
                first, last = struct.unpack("<QQ", e[32:48])
                name = e[56:128].decode("utf-16-le", "replace").rstrip("\0")
                out.append((GPT_TYPES.get(guid, guid[:8]), first, last - first + 1, name))
    return out


def look_diskimage(look):
    st = look.subtype
    size = look.size
    virt = None
    notes = []
    parts = []
    try:
        with open(look.path, "rb") as f:
            h = f.read(4096)
            if st == "qcow2":
                ver, bf_off, bf_size, cbits, virt, crypt = struct.unpack(">IQIIQI", h[4:36])
                notes.append(f"qcow2 v{ver}, cluster {1 << cbits} bytes")
                if bf_off:
                    f.seek(bf_off)
                    back = os.path.basename(f.read(min(bf_size, 1024)).decode("utf-8", "replace"))
                    look.flag("BACKING-FILE", "header", f"depends on {back}", "a differencing image: it is incomplete without its parent file")
                if crypt:
                    look.flag("ENCRYPTED", "header", "qcow2 encryption method %d" % crypt, "contents cannot be read without the key")
            elif st == "vmdk":
                cap = struct.unpack("<Q", h[12:20])[0]
                virt = cap * 512
                do, ds = struct.unpack("<QQ", h[28:44])
                f.seek(do * 512)
                desc = f.read(min(ds * 512, 4096)).decode("utf-8", "replace") if do else ""
                m = re.search(r'parentFileNameHint="([^"]+)"', desc)
                notes.append("sparse VMDK")
                if m:
                    look.flag("BACKING-FILE", "descriptor", f"depends on {os.path.basename(m.group(1))}", "a snapshot child: incomplete without its parent")
            elif st == "vhd":
                f.seek(max(0, size - 512))
                ft = f.read(512)
                if ft[:8] != b"conectix":
                    ft = h[:512]
                virt = struct.unpack(">Q", ft[48:56])[0]
                typ = struct.unpack(">I", ft[60:64])[0]
                notes.append({2: "fixed", 3: "dynamic", 4: "differencing"}.get(typ, "VHD"))
                if typ == 4:
                    look.flag("BACKING-FILE", "footer", "differencing disk", "incomplete without its parent file")
                if typ == 2:
                    parts = partitions(f)
            elif st == "vhdx":
                virt = vhdx_size(f)
                notes.append("VHDX")
            elif st in ("img", "raw"):
                parts = partitions(f)
                virt = size
            elif st == "dmg":
                f.seek(max(0, size - 512))
                tr = f.read(512)
                notes.append("Apple UDIF" if tr[:4] == b"koly" else "disk image")
    except (OSError, struct.error, ValueError) as e:
        look.flag("CORRUPT", "header", f"{type(e).__name__}: {e}"[:100], "header unreadable")
    look.headline = f"{st} disk image, virtual size {core.human(virt) if virt else 'unknown'}, file {core.human(size)}"
    look.dims = f"{core.human(virt)} virtual" if virt else ""
    look.fact("virtual_size", virt)
    look.line(f"{st} disk image ({', '.join(notes) or 'header read'}); virtual size {core.human(virt) if virt else 'not read'}, stored as {core.human(size)}.", 98)
    if parts:
        look.line("Partitions: " + "; ".join(f"{t} {core.human(n * 512)} from sector {lba}" + (f" '{name}'" if name else "") for t, lba, n, name in parts[:8]), 92)
    look.flag("NOT-MOUNTED", "image", "listed only, never mounted", "contents were not opened")
    look.skip("files inside the image", "listing needs 7-Zip; the image is never mounted" if not look.tool("7z") else "listing the image is not run at this tier", "7z")


def vhdx_size(f):
    import uuid
    f.seek(0x30000)
    rt = f.read(65536)
    if rt[:4] != b"regi":
        return None
    cnt = struct.unpack("<I", rt[8:12])[0]
    md_off = None
    for i in range(min(cnt, 64)):
        e = rt[16 + 32 * i:48 + 32 * i]
        if str(uuid.UUID(bytes_le=e[:16])).upper() == GUID_MD:
            md_off = struct.unpack("<Q", e[16:24])[0]
    if md_off is None:
        return None
    f.seek(md_off)
    mt = f.read(65536)
    n = struct.unpack("<H", mt[10:12])[0]
    for i in range(min(n, 64)):
        e = mt[32 + 32 * i:64 + 32 * i]
        if str(uuid.UUID(bytes_le=e[:16])).upper() == GUID_SIZE:
            off = struct.unpack("<I", e[16:20])[0]
            f.seek(md_off + off)
            return struct.unpack("<Q", f.read(8))[0]
    return None


# ================================================================= git bundle
def git_env(look):
    e = look.env()
    e.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TEMPLATE_DIR="", GIT_ALLOW_PROTOCOL="file")
    return e


def look_gitbundle(look):
    head = look.path.read_bytes()[:65536].decode("utf-8", "replace")
    lines = head.split("\n")
    prereq, refs = [], []
    for ln in lines[1:]:
        if not ln or ln.startswith("PACK"):
            break
        if ln.startswith("-"):
            prereq.append(ln[1:41])
        elif re.match(r"[0-9a-f]{40,64} ", ln):
            refs.append(ln.split(" ", 1)[1].strip())
    look.fact("refs", refs)
    look.fact("prerequisites", len(prereq))
    look.headline = f"git bundle with {len(refs)} ref(s)" + (f" and {len(prereq)} missing prerequisite commit(s): INCOMPLETE" if prereq else "")
    look.line(f"Git bundle ({lines[0].strip('# ')}): refs {', '.join(refs[:8])}{' ...' if len(refs) > 8 else ''}; prerequisites {len(prereq)}.", 98)
    if prereq:
        look.flag("INCOMPLETE-BUNDLE", "header", f"{len(prereq)} prerequisite commit(s) must already exist in the target repository", "created with --since or a range: it cannot be cloned alone")
    git = look.tool("git")
    if not git:
        look.skip("commit count, authors, date range and top paths", "git not found" if not look.no_tools else "disabled by --no-tools", "git")
        return
    if prereq:
        look.skip("commit statistics", "an incomplete bundle cannot be cloned without its parent repository", None, "")
        return
    dest = look.out / "_bare"
    shutil.rmtree(dest, ignore_errors=True)
    env = git_env(look)
    r = look.run([git, "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false", "clone", "--bare", "--no-checkout", "--quiet", "--template=", str(look.path), str(dest)], timeout=300)
    if r is None or r.returncode != 0:
        look.flag("BUNDLE-UNREADABLE", "git", (r.stderr.decode("utf-8", "replace")[-150:] if r is not None else "failed"), "git could not clone the bundle")
        return

    def g(*a):
        import subprocess
        p = subprocess.run([git, "-c", "core.hooksPath=" + os.devnull, "-C", str(dest), *a], capture_output=True, timeout=120, env=env, stdin=subprocess.DEVNULL)
        look.exec_log.append(git)
        return p.stdout.decode("utf-8", "replace")
    count = g("rev-list", "--count", "--all").strip()
    dates = g("log", "--all", "--format=%at").split()
    authors = Counter(x for x in g("log", "--all", "--format=%an").split("\n") if x)
    paths = Counter(x for x in g("log", "--all", "--name-only", "--format=", "-n", "20000").split("\n") if x)
    shutil.rmtree(dest, ignore_errors=True)
    if dates:
        d0, d1 = datetime.fromtimestamp(min(int(x) for x in dates), timezone.utc), datetime.fromtimestamp(max(int(x) for x in dates), timezone.utc)
        look.line(f"{count} commits by {len(authors)} author name(s) (top: {', '.join(f'{a} {n}' for a, n in authors.most_common(4))}); {d0:%Y-%m-%d} to {d1:%Y-%m-%d}.", 95)
    look.line("Most changed paths: " + ", ".join(f"{p} ({n})" for p, n in paths.most_common(8)), 80)
    look.fact("commits", int(count or 0))
    look.step("bare clone (no checkout, no hooks) and git log", "git")


# ================================================================= EPUB
def epub_extras(look):
    try:
        z = zipfile.ZipFile(look.path)
    except zipfile.BadZipFile:
        return
    names = z.namelist()
    opf_name = None
    try:
        cont = z.read("META-INF/container.xml").decode("utf-8", "replace")
        m = re.search(r'full-path="([^"]+)"', cont)
        opf_name = m.group(1) if m else None
    except KeyError:
        pass
    if not opf_name or opf_name not in names:
        look.flag("CORRUPT", "container.xml", "no package document", "not a valid EPUB")
        return
    opf = z.read(opf_name).decode("utf-8", "replace")
    base = os.path.dirname(opf_name)
    first = lambda tag: (re.search(r"<dc:%s[^>]*>(.*?)</dc:%s>" % (tag, tag), opf, re.S) or [None, ""])[1].strip()   # noqa: E731
    title, author, lang = first("title"), first("creator"), first("language")
    manifest = {m.group(1): m.group(2) for m in re.finditer(r'<item\b[^>]*?\bid="([^"]+)"[^>]*?\bhref="([^"]+)"', opf)}
    manifest.update({m.group(2): m.group(1) for m in re.finditer(r'<item\b[^>]*?\bhref="([^"]+)"[^>]*?\bid="([^"]+)"', opf) if m.group(2) not in manifest})
    spine = re.findall(r'<itemref\b[^>]*?\bidref="([^"]+)"', opf)
    chapters = []
    for idref in spine:
        href = manifest.get(idref)
        if not href:
            continue
        p = (base + "/" + href).lstrip("/") if base else href
        p = re.sub(r"[^/]+/\.\./", "", p)
        if p not in names:
            continue
        if z.getinfo(p).file_size > 8 << 20:
            look.flag("TRUNCATED", p, "chapter larger than 8 MB not read", "")
            continue
        html = z.read(p).decode("utf-8", "replace")
        t = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
        h1 = re.search(r"<h[12][^>]*>(.*?)</h[12]>", html, re.S)
        txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = re.sub(r"&nbsp;|&#160;", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        label = re.sub(r"<[^>]+>", "", (h1 or t or [None, p])[1]).strip() or p
        chapters.append((label[:70], len(txt.split()), txt))
    words = sum(c[1] for c in chapters)
    look.fact("chapters", len(chapters))
    look.fact("words", words)
    look.headline = f"EPUB \"{title[:60]}\" by {author[:40] or 'unknown'}, {len(chapters)} chapters, {U.compact(words)} words"
    look.dims = f"{len(chapters)} chapters"
    look.line(f"Title {title[:80]!r}; author {author[:60]!r}; language {lang or '?'}; {len(chapters)} spine documents, {words} words (about {core.direct_tokens(words * 5)} tokens to read whole).", 98)
    if "META-INF/encryption.xml" in names:
        enc = z.read("META-INF/encryption.xml").decode("utf-8", "replace")
        if re.search(r"EncryptionMethod[^>]*Algorithm=\"(?!http://www.idpf.org/2008/embedding|http://ns.adobe.com/pdf/enc)", enc):
            look.flag("DRM", "META-INF/encryption.xml", "content is encrypted", "the text cannot be read without the license")
    if "rendition:layout\">pre-paginated" in opf or 'rendition:layout">pre-paginated' in opf:
        look.flag("FIXED-LAYOUT", "package", "pre-paginated book", "pages are pictures or fixed boxes; text order may differ from reading order")
    look.mapline("Chapters (words):\n" + "\n".join(f"  {i + 1}. {c[0]} ({c[1]})" for i, c in enumerate(chapters[:30])) + (f"\n  ... {len(chapters) - 30} more" if len(chapters) > 30 else ""), 60)
    look.write_text("chapters.md", "\n\n".join(f"## {i + 1}. {c[0]} ({c[1]} words)\n{' '.join(re.split(r'(?<=[.!?]) ', c[2])[:3])[:500]}" for i, c in enumerate(chapters)), "each chapter with its first sentences", value=6)
    look.write_text("text.md", "\n\n".join(f"<!-- chapter {i + 1}: {c[0]} -->\n{c[2]}" for i, c in enumerate(chapters)), "the whole text, one block per chapter", value=1, slice_cmd="--page A-B (chapters) or --grep REGEX")
