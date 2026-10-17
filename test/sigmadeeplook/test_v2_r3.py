"""SigmaDeepLook v2 fix round 3 (ticket 83 P0.14): a smaller first print with every fact kept.

Decimal sizes, claim-ranked speech gist, log error templates with first and last time and the burst start, the root cause as a
finding, the pptx outline and its contradiction flag, squeezed spreadsheet rows, the content cap of step 1, the deleted text as a
finding, and the speaker count line. Everything is generated here; nothing is downloaded or executed.
"""
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "sigmadeeplook" / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE))
import dl_core as core  # noqa: E402
import dl_docs  # noqa: E402
import dl_logs  # noqa: E402
import dl_media  # noqa: E402
import dl_mediax  # noqa: E402
import dl_write as W  # noqa: E402
from test_v2 import run  # noqa: E402
from test_v2_fix import docx_bytes  # noqa: E402


class Sizes(unittest.TestCase):
    def test_sizes_are_decimal_megabytes(self):
        self.assertEqual(core.human(185_174_099), "185.2 MB")
        self.assertEqual(core.human(999), "999 B")
        self.assertEqual(core.human(1_500_000), "1.5 MB")
        self.assertEqual(core.human(2_000_000_000), "2.0 GB")

    def test_a_binary_megabyte_is_not_printed_as_a_megabyte(self):
        self.assertEqual(core.human(1 << 20), "1.0 MB")   # 1.048 MB rounds to 1.0, not 1.05 of a "MB" that was a MiB
        self.assertEqual(core.human(176_600_000), "176.6 MB")


class Gist(unittest.TestCase):
    def segs(self):
        rows = [(0, "Every factory on Earth runs into the same wall, power."),
                (9, "So here is the experiment. One plot of land, six and a half megawatts, with every watt accounted for."),
                (33, "14 systems, five companies, the same power. Tonight we find out what each one buys you."),
                (120, "We walk through the history of the idea and why it matters to a lot of people."),
                (300, "Another sentence without any figure at all, only words and more words here."),
                (710, "The final standings from 2.4 to 36 exaflops, a 15-fold spread on the same power."),
                (800, "Thanks for watching, and see you in the next one, bye for now everyone.")]
        return [{"start": s, "text": t} for s, t in rows]

    def test_claims_beat_the_middle_of_the_film(self):
        out = dl_media.gist_lines(self.segs(), 857, None)
        text = " / ".join(out)
        self.assertIn("[0:00] Every factory", text)
        self.assertIn("six and a half megawatts", text)
        self.assertIn("14 systems", text)
        self.assertIn("15-fold", text)
        self.assertNotIn("history of the idea", text)

    def test_no_figures_falls_back_to_quotes(self):
        segs = [{"start": i * 20, "text": f"This is a plain sentence number {'x' * i} about nothing in particular, really."} for i in range(8)]
        out = dl_media.gist_lines(segs, 160, None)
        self.assertGreaterEqual(len(out), 2)

    def test_section_turns_name_where_a_new_part_starts(self):
        segs = [{"start": 764, "text": "Now, the money, hardware ranges from about $64 million to over 600 million"},
                {"start": 9, "text": "So here is the experiment, one plot of land."},
                {"start": 95, "text": "Next, the yardstick. Every system is scored the same way."}]
        self.assertEqual(dl_media.section_turns(sorted(segs, key=lambda s: s["start"])), ["[1:35] the yardstick", "[12:44] the money"])

    def test_claim_score(self):
        self.assertEqual(dl_media.claim_score("no numbers here at all"), 0)
        self.assertGreater(dl_media.claim_score("a 15-fold spread"), dl_media.claim_score("one thing"))

    def test_clip_keeps_the_unit_in_view(self):
        t = "word " * 40 + "then six and a half megawatts at the meter and more words after it"
        c = dl_media.clip_around(t, 115)
        self.assertIn("megawatts", c)
        self.assertLessEqual(len(c), 125)


