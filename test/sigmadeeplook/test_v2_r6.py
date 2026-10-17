"""SigmaDeepLook round 6 (ticket 83 P0.14b, 17-10 owner: "make deeplook the helper for hard tasks").

Gate routing (plain text is read by the agent at any size; media, scans, binaries and non-UTF-8 text go to the look),
the stdlib PDF page map (a page without a text layer must not shift the page numbers), and the one-line-break rule for
Flate streams (the last compressed byte may be a newline, and it is data). Standard library only.
"""
import re
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "sigmadeeplook" / "scripts"
FX = HERE / "fixtures"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))

import dl_docs  # noqa: E402
import dl_gate  # noqa: E402

from test_v2 import run  # noqa: E402


def gate_of(path, *extra):
    r = run(["gate", str(path), *extra])
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def tmp_file(name, data):
    d = Path(tempfile.mkdtemp(prefix="sdl-r6-"))
    f = d / name
    f.write_bytes(data)
    return f


class GateRouting(unittest.TestCase):
    def test_plain_text_and_data_are_read_at_any_size(self):
        big_log = tmp_file("big.log", ("2026-10-17 10:00:00 INFO request id=1 ms=3\n" * 30000).encode())
        self.assertRegex(gate_of(big_log), r"^READ .+over one read: query it with python or grep\)$")
        big_json = tmp_file("big.json", ('{"id": 1, "name": "row"}\n' * 30000).encode())
        self.assertRegex(gate_of(big_json), r"^READ .+over one read")
        bom_csv = tmp_file("bom.csv", b"\xef\xbb\xbfid,name\n1,a\n2,b\n")
        self.assertRegex(gate_of(bom_csv), r"^READ .+ \(~\d+ tokens\)$")
        empty = tmp_file("empty.csv", b"")
        self.assertRegex(gate_of(empty), r"^READ .+ \(~0 tokens\)$")

    def test_text_that_is_not_utf8_goes_to_the_look(self):
        cp = tmp_file("latin.csv", "id,city\n1,Wien\n2,Zürich\n".encode("cp1252"))
        self.assertRegex(gate_of(cp), r"^LOOK standard .+not UTF-8 text")
        u16 = tmp_file("wide.csv", "id,city\n1,Wien\n".encode("utf-16"))
        self.assertRegex(gate_of(u16), r"^LOOK standard .+not UTF-8 text")

    def test_big_embedded_text_and_outlook_msg_are_not_plain_text(self):
        page = tmp_file("big.html", ("<p>hello</p>\n" * 40000).encode())
        self.assertRegex(gate_of(page), r"^LOOK standard .+over one read: its parts")
        small_page = tmp_file("small.html", b"<p>hi</p>\n")
        self.assertRegex(gate_of(small_page), r"^READ .+ \(~\d+ tokens\)$")
        msg = FX / "msg.msg"
        if msg.exists():
            self.assertRegex(gate_of(msg), r"^LOOK standard .+email \(msg\): binary or container$")

    def test_media_and_binaries_go_to_the_look(self):
        for name, pattern in (("clip.mp4", r"^LOOK standard .+video"), ("app.sqlite", r"^LOOK standard .+binary or container"),
                              ("ok.tar.gz", r"^LOOK standard .+binary or container"), ("speech.wav", r"^LOOK standard .+audio")):
            self.assertRegex(gate_of(FX / name), pattern, name)

    def test_budget_turns_plain_text_into_a_look(self):
        f = tmp_file("some.csv", ("id,v\n" + "".join(f"{i},{i * 7 % 13}\n" for i in range(3000))).encode())
        self.assertRegex(gate_of(f, "--budget", "200"), r"^LOOK standard .+over your --budget 200")


class StdlibPdfPages(unittest.TestCase):
    def test_a_page_without_text_keeps_the_later_page_numbers(self):
        out = Path(tempfile.mkdtemp(prefix="sdl-pdf-")) / "look"
        r = run([str(FX / "mixed.pdf"), "--no-tools", "--out", str(out), "--fresh"])
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (out / "text.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"<!-- page 1 -->\n\s*Left column")
        self.assertRegex(text, r"<!-- page 2 -->\n\s*\n<!-- page 3 -->\nForm page: please enter your name below", text)


class FlateTrailingBytes(unittest.TestCase):
    def test_only_one_line_break_is_removed_before_endstream(self):
        text = b"BT /F1 12 Tf 50 740 Td (Only page) Tj ET"
        pad = b""
        while True:   # the compressed stream must end with a newline byte, which is data, not a line break
            comp = zlib.compress(text + pad)
            if comp.endswith(b"\n"):
                break
            pad += b" "
        pdf = (b"%PDF-1.4\n"
               b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
               b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
               b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>\nendobj\n"
               b"4 0 obj\n<< /Length " + str(len(comp)).encode() + b" /Filter /FlateDecode >>\nstream\n" + comp + b"\nendstream\nendobj\n"
               b"%%EOF\n")
        f = tmp_file("one.pdf", pdf)
        raw = dl_docs.pdf_raw(str(f))
        self.assertEqual(raw["page_texts"], ["Only page"])


if __name__ == "__main__":
    unittest.main()
