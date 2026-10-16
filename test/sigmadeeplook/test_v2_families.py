"""SigmaDeepLook v2 families that need no new install: logs, subtitles, certificates, ML model files, disk images, git bundles, EPUB.

Inputs are generated into temp folders (nothing is downloaded, nothing is executed; the malicious pickle is only scanned).
Each family also has a 'tool missing' test: SIGMADEEPLOOK_HIDE pretends a tool or module is absent and the look must list it
under Not looked at with the install line.
"""
import json
import os
import random
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "sigmadeeplook" / "scripts"
LOOK = SCRIPTS / "look.py"


def run(args, hide=""):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    if hide:
        e["SIGMADEEPLOOK_HIDE"] = hide
    return subprocess.run([sys.executable, str(LOOK), *args], capture_output=True, text=True, encoding="utf-8", env=e, timeout=600)


def make(name, data):
    d = Path(tempfile.mkdtemp(prefix="sdl-fam-"))
    f = d / name
    f.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return f


def look(f, *extra, hide=""):
    out = tempfile.mkdtemp(prefix="sdl-famout-")
    r = run([str(f), "--out", out, "--fresh", "--no-direct", *extra], hide=hide)
    lj = json.loads((Path(out) / "look.json").read_text(encoding="utf-8")) if (Path(out) / "look.json").exists() else None
    return r, Path(out), lj


def flags(lj):
    return {x["kind"] for x in lj["flags"]}


def skipped(lj):
    return [s for s in lj["steps"] if s["status"] == "skipped"]


def text_of(r, out):
    return r.stdout + "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in out.glob("*.md"))


def log_lines():
    random.seed(3)
    t = datetime(2026, 10, 10, 8, 0, 0, tzinfo=timezone.utc)
    out = []
    for i in range(6000):
        t += timedelta(milliseconds=200 + random.random() * 800)
        if i == 3000:
            t += timedelta(minutes=30)
        ts = t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        if i == 4000:
            out.append(f"{ts} WARN pool: connection pool at 95% (max 50)")
        elif i == 4040:
            out += [f"{ts} ERROR db: query failed id=5521 timeout after 30000 ms", "    at com.acme.Db.query(Db.java:88)", "    at com.acme.Svc.run(Svc.java:12)"]
        elif random.random() < 0.8:
            out.append(f"{ts} INFO http: GET /api/items/{random.randint(1, 9999)} 200 {random.randint(3, 90)}ms from 10.0.{random.randint(0, 9)}.{random.randint(1, 250)}")
        else:
            out.append(f"{ts} DEBUG cache: hit key=user:{random.randint(1, 500)}")
    return "\n".join(out) + "\n"


class Logs(unittest.TestCase):
    def test_templates_gap_first_error(self):
        f = make("app.log", log_lines())
        r, out, lj = look(f)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(lj["type"], "log")
        txt = text_of(r, out)
        self.assertIn("ERROR", txt)
        self.assertIn("GAP", flags(lj))
        self.assertRegex(txt, r"GET /api/items/<\*>|GET /api/items/<NUM>")
        self.assertTrue((out / "templates.csv").exists())

    def test_detected_without_extension(self):
        f = make("noext", log_lines())
        r, out, lj = look(f)
        self.assertEqual(lj["type"], "log")


SRT = """1
00:00:01,000 --> 00:00:03,000
Hello there, this is a perfectly normal line.

2
00:00:02,500 --> 00:00:03,500
Overlapping cue that runs into the first one and is far too long to read in one second.

3
00:00:10,000 --> 00:00:12,000
Fin.
"""


class Subtitles(unittest.TestCase):
    def test_srt_overlap_and_speed(self):
        f = make("a.srt", SRT)
        r, out, lj = look(f)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(lj["type"], "subtitle")
        self.assertIn("OVERLAPPING-CUES", flags(lj))
        self.assertTrue((out / "cues.csv").exists())


def self_signed(expired=False):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example.org")])
    now = datetime.now(timezone.utc)
    nb, na = (now - timedelta(days=400), now - timedelta(days=30)) if expired else (now - timedelta(days=1), now + timedelta(days=90))
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1)
            .not_valid_before(nb).not_valid_after(na)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("test.example.org"), x509.DNSName("www.example.org")]), critical=False)
            .sign(key, hashes.SHA256()))
    pem = cert.public_bytes(serialization.Encoding.PEM)
    kpem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return pem, kpem