class Speakers(unittest.TestCase):
    def test_line_states_count_and_turns(self):
        class L:
            def __init__(self):
                self.facts, self.lines = {}, []

            def fact(self, k, v):
                self.facts[k] = v

            def line(self, s, pri=50, tag=""):
                self.lines.append(s)
        look = L()
        dl_mediax.speaker_line(look, [{"speaker": "A", "start": 0, "end": 10}, {"speaker": "A", "start": 12, "end": 30}])
        self.assertEqual(look.facts["speakers"], 1)
        self.assertEqual(look.facts["speaker_turns"], 2)
        self.assertRegex(look.lines[0], r"Speakers: 1 voice .*2 turns")
        look = L()
        dl_mediax.speaker_line(look, [{"speaker": "A", "start": 0, "end": 10}, {"speaker": "B", "start": 10, "end": 30}, {"speaker": "A", "start": 30, "end": 40}])
        self.assertRegex(look.lines[0], r"Speakers: 2 voices.*3 turns, 2 changes")


def make_log(path, burst=True):
    rnd = random.Random(3)
    lines, t = [], 0
    for i in range(6000):
        t += rnd.choice((1, 1, 2))
        h, rem = divmod(t, 3600)
        stamp = f"2026-10-14 {2 + h:02d}:{rem // 60:02d}:{rem % 60:02d}"
        lines.append(f"{stamp} INFO [api] GET /v1/items status=200 ms={rnd.randint(5, 90)} req={1000 + i}")
        if i % 400 == 7:
            lines.append(f"{stamp} ERROR [api] GET /v1/orders status=500 ms=273 req={5000 + i}")
        if burst and i == 3000:
            lines.append(f"{stamp} WARN [db] disk quota 98 percent on /var/lib/postgres, writes will slow")
        if burst and 3030 <= i < 3060:
            lines.append(f"{stamp}.{(i * 37) % 1000:03d} ERROR [api] upstream timeout calling payments after 5000ms req={9000 + i}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


class LogBurst(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(tempfile.mkdtemp(prefix="sdl-r3-"))
        cls.f = d / "app.log"
        make_log(cls.f)
        cls.out = Path(tempfile.mkdtemp(prefix="sdl-r3o-"))
        cls.r = run([str(cls.f), "--out", str(cls.out), "--no-tools", "--fresh"])
        cls.lj = json.loads((cls.out / "look.json").read_text(encoding="utf-8"))

    def test_error_templates_carry_count_first_and_last_time(self):
        self.assertEqual(self.r.returncode, 0, self.r.stderr)
        row = next(l for l in self.r.stdout.splitlines() if "upstream timeout calling payments" in l and "|" in l and "lines" in l)
        self.assertRegex(row, r"30x \[ERROR\].*\| \d\d:\d\d:\d\d(\.\d+)? to \d\d:\d\d:\d\d(\.\d+)? \| lines \d+-\d+")

    def test_burst_start_time_is_named(self):
        self.assertIn("ERROR-BURST", self.r.stdout)
        m = [l for l in self.r.stdout.splitlines() if "ERROR-BURST" in l][0]
        self.assertRegex(m, r"@ \d\d:\d\d:\d\d(\.\d+)?: 30x \[ERROR\]")

    def test_the_warning_before_the_burst_is_a_finding_with_its_offset(self):
        m = [l for l in self.r.stdout.splitlines() if "ROOT-CAUSE-EARLIER?" in l][0]
        self.assertIn("disk quota 98 percent", m)
        self.assertRegex(m, r"\d+ s before the error burst at \d\d:\d\d:\d\d")

    def test_flat_log_without_a_burst_has_no_burst_flag(self):
        d = Path(tempfile.mkdtemp(prefix="sdl-r3f-"))
        f = d / "flat.log"
        make_log(f, burst=False)
        r = run([str(f), "--out", str(d / "o"), "--no-tools", "--fresh"])
        self.assertNotIn("ERROR-BURST", r.stdout)

    def test_log_files_are_not_printed_twice(self):
        self.assertNotIn("## Content: templates.csv", self.r.stdout)
        self.assertNotIn("## Content: rare.md", self.r.stdout)


class Pptx(unittest.TestCase):
    def recs(self):
        out = []
        for i in range(1, 11):
            title = "Q3 Planning Review" if i == 1 else "Revenue 2026: 4.2M EUR" if i == 5 else f"Slide {i} topic"
            note = "Say that revenue is 3.1M EUR this year, not 4.2M." if i == 5 else (f"Talk track for slide {i}: keep it short." if i % 2 else "")
            out.append((i, [title, f"Point A for slide {i}."], note, i == 8))
        return out

    def test_ranges(self):
        self.assertEqual(dl_docs.ranges([1, 2, 3, 5, 7, 8]), "1-3, 5, 7-8")

    def test_outline_says_repeats_once_and_lists_odd_slides(self):
        lines, bad = dl_docs.pptx_outline(self.recs())
        text = "\n".join(lines)
        self.assertIn("1 Q3 Planning Review", text)
        self.assertIn("5 Revenue 2026: 4.2M EUR", text)
        self.assertIn("titled 'Slide N topic'", text)
        self.assertIn("Say that revenue is 3.1M EUR", text)
        self.assertLess(len(text), 900)

    def test_note_that_contradicts_the_slide_is_returned(self):
        _, bad = dl_docs.pptx_outline(self.recs())
        self.assertEqual([b[0] for b in bad], [5])
        self.assertEqual(bad[0][1], "4.2M")

    def test_agreeing_note_is_not_a_contradiction(self):
        r = [(1, ["Revenue 2026: 4.2M EUR"], "Say that revenue is 4.2M EUR this year.", False)]
        self.assertEqual(dl_docs.pptx_outline(r)[1], [])


class Spreadsheet(unittest.TestCase):
    def test_rows_that_differ_only_in_digits_are_said_once(self):
        rows = [f"| {i} |  |  |" for i in range(1, 6)]
        out = dl_docs.squeeze_rows(rows)
        self.assertEqual(out[0], "| 1 |  |  |")
        self.assertIn("4 more row(s) like the one above", out[1])
        self.assertEqual(len(out), 2)

    def test_real_rows_stay(self):
        rows = ["| a | 1 |", "| b | 2 |"]
        self.assertEqual(dl_docs.squeeze_rows(rows), rows)


class DocxFinding(unittest.TestCase):
    def test_deleted_sum_of_money_is_in_the_flag_not_only_in_text_md(self):
        d = Path(tempfile.mkdtemp(prefix="sdl-r3d-"))
        f = d / "a.docx"
        f.write_bytes(docx_bytes())
        r = run([str(f), "--out", str(d / "o"), "--no-tools", "--fresh"])
        line = [l for l in r.stdout.splitlines() if "TRACKED-CHANGES" in l][0]
        self.assertIn("$250,000", line)
        self.assertIn("deleted but still in the file", line)


class StepOne(unittest.TestCase):
    def stream(self):
        s = [{"id": 0, "sec": "head", "pri": 1000, "tag": "identity", "text": "# x", "tok": 10}]
        for k in range(3):
            s.append({"id": len(s), "sec": "key", "pri": 80 - k, "tag": "", "text": "fact " * 20, "tok": 40})
        for k in range(8):
            s.append({"id": len(s), "sec": "content", "pri": 23, "tag": "text.md", "text": "line " * 40, "tok": 60, "line": 1 + k, "line_end": 1 + k})
        return s

    def test_raw_content_in_step_one_is_capped(self):
        s = self.stream()
        chunks, nxt = W.window(s, 0, 900, False, W.CONTENT_FIRST)
        body = sum(c["tok"] for c in chunks if c["sec"] == "content")
        self.assertLessEqual(body, W.CONTENT_FIRST + 60)
        self.assertLess(nxt, len(s))
        more, end = W.window(s, nxt, 900)
        self.assertEqual(end, len(s))   # the cursor continues where step one stopped

    def test_without_a_cap_the_window_fills(self):
        chunks, nxt = W.window(self.stream(), 0, 900, False)
        self.assertEqual(nxt, len(self.stream()))

    def test_new_trap_kinds_rank_first(self):
        for k in ("ERROR-BURST", "ROOT-CAUSE-EARLIER?", "NOTE-CONTRADICTS-SLIDE"):
            self.assertEqual(W.kind_pri(k), 100)


if __name__ == "__main__":
    unittest.main()
