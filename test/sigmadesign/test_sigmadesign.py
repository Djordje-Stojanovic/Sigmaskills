import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sigmadesign" / "scripts"))
import sigmadesign as sd  # noqa: E402


class Contrast(unittest.TestCase):
    def test_known_values(self):
        self.assertAlmostEqual(sd.contrast("#000000", "#ffffff"), 21.0, places=1)
        self.assertAlmostEqual(sd.contrast("#777777", "#ffffff"), 4.48, places=1)

    def test_hex_forms(self):
        self.assertEqual(sd.hex_to_rgb("#fff"), (255, 255, 255))
        with self.assertRaises(ValueError):
            sd.hex_to_rgb("blue")


class Create(unittest.TestCase):
    def test_any_accent_passes_its_own_check(self):
        # a pale yellow, a dark navy, a grey and a saturated green: the tool must fix the accent, not ship a failing pair
        for accent in ("#fde047", "#1e1b4b", "#808080", "#34d399", "#ff0000"):
            with tempfile.TemporaryDirectory() as td:
                sd.new(Path(td) / "d", "T", accent, None, 6.0, "Inter", "soft")
                self.assertEqual(sd.check(Path(td) / "d" / "DESIGN.md"), [], accent)

    def test_new_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            sd.new(Path(td), "T", "#34d399", None, 6.0, "Inter", "soft")
            with self.assertRaises(FileExistsError):
                sd.new(Path(td), "T", "#34d399", None, 6.0, "Inter", "soft")

    def test_front_matter_round_trips(self):
        with tempfile.TemporaryDirectory() as td:
            sd.new(Path(td), "Round Trip", "#e8a33d", 215, 14.0, "Space Grotesk", "round")
            data, packs = sd.load_design(Path(td) / "DESIGN.md")
            self.assertEqual(data["name"], "Round Trip")
            self.assertTrue(data["colors"]["primary"].startswith("#"))
            self.assertIn("light-primary", data["colors"])
            self.assertTrue(data["typography"]["display"]["fontFamily"].startswith("Space Grotesk"))
            self.assertEqual(data["components"]["button-primary"]["backgroundColor"], "{colors.primary}")
            self.assertEqual(packs, {})

    def test_prose_still_has_fill_markers(self):
        with tempfile.TemporaryDirectory() as td:
            p = sd.new(Path(td), "T", "#34d399", None, 6.0, "Inter", "soft")
            self.assertIn("FILL", p.read_text(encoding="utf-8"))


class PacksAndBuild(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)
        self.design = sd.new(self.d / "a", "T", "#34d399", None, 6.0, "Inter", "soft")

    def tearDown(self):
        self.td.cleanup()

    def test_packs_dark_and_light(self):
        self.assertEqual(sd.add_pack(self.design, "yellow-black", "#fbbf24"), [])
        self.assertEqual(sd.add_pack(self.design, "red-white", "#dc2626", light=True), [])
        _, packs = sd.load_design(self.design)
        self.assertEqual(set(packs), {"yellow-black", "red-white"})
        self.assertEqual(packs["red-white"]["mode"], "light")
        self.assertEqual(sd.check(self.design), [])

    def test_build_writes_every_theme_and_no_literal_in_components(self):
        sd.add_pack(self.design, "blue-black", "#60a5fa")
        out = self.d / "out"
        sd.build(self.design, out)
        css = (out / "tokens.css").read_text(encoding="utf-8")
        for needle in (":root {", ':root[data-theme="light"]', ':root[data-theme="blue-black"]', "--primary:", "--radius-md:"):
            self.assertIn(needle, css)
        self.assertNotRegex((out / "components.css").read_text(encoding="utf-8"), r"#[0-9a-fA-F]{3,6}\b")
        self.assertIn("blue-black", (out / "index.html").read_text(encoding="utf-8"))
        self.assertIn("--color-primary: var(--primary)", (out / "tailwind.css").read_text(encoding="utf-8"))

    def test_check_finds_a_stale_build_and_a_bad_pair(self):
        out = self.d / "out"
        sd.build(self.design, out)
        self.assertEqual(sd.check(self.design, out), [])
        text = self.design.read_text(encoding="utf-8")
        self.design.write_text(text.replace("  mute: ", "  mute: \"#222222\"\n  mute-old: ", 1), encoding="utf-8")
        problems = sd.check(self.design, out)
        self.assertTrue(any("mute on surface" in p for p in problems), problems)
        self.assertTrue(any("stale" in p for p in problems), problems)

    def test_cli_exit_codes(self):
        self.assertEqual(sd.main(["check", str(self.design)]), 0)
        self.assertEqual(sd.main(["check", str(self.d / "missing" / "DESIGN.md")]), 2)


class Integrate(unittest.TestCase):
    def test_scan_rewrites_only_exact_css_matches(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            design = sd.new(d / "a", "T", "#34d399", None, 6.0, "Inter", "soft")
            data, _ = sd.load_design(design)
            primary = data["colors"]["primary"]
            repo = d / "repo"
            (repo / "node_modules" / "x").mkdir(parents=True)
            (repo / "node_modules" / "x" / "a.css").write_text("a{color:#123456}", encoding="utf-8")
            (repo / "site.css").write_text("a{color:%s;border:1px solid #abcdef}" % primary.upper(), encoding="utf-8")
            (repo / "page.html").write_text('<i style="color:%s">' % primary, encoding="utf-8")
            rows, changed = sd.scan(repo, design, write=True)
            self.assertEqual(changed, 1)
            self.assertIn("var(--primary)", (repo / "site.css").read_text(encoding="utf-8"))
            self.assertIn("#abcdef", (repo / "site.css").read_text(encoding="utf-8"))
            self.assertIn(primary, (repo / "page.html").read_text(encoding="utf-8"))
            self.assertNotIn("#123456", [r["value"] for r in rows])

    def test_integrate_copies_bytes_and_adds_one_pointer(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            design = sd.new(d / "a", "T", "#34d399", None, 6.0, "Inter", "soft")
            design.write_bytes(design.read_bytes().replace(b"\n", b"\r\n"))
            repo = d / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_bytes(b"# Agents\n\nRules.\n")
            self.assertTrue(any("will be" in r for r in sd.integrate(design, repo)))
            self.assertFalse((repo / "DESIGN.md").exists())
            sd.integrate(design, repo, write=True)
            self.assertEqual((repo / "DESIGN.md").read_bytes(), design.read_bytes())
            sd.integrate(design, repo, write=True)
            self.assertEqual((repo / "AGENTS.md").read_text(encoding="utf-8").count("DESIGN.md"), 1)


if __name__ == "__main__":
    unittest.main()