class Certs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import cryptography  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("cryptography not installed")

    def test_expired_self_signed(self):
        pem, _ = self_signed(expired=True)
        r, out, lj = look(make("c.pem", pem))
        self.assertEqual(lj["type"], "cert")
        self.assertTrue({"EXPIRED", "SELF-SIGNED"} <= flags(lj), flags(lj))
        self.assertIn("test.example.org", r.stdout)

    def test_private_key_never_printed(self):
        _, kpem = self_signed()
        r, out, lj = look(make("k.pem", kpem))
        self.assertIn("PRIVATE-KEY", flags(lj))
        body = kpem.decode().splitlines()[1]
        everything = r.stdout + "".join(p.read_text(encoding="utf-8", errors="replace") for p in out.rglob("*") if p.is_file())
        self.assertNotIn(body, everything)

    def test_tool_missing_row(self):
        pem, _ = self_signed()
        r, out, lj = look(make("c.pem", pem), hide="cryptography,openssl")
        sk = skipped(lj)
        self.assertTrue(any("certificate fields" in s["name"] and "cryptography" in s["install"] for s in sk), sk)
        self.assertIn("Not looked at", r.stdout)


def gguf_bytes():
    def s(x):
        b = x.encode()
        return struct.pack("<Q", len(b)) + b

    def kv_str(k, v):
        return s(k) + struct.pack("<I", 8) + s(v)

    def kv_u32(k, v):
        return s(k) + struct.pack("<I", 4) + struct.pack("<I", v)
    kvs = kv_str("general.architecture", "llama") + kv_str("general.name", "tiny") + kv_u32("general.file_type", 15) + kv_u32("llama.context_length", 4096) + kv_u32("llama.block_count", 2)
    t = s("blk.0.attn.weight") + struct.pack("<I", 2) + struct.pack("<QQ", 64, 64) + struct.pack("<I", 12) + struct.pack("<Q", 0)
    return b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 1) + struct.pack("<Q", 5) + kvs + t + b"\0" * 64


def safetensors_bytes(truncate=False):
    hdr = {"__metadata__": {"format": "pt"}, "model.layers.0.w": {"dtype": "F16", "shape": [10, 10], "data_offsets": [0, 200]}, "model.layers.1.w": {"dtype": "F16", "shape": [10, 10], "data_offsets": [200, 400]}}
    h = json.dumps(hdr).encode()
    return struct.pack("<Q", len(h)) + h + (b"\0" * (100 if truncate else 400))


def pb(field, wt, payload):
    def varint(n):
        o = b""
        while True:
            b = n & 0x7F
            n >>= 7
            o += bytes([b | (0x80 if n else 0)])
            if not n:
                return o
    key = varint(field << 3 | wt)
    return key + (varint(payload) if wt == 0 else varint(len(payload)) + payload)


def onnx_bytes():
    node = pb(4, 2, b"Relu")
    init = pb(1, 0, 3) + pb(1, 0, 4) + pb(2, 0, 1)
    dim = pb(1, 2, pb(1, 0, 1))
    shape = pb(2, 2, dim)
    tt = pb(1, 2, pb(1, 0, 1) + shape)
    vi_in = pb(1, 2, b"x") + pb(2, 2, tt)
    vi_out = pb(1, 2, b"y") + pb(2, 2, tt)
    graph = pb(1, 2, node) + pb(5, 2, init) + pb(11, 2, vi_in) + pb(12, 2, vi_out)
    return pb(1, 0, 8) + pb(2, 2, b"pytorch") + pb(7, 2, graph) + pb(8, 2, pb(2, 0, 17))


EVIL_PICKLE = b"cos\nsystem\n(S'echo pwned'\ntR."
SAFE_PICKLE = b"ccollections\nOrderedDict\n)Rq\x00."


class Models(unittest.TestCase):
    def test_gguf_header_and_name_mismatch(self):
        f = make("tiny-Q8_0.gguf", gguf_bytes())
        r, out, lj = look(f)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(lj["subtype"], "gguf")
        self.assertIn("llama", r.stdout)
        self.assertIn("QUANT-MISMATCH", flags(lj))
        self.assertEqual(lj["facts"]["parameters"], 4096)

    def test_safetensors_and_truncation(self):
        r, out, lj = look(make("m.safetensors", safetensors_bytes()))
        self.assertEqual(lj["facts"]["parameters"], 200)
        self.assertNotIn("TRUNCATED", flags(lj))
        r, out, lj = look(make("t.safetensors", safetensors_bytes(truncate=True)))
        self.assertIn("TRUNCATED", flags(lj))

    def test_onnx_graph_walk(self):
        r, out, lj = look(make("m.onnx", onnx_bytes()))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(lj["facts"]["parameters"], 12)
        self.assertIn("Relu", r.stdout)

    def test_evil_pickle_flagged_and_never_run(self):
        sentinel = Path(tempfile.gettempdir()) / "sdl-pwned.txt"
        evil = b"cos\nsystem\n(S'echo x > " + str(sentinel).replace("\\", "/").encode() + b"'\ntR."
        sentinel.unlink(missing_ok=True)
        r, out, lj = look(make("evil.pkl", evil))
        self.assertIn("PICKLE-EXEC", flags(lj))
        self.assertFalse(sentinel.exists(), "the pickle must never be executed")

    def test_plain_pickle_not_flagged_exec(self):
        r, out, lj = look(make("ok.pkl", SAFE_PICKLE))
        self.assertNotIn("PICKLE-EXEC", flags(lj))

    def test_hdf5_needs_h5py_row(self):
        f = make("w.h5", b"\x89HDF\r\n\x1a\n" + b"\0" * 2048)
        r, out, lj = look(f, hide="h5py")
        self.assertEqual(lj["type"], "model")
        self.assertTrue(any("h5py" in s["install"] for s in skipped(lj)), skipped(lj))


