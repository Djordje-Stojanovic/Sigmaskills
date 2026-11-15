"""Dry self-test of the sigmaclimb template: made-up run folders, the real scripts, no target.
Run: python3 test/sigmaclimb_dry.py   (test/sigmaclimb.test.js runs it under npm test)"""
import json, os, shutil, subprocess, sys, tempfile, unittest, warnings

TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sigmaclimb", "assets", "project-template")
BASH = shutil.which("bash")
warnings.simplefilter("ignore", ResourceWarning)  # the scripts open files the short way; not a defect here


def put(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))


class Climb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj = os.path.join(self.tmp, "proj")
        shutil.copytree(TEMPLATE, self.proj)
        self.project(weights={"a": 0.5, "b": 0.5}, lower_is_better=["b"])
        for name, a, b in (("0001", 10.0, 5.0), ("0002", 10.1, 5.0), ("0003", 9.9, 5.05)):  # A/A: about 1 % noise
            self.run_dir(name, {"a": a, "b": b}, quality=True)
        self.py("scripts/bench/aa.py", "runs/0001", "runs/0002", "runs/0003")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def project(self, **changes):
        path = os.path.join(self.proj, "project.json")
        p = json.load(open(path, encoding="utf-8"))
        for k, v in changes.items():
            p[k] = dict(p[k], **v) if isinstance(v, dict) and isinstance(p.get(k), dict) and k == "heldout" else v
        put(path, p)

    def run_dir(self, name, probes=None, quality=None, change="change A", pairs=None, stages=None):
        raw = os.path.join(self.proj, "runs", name, "raw")
        put(os.path.join(raw, "score.json"), {"pairs": pairs} if pairs else {"probes": probes})
        put(os.path.join(raw, "meta.json"), {"status": "OK", "stage_s": stages or {"start": 60, "score": 300, "quality": 60}})
        put(os.path.join(raw, "change"), change)
        if quality is not None:
            put(os.path.join(raw, "quality.json"), {"ok": quality, "fails": [] if quality else ["needle lost"]})

    def py(self, *args, env=None):
        r = subprocess.run([sys.executable, *args], cwd=self.proj, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode in (0, 1), True, r.stderr)
        return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr

    def verdict(self, *args):
        return self.py("scripts/bench/verdict.py", *args)

    def champion(self):
        return json.load(open(os.path.join(self.proj, "state", "champion.json"), encoding="utf-8"))

    def test_two_ratios_champion_before_and_start(self):
        self.run_dir("0004", {"a": 12.0, "b": 5.0}, quality=True)  # a +20 %: x1.0954 on the score
        self.assertIn("PROMOTED", self.verdict("promote", "runs/0004"))
        self.run_dir("0005", {"a": 13.2, "b": 5.0}, quality=True)  # +10 % over 0004, +32 % over the start
        line = self.verdict("runs/0005")
        self.assertRegex(line, r"^VERDICT KEEP")
        self.assertIn("x1.049 against the champion before", line)
        self.assertIn("x1.149 against the start", line)

    def test_project_json_sets_the_smallest_gain(self):
        self.run_dir("0004", {"a": 10.6, "b": 5.0}, quality=True)  # +3 % on the score; noise is about 1 %
        self.assertRegex(self.verdict("runs/0004"), r"^VERDICT KEEP")
        self.project(min_gain=0.07)  # now even the +6 % probe alone is inside the bar
        self.assertRegex(self.verdict("runs/0004"), r"^VERDICT REJECT: gain \+0\.0296 < 0\.0700")

    def test_stage1_win_is_not_a_keep(self):
        self.run_dir("0004", {"a": 12.0, "b": 5.0})  # no quality.json yet
        self.assertRegex(self.verdict("runs/0004"), r"^VERDICT STAGE1-WIN")
        self.assertIn("REFUSED: the quality check has not run", self.verdict("promote", "runs/0004"))

    def test_a_trade_and_a_side_effect(self):
        self.run_dir("0004", {"a": 13.0, "b": 6.0}, quality=True)  # a +30 %, b 20 % slower
        self.assertRegex(self.verdict("runs/0004"), r"^VERDICT ARCHIVE")

    def test_promote_off_owner_and_confirmation(self):
        self.run_dir("0004", {"a": 10.6, "b": 5.0}, quality=True)  # small gain: needs one confirmation
        self.assertIn("run one confirmation first", self.verdict("promote", "runs/0004"))
        self.run_dir("0005", {"a": 10.7, "b": 5.0}, change="change B")
        self.assertIn("is another change", self.verdict("promote", "runs/0004", "runs/0005"))
        self.run_dir("0005", {"a": 10.7, "b": 5.0})
        self.assertIn("PROMOTED", self.verdict("promote", "runs/0004", "runs/0005"))
        self.assertEqual(self.champion()["runs"], ["runs/0004", "runs/0005"])
        self.run_dir("0006", {"a": 13.0, "b": 6.0}, quality=True)  # a trade: only the owner's word promotes it
        self.assertIn("only the owner's word", self.verdict("promote", "runs/0006"))
        self.assertIn("on the owner's word", self.verdict("promote", "runs/0006", "--owner", "take it, b does not matter to me"))
        self.assertEqual(self.champion()["history"][-1]["owner"], "take it, b does not matter to me")

    def test_heldout_required_names_the_stage(self):
        d = os.path.join(self.tmp, "heldout")
        self.project(heldout={"mode": "required", "dir": d})
        self.run_dir("0004", {"a": 12.0, "b": 5.0}, quality=True)
        self.verdict("runs/0004")
        self.assertIn("REFUSED: held-out check (required): no answer yet", self.verdict("promote", "runs/0004"))

        def owner_check(quality_ok, gain):  # the owner's script; it prints noise and one answer line
            put(os.path.join(d, "check.py"), f'print("detail 1.23")\nprint(\'{{"quality_ok": {quality_ok}, "gain": {gain}}}\')\n')

        owner_check("false", 0.0)
        self.assertIn("SELFTEST FAIL", self.py("scripts/bench/heldout.py", "selftest", self.proj))
        self.assertIn("BROKEN", self.py("scripts/bench/heldout.py", "check", self.proj, "runs/0004"))
        owner_check("true", 0.0)
        self.assertEqual("SELFTEST PASS", self.py("scripts/bench/heldout.py", "selftest", self.proj))
        owner_check("false", 0.09)
        self.assertEqual("FAIL quality", self.py("scripts/bench/heldout.py", "check", self.proj, "runs/0004"))
        self.assertIn("REFUSED: held-out check (required): FAIL quality", self.verdict("promote", "runs/0004"))
        owner_check("true", 0.01)  # visible gain +9.5 %: half of it is the bar
        self.assertEqual("FAIL gain", self.py("scripts/bench/heldout.py", "check", self.proj, "runs/0004"))
        self.assertIn("FAIL gain", self.verdict("promote", "runs/0004"))
        owner_check("true", 0.06)
        self.assertEqual("PASS", self.py("scripts/bench/heldout.py", "check", self.proj, "runs/0004"))
        self.assertIn("PROMOTED", self.verdict("promote", "runs/0004"))
        self.assertEqual(self.champion()["history"][-1]["heldout"], "PASS")

    def test_heldout_advisory_never_blocks(self):
        self.project(heldout={"mode": "advisory", "dir": os.path.join(self.tmp, "none")})
        self.run_dir("0004", {"a": 12.0, "b": 5.0}, quality=True)
        out = subprocess.run([sys.executable, "scripts/bench/verdict.py", "promote", "runs/0004"], cwd=self.proj,
                             capture_output=True, text=True).stdout
        self.assertIn("held-out check (advisory, does not block): not run", out)
        self.assertIn("PROMOTED", out)

    def test_a_judge_measurer_scores_the_share_of_pairs_won(self):
        self.project(measurer="pairs")
        for name, won in (("0001", 10), ("0002", 11), ("0003", 9)):  # the unchanged film against itself
            self.run_dir(name, pairs={"champion": {"won": won, "lost": 20 - won, "tied": 0}})
        self.py("scripts/bench/aa.py", "runs/0001", "runs/0002", "runs/0003")  # spread 0.05: smallest gain 0.10
        self.run_dir("0004", pairs={"champion": {"won": 15, "lost": 4, "tied": 1}, "start": {"won": 17, "lost": 3, "tied": 0}},
                     quality=True)
        line = self.verdict("runs/0004")
        self.assertRegex(line, r"^VERDICT KEEP")
        self.assertIn("won 78% of pairs against the champion before, 85% against the start", line)
        self.run_dir("0005", pairs={"champion": {"won": 11, "lost": 9, "tied": 0}}, quality=True)  # inside the noise
        self.assertRegex(self.verdict("runs/0005"), r"^VERDICT REJECT")

    def test_status_measures_the_loop(self):
        rows = [("1", "BASELINE", "base", "60", "0.9"), ("2", "REJECT", "idea-a", "30", "0.3"),
                ("3", "KEEP", "idea-b", "40", "0.4"), ("4", "KEEP", "idea-b", "20", "0.5")]
        hdr = open(os.path.join(self.proj, "results.tsv"), encoding="utf-8").readline().rstrip("\n").split("\t")
        with open(os.path.join(self.proj, "results.tsv"), "a", encoding="utf-8") as f:
            for p, v, idea, minutes, share in rows:
                row = dict.fromkeys(hdr, "") | {"pass": p, "verdict": v, "idea_id": idea, "minutes": minutes, "score_share": share}
                f.write("\t".join(row[h] for h in hdr) + "\n")
        put(os.path.join(self.proj, "state", "champion.json"), {"runs": [], "probes": {}, "start": {}, "history": [{"keep_to_champion_min": 25}]})
        line = self.py("scripts/status.py")
        self.assertIn("45 min per idea", line)  # 90 minutes over 2 ideas; the baseline does not count
        self.assertIn("25 min from a KEEP to its champion", line)
        self.assertIn("40% of a pass measures the score - UNDER HALF", line)
        self.assertIn("score", subprocess.run([sys.executable, "check_state.py"], cwd=self.proj, capture_output=True, text=True).stdout)

    @unittest.skipUnless(BASH, "needs bash")
    def test_a_slower_run_ends_before_the_quality_check(self):
        put(os.path.join(self.proj, "fake_target.sh"), "\n".join([
            'cmd=$1; shift', 'case "$cmd" in',
            '  score) OUT=$1; echo "{\\"probes\\": {\\"a\\": $FAKE_A, \\"b\\": 5.0}}" > "$OUT/score.json" ;;',
            '  quality) OUT=$1; touch "$OUT/quality_ran"; echo \'{"ok": true, "fails": []}\' > "$OUT/quality.json" ;;',
            'esac', ""]))
        put(os.path.join(self.proj, "change.patch"), "one change")
        env = dict(os.environ, TARGET=os.path.join(self.proj, "fake_target.sh"), PYTHON=sys.executable, CLIMB_ROOT=self.proj)
        for name, a, quality_runs, verdict in (("0004", "9.0", False, "REJECT"), ("0005", "12.0", True, "KEEP")):
            subprocess.run([BASH, "scripts/bench/run_experiment.sh", f"runs/{name}", "change.patch"], cwd=self.proj,
                           env=dict(env, FAKE_A=a), check=True, capture_output=True)
            raw = os.path.join(self.proj, "runs", name, "raw")
            self.assertTrue(os.path.exists(os.path.join(raw, "DONE")))
            self.assertEqual(os.path.exists(os.path.join(raw, "quality_ran")), quality_runs, name)
            self.assertEqual(set(json.load(open(os.path.join(raw, "meta.json")))["stage_s"]) >= {"start", "score", "stop"}, True)
            self.assertRegex(self.verdict(f"runs/{name}"), rf"^VERDICT {verdict}")


if __name__ == "__main__":
    unittest.main()
