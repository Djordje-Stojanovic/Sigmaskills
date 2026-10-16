"""SigmaDeepLook v2 video and audio checks: event runs, adaptive cuts, silence hallucinations, loudness, model-missing rows."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "sigmadeeplook" / "scripts"
LOOK = SCRIPTS / "look.py"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))
import dl_core as core  # noqa: E402
import dl_mediax as M  # noqa: E402

FFMPEG = shutil.which("ffmpeg")


def mk_look():
    d = Path(tempfile.mkdtemp(prefix="sdl-mx-"))
    f = d / "x.mp4"
    f.write_bytes(b"\0" * 100)
    opts = Namespace(no_tools=False, tier="standard", quick=False, deep=False, budget=None, extract=False, recurse=0, allow_network=False, reader="claude", mode="overview")
    return core.Look(f, d / "out", opts)


class Pure(unittest.TestCase):
    def test_runs_merge_close_events(self):
        r = M.runs([(1.0, 1.1), (1.3, 1.4), (1.6, 1.7), (9.0, 10.0)], gap=0.5)
        self.assertEqual([(a, b, n) for a, b, n in r], [(1.0, 1.7, 3), (9.0, 10.0, 1)])

    def test_flag_runs_calls_a_burst_a_burst(self):
        look = mk_look()
        M.flag_runs(look, "BLACK", [(i * 0.2, i * 0.2 + 0.1) for i in range(14)], 1.0, "of black", "hint")
        self.assertEqual(len(look.flags), 1)
        self.assertIn("14 events", look.flags[0]["value"])

    def test_parse_and_adaptive(self):
        text = "frame:0 pts:1 pts_time:2\nlavfi.scene_score=0.844343\nframe:1 pts:2 pts_time:4\nlavfi.scene_score=0.200000\nframe:2 pts:3 pts_time:30\nlavfi.scene_score=0.130000\n"
        c = M.parse_scene_scores(text)
        self.assertEqual(c, [(2.0, 0.844343), (4.0, 0.2), (30.0, 0.13)])
        cuts = M.adaptive_cuts(c)
        self.assertEqual([t for t, _ in cuts], [2.0, 4.0, 30.0], "a soft cut next to a hard one is still a cut; a lone 0.13 in a quiet stretch is one too")

    def test_noise_among_neighbours_is_not_a_cut(self):
        c = [(10 + i * 0.1, 0.13) for i in range(10)]
        self.assertEqual(M.adaptive_cuts(c), [], "a flicker of equal scores is not a series of cuts")

    def test_silence_hallucination(self):
        look = mk_look()
        look.silence_runs = [(10.0, 20.0)]
        M.silence_hallucinations(look, [{"start": 11.0, "end": 14.0, "text": "Thanks for watching"}, {"start": 30.0, "end": 33.0, "text": "real speech"}])
        self.assertEqual([f["kind"] for f in look.flags], ["HALLUCINATION?"])

    def test_loudness_line(self):
        look = mk_look()
        M.loudness_line(look, [-60.0] * 20 + [-20.0] * 20, 20.0)
        self.assertTrue(any("Loudness over time" in s for s in look.summary))

    def test_models_missing_give_install_rows(self):
        look = mk_look()
        saved = set(core.HIDE)
        core.HIDE.update({"yunet", "pyannote", "ast"})
        try:
            M.faces_row(look)
            M.audio_adapters(look, None, [], 10.0)
        finally:
            core.HIDE.clear()
            core.HIDE.update(saved)
        tools = {s["tool"]: s["install"] for s in look.steps if s["status"] == "skipped"}
        self.assertEqual(set(tools), {"yunet", "pyannote", "ast"})
        self.assertTrue(all(tools.values()))


@unittest.skipUnless(FFMPEG, "ffmpeg not installed")
class RealVideo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(tempfile.mkdtemp(prefix="sdl-mv-"))
        cls.file = d / "t.mp4"
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x240:d=2:r=25", "-f", "lavfi", "-i", "smptebars=s=320x240:d=2:r=25",
                        "-f", "lavfi", "-i", "rgbtestsrc=s=320x240:d=2:r=25", "-f", "lavfi", "-i", "sine=f=440:d=6",
                        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0,format=yuv420p[v]", "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(cls.file)], check=True)
        cls.out = Path(tempfile.mkdtemp(prefix="sdl-mvo-"))
        cls.r = subprocess.run([sys.executable, str(LOOK), str(cls.file), "--out", str(cls.out), "--fresh"], capture_output=True, text=True, encoding="utf-8", timeout=600,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        cls.lj = json.loads((cls.out / "look.json").read_text(encoding="utf-8"))

    def test_two_cuts_found(self):
        self.assertEqual(self.r.returncode, 0, self.r.stderr)
        self.assertEqual(self.lj["facts"]["scene_cuts"], 2)
        self.assertIn("Scene cuts: 2", "\n".join(self.lj["summary"]))

    def test_loudness_over_time_and_model_rows(self):
        self.assertIn("Loudness over time", "\n".join(self.lj["summary"]))
        names = " ".join(s["name"] for s in self.lj["steps"] if s["status"] == "skipped")
        self.assertIn("faces in the frames", names)
        self.assertIn("who speaks when", names)

    def test_at_zoom_does_not_wipe_the_cache(self):
        r = subprocess.run([sys.executable, str(LOOK), str(self.file), "--out", str(self.out), "--at", "0:02", "--len", "2"], capture_output=True, text=True, encoding="utf-8", timeout=600,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("window 0:02", r.stdout)
        self.assertIn("zoom sheet", r.stdout)
        self.assertTrue((self.out / "look.json").exists())


if __name__ == "__main__":
    unittest.main()