class DiskImages(unittest.TestCase):
    def test_qcow2_backing_file(self):
        parent = b"base.qcow2"
        off = 112
        hdr = b"QFI\xfb" + struct.pack(">IQIIQI", 3, off, len(parent), 16, 10 << 30, 0)
        data = hdr + b"\0" * (off - len(hdr)) + parent + b"\0" * 512
        r, out, lj = look(make("d.qcow2", data))
        self.assertEqual(lj["type"], "diskimage")
        self.assertIn("BACKING-FILE", flags(lj))
        self.assertIn("NOT-MOUNTED", flags(lj))
        self.assertEqual(lj["facts"]["virtual_size"], 10 << 30)

    def test_7zip_missing_row(self):
        hdr = b"QFI\xfb" + struct.pack(">IQIIQI", 3, 0, 0, 16, 1 << 30, 0)
        r, out, lj = look(make("d.qcow2", hdr + b"\0" * 1024), hide="7z")
        self.assertTrue(any(s["tool"] == "7z" and s["install"] for s in skipped(lj)), skipped(lj))


class GitBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shutil
        if not shutil.which("git"):
            raise unittest.SkipTest("git not installed")

    def test_complete_bundle_and_missing_git_row(self):
        d = Path(tempfile.mkdtemp(prefix="sdl-git-"))
        env = dict(os.environ, GIT_AUTHOR_NAME="a", GIT_AUTHOR_EMAIL="a@x", GIT_COMMITTER_NAME="a", GIT_COMMITTER_EMAIL="a@x")
        g = lambda *a: subprocess.run(["git", "-C", str(d), *a], env=env, capture_output=True, check=True)   # noqa: E731
        g("init", "-q")
        for i in range(3):
            (d / f"f{i}.txt").write_text(str(i))
            g("add", ".")
            g("-c", "commit.gpgsign=false", "commit", "-q", "-m", f"c{i}")
        b = d.parent / (d.name + ".bundle")
        g("bundle", "create", str(b), "--all")
        r, out, lj = look(b)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(lj["facts"]["commits"], 3)
        self.assertNotIn("INCOMPLETE-BUNDLE", flags(lj))
        r, out, lj = look(b, hide="git")
        self.assertTrue(any(s["tool"] == "git" and s["install"] for s in skipped(lj)), skipped(lj))
        self.assertFalse(list(out.glob("_bare")), "no clone folder is left behind")

    def test_incomplete_bundle_flagged(self):
        head = b"# v2 git bundle\n-" + b"a" * 40 + b" prereq\n" + b"b" * 40 + b" refs/heads/main\n\nPACK"
        r, out, lj = look(make("inc.bundle", head + b"\0" * 64))
        self.assertIn("INCOMPLETE-BUNDLE", flags(lj))


def epub_bytes(drm=False):
    import io
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        z.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf", '<package><metadata xmlns:dc="x"><dc:title>My Book</dc:title><dc:creator>An Author</dc:creator><dc:language>en</dc:language></metadata>'
                   '<manifest><item id="c1" href="c1.xhtml"/><item id="c2" href="c2.xhtml"/></manifest><spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>')
        z.writestr("OEBPS/c1.xhtml", "<html><body><h1>One</h1><p>" + "word " * 120 + "</p></body></html>")
        z.writestr("OEBPS/c2.xhtml", "<html><body><h1>Two</h1><p>" + "other " * 80 + "</p></body></html>")
        if drm:
            z.writestr("META-INF/encryption.xml", '<encryption><EncryptedData><EncryptionMethod Algorithm="http://www.w3.org/2001/04/xmlenc#aes128-cbc"/></EncryptedData></encryption>')
    return b.getvalue()


class Epub(unittest.TestCase):
    def test_chapters_and_words(self):
        r, out, lj = look(make("b.epub", epub_bytes()))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(lj["facts"]["chapters"], 2)
        self.assertGreaterEqual(lj["facts"]["words"], 200)
        self.assertIn("My Book", r.stdout)
        self.assertNotIn("DRM", flags(lj))

    def test_drm_flagged(self):
        r, out, lj = look(make("d.epub", epub_bytes(drm=True)))
        self.assertIn("DRM", flags(lj))


if __name__ == "__main__":
    unittest.main()
