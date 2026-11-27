"""Dry self-test of the sigmaclimb template: made-up run folders, the real scripts, no target.
Run: python3 test/sigmaclimb_dry.py   (test/sigmaclimb.test.js runs it under npm test)"""
import csv, importlib.util, json, os, shlex, shutil, socket, subprocess, sys, tempfile, time, unittest
from pathlib import Path

TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sigmaclimb", "assets", "project-template")
def command(code):
    args = [sys.executable, "-c", code]
    return subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)


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
        self.py("climb.py", "lock", "runs/0001", "runs/0002", "runs/0003")

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
        shutil.rmtree(raw, ignore_errors=True)  # a new run starts empty, as the runner does
        put(os.path.join(raw, "score.json"), {"pairs": pairs} if pairs else {"probes": probes})
        put(os.path.join(raw, "meta.json"), {"status": "OK", "stage_s": stages or {"start": 60, "score": 300, "quality": 60}})
        put(os.path.join(raw, "change"), change)
        put(os.path.join(self.proj, "runs", name, "invariants.json"), {"ok": True, "problems": []})
        if quality is not None:
            put(os.path.join(raw, "quality.json"), {"ok": quality, "fails": [] if quality else ["needle lost"]})

    def py(self, *args, env=None):
        r = subprocess.run([sys.executable, *args], cwd=self.proj, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode in (0, 1), True, r.stderr)
        return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr

    def verdict(self, *args):
        return self.py("climb.py", *args) if args[0] == "promote" else self.py("climb.py", "verdict", *args)

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

    def test_a_missing_probe_or_invariants_check_is_never_a_pass(self):
        self.run_dir("0004", {"a": 13.0}, quality=True)  # b not measured
        self.assertIn("VERDICT CRASH: probes the champion has are missing: ['b']", self.verdict("runs/0004"))
        self.run_dir("0005", {"a": 13.0, "b": 5.0}, quality=True)
        os.remove(os.path.join(self.proj, "runs", "0005", "invariants.json"))
        self.assertRegex(self.verdict("runs/0005"), r"^VERDICT VOID: no invariants.json")
        self.project(invariants=False)
        self.assertRegex(self.verdict("runs/0005"), r"^VERDICT KEEP")

    def test_a_trade_and_a_side_effect(self):
        self.run_dir("0004", {"a": 13.0, "b": 6.0}, quality=True)  # a +30 %, b 20 % slower
        self.assertRegex(self.verdict("runs/0004"), r"^VERDICT ARCHIVE")

    def test_promote_off_owner_and_confirmation(self):
        self.run_dir("0004", {"a": 10.6, "b": 5.0}, quality=True)  # small gain: needs one confirmation
        self.assertIn("run one confirmation first", self.verdict("promote", "runs/0004"))
        self.run_dir("0005", {"a": 10.7, "b": 5.0}, change="change B", quality=True)
        self.assertIn("is another change", self.verdict("promote", "runs/0004", "runs/0005"))
        self.run_dir("0005", {"a": 10.7, "b": 5.0})  # no quality check on the confirmation: not a KEEP
        self.assertIn("is not a KEEP", self.verdict("promote", "runs/0004", "runs/0005"))
        self.run_dir("0005", {"a": 10.7, "b": 5.0}, quality=True)
        self.assertIn("PROMOTED", self.verdict("promote", "runs/0004", "runs/0005"))
        self.assertEqual(self.champion()["runs"], ["runs/0004", "runs/0005"])
        self.run_dir("0006", {"a": 13.0, "b": 6.0}, quality=True)  # a trade: only the owner's word promotes it
        self.assertIn("only the owner's word", self.verdict("promote", "runs/0006"))
        self.assertIn("on the owner's word", self.verdict("promote", "runs/0006", "--owner", "take it, b does not matter to me"))
        self.assertEqual(self.champion()["history"][-1]["owner"], "take it, b does not matter to me")

    def test_heldout_required_names_the_stage(self):
        self.configure_steps()
        d = os.path.join(self.tmp, "heldout")
        self.project(heldout={"mode": "required", "dir": d})
        self.run_dir("0004", {"a": 12.0, "b": 5.0}, quality=True)
        self.verdict("runs/0004")
        self.assertIn("REFUSED: held-out check (required): no answer yet", self.verdict("promote", "runs/0004"))

        def owner_check(quality_ok, gain):  # the owner's script; it prints noise and one answer line
            put(os.path.join(d, "check.py"), f'print("detail 1.23")\nprint(\'{{"quality_ok": {quality_ok}, "gain": {gain}}}\')\n')

        owner_check("false", 0.0)
        self.assertIn("SELFTEST FAIL", self.py("climb.py", "heldout", "selftest"))
        self.assertIn("BROKEN", self.py("climb.py", "heldout", "check", "runs/0004"))
        put(os.path.join(d, "check.py"), 'import os, sys\nok = os.path.isfile(os.path.join(sys.argv[1], "project.json")) '
            'and os.path.isfile(os.path.join(sys.argv[2], "raw", "score.json"))\n'
            'print(\'{"quality_ok": %s, "gain": 0.0}\' % ("true" if ok else "false"))\n')
        self.assertEqual("SELFTEST PASS", self.py("climb.py", "heldout", "selftest"))
        owner_check("false", 0.09)
        self.assertEqual("FAIL quality", self.py("climb.py", "heldout", "check", "runs/0004"))
        self.assertIn("REFUSED: held-out check (required): FAIL quality", self.verdict("promote", "runs/0004"))
        owner_check("true", 0.01)  # visible gain +9.5 %: half of it is the bar
        self.assertEqual("FAIL gain", self.py("climb.py", "heldout", "check", "runs/0004"))
        self.assertIn("FAIL gain", self.verdict("promote", "runs/0004"))
        change = os.path.join(self.proj, "runs", "0004", "raw", "change")
        with open(change, "wb") as f:
            f.write(b"change A\nline 2\n")
        owner_check("true", 0.06)
        self.assertEqual("PASS", self.py("climb.py", "heldout", "check", "runs/0004"))
        with open(change, "wb") as f:  # the same change with Windows line endings is still the change checked
            f.write(b"change A\r\nline 2\r\n")
        self.assertIn("PROMOTED", self.verdict("promote", "runs/0004"))
        self.assertEqual(self.champion()["history"][-1]["heldout"], "PASS")

    def test_heldout_selftest_has_a_time_cap(self):
        d = Path(self.tmp, "heldout")
        self.configure_steps(step_seconds=1)
        self.project(heldout={"dir": str(d), "mode": "required"})
        put(d / "check.py", "import time; time.sleep(60)")
        result = subprocess.run([sys.executable, "climb.py", "heldout", "selftest"], cwd=self.proj,
                                capture_output=True, text=True, timeout=5)
        self.assertIn("SELFTEST FAIL", result.stdout)
        self.assertFalse(json.loads((d / "selftest.json").read_text())["ok"])

    def test_heldout_advisory_never_blocks(self):
        self.project(heldout={"mode": "advisory", "dir": os.path.join(self.tmp, "none")})
        self.run_dir("0004", {"a": 12.0, "b": 5.0}, quality=True)
        out = subprocess.run([sys.executable, "climb.py", "promote", "runs/0004"], cwd=self.proj,
                             capture_output=True, text=True).stdout
        self.assertIn("held-out check (advisory, does not block): not run", out)
        self.assertIn("PROMOTED", out)

    def test_human_picks_score_the_share_of_pairs_won(self):
        self.project(measurer="pairs")
        for name, won in (("0001", 10), ("0002", 11), ("0003", 9)):  # the unchanged film against itself
            self.run_dir(name, pairs={"champion": {"won": won, "lost": 20 - won, "tied": 0}})
        self.py("climb.py", "lock", "runs/0001", "runs/0002", "runs/0003")  # spread 0.05: smallest gain 0.10
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
        line = self.py("climb.py", "status")
        self.assertIn("45 min per idea", line)  # 90 minutes over 2 ideas; the baseline does not count
        self.assertIn("25 min from a KEEP to its champion", line)
        self.assertIn("40% of a pass measures the score - UNDER 50%", line)
        self.assertIn("score", subprocess.run([sys.executable, "climb.py", "check"], cwd=self.proj, capture_output=True, text=True).stdout)

    def configure_steps(self, step_seconds=5, pass_seconds=20, **steps):
        self.project(budget={"step_seconds": step_seconds, "pass_seconds": pass_seconds, "run_hours": None},
                     steps={key: command(code) for key, code in steps.items()})
        put(os.path.join(self.proj, "change.patch"), "one change")
        lock = os.path.join(self.proj, "evaluator.lock")
        put(lock, dict(json.load(open(lock, encoding="utf-8")), steps=json.load(open(os.path.join(self.proj, "project.json"), encoding="utf-8"))["steps"]))

    def run_pass(self, run, *args):
        return subprocess.run([sys.executable, "climb.py", "run", run, "change.patch", *args],
                              cwd=self.proj, capture_output=True, text=True, timeout=10)

    def test_a_slower_run_ends_before_the_quality_check(self):
        for run, value, quality_runs, verdict in (("runs/0004", 9, False, "REJECT"), ("runs/0005", 12, True, "KEEP"),
                                                  ("runs/0007", 9, True, "REJECT"),
                                                  (os.path.join(self.tmp, "external", "0006"), 12, True, "KEEP")):
            raw = Path(self.proj, run, "raw")
            put(raw.parent / "invariants.json", {"ok": True})
            self.configure_steps(
                score="import os; from pathlib import Path; assert Path(os.environ['CLIMB_CHANGE']).read_text() == 'one change'; "
                      f"Path(os.environ['CLIMB_OUT'], 'score.json').write_text({json.dumps({'probes': {'a': value, 'b': 5}})!r})",
                quality="import os; from pathlib import Path; Path(os.environ['CLIMB_OUT'], 'quality.json').write_text('{\"ok\":true}')")
            r = self.run_pass(run, "--full") if run == "runs/0007" else self.run_pass(run)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((raw / "DONE").exists())
            self.assertEqual((raw / "quality.json").exists(), quality_runs, run)
            self.assertTrue(set(json.loads((raw / "meta.json").read_text())["stage_s"]) >= {"start", "score", "stop"})
            self.assertRegex(self.verdict(run), rf"^VERDICT {verdict}")

    def test_guards_from_the_review_round(self):
        write = "import os, sys; from pathlib import Path; out = Path(os.environ['CLIMB_OUT']); "
        self.configure_steps(score=write + "(out / 'status').write_text('OK'); (out / 'score.json').write_text('{\"probes\": {\"a\": 12, \"b\": 5}}')",
                             quality=write + "(out / 'quality.json').write_text('{\"ok\": true}'); sys.exit(1)")
        put(os.path.join(self.proj, "runs", "0004", "invariants.json"), {"ok": True})
        self.assertEqual(self.run_pass("runs/0004").returncode, 0)
        self.assertRegex(self.verdict("runs/0004"), r"^VERDICT CRASH: run status quality exited 1")  # a status file hides no failed step
        again = self.run_pass("runs/0004")  # a finished run keeps its evidence
        self.assertEqual((again.returncode, "already holds a finished run" in again.stdout), (2, True))
        self.project(steps={"score": "echo less work"})  # the step commands are part of the scorer
        self.assertRegex(self.verdict("runs/0004"), r"^VERDICT VOID: the step commands")
        self.configure_steps()
        self.run_dir("0005", {"a": 10.6, "b": 5.0}, quality=True)  # a small gain cannot confirm itself
        self.assertIn("is the run itself", self.verdict("promote", "runs/0005", "runs/./0005"))
        self.run_dir("0006", {"a": 10.6, "b": -1}, quality=True)  # a probe that went negative is a gap, not a pass
        self.assertIn("VERDICT CRASH: probes the champion has are missing: ['b']", self.verdict("runs/0006"))
        self.run_dir("0007", {"a": 10.6, "b": 5.0})  # a half-written file is a CRASH
        put(os.path.join(self.proj, "runs", "0007", "raw", "quality.json"), '{"ok": tr')
        self.assertRegex(self.verdict("runs/0007"), r"^VERDICT CRASH: run status unreadable raw file")
        results = Path(self.proj, "results.tsv")
        for run in ("0005", "0006"):  # a last row without its newline is not joined to the next one
            self.py("climb.py", "record", "--run", f"runs/{run}", "--idea", "x", "--category", "c", "--work", "CODE",
                    "--part", "p", "--desc", "d", "--verdict", "REJECT")
            results.write_text(results.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")
        self.assertEqual([line.split("\t")[0] for line in results.read_text(encoding="utf-8").splitlines()], ["pass", "5", "6"])
        r = subprocess.run([sys.executable, "climb.py", "lock", "runs/0001", "runs/0001", "runs/0002"], cwd=self.proj,
                           capture_output=True, text=True)
        self.assertIn("NOT LOCKED: the same run is named twice", r.stderr)

    def test_budget_is_required_before_any_step(self):
        for step, total in ((None, 3), (3, 0), (-1, 3), (True, 3)):
            self.configure_steps(step_seconds=step, pass_seconds=total,
                                 start="from pathlib import Path; Path('started').touch()")
            result = self.run_pass("runs/0004")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(len((result.stdout + result.stderr).splitlines()), 1)
            self.assertFalse(Path(self.proj, "started").exists())

    def test_timeout_kills_child_and_runs_stop(self):
        # The grandchild owns a listening socket. Binding the same port proves that it died.
        child = "import socket,time; from pathlib import Path; s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen(); Path('port').write_text(str(s.getsockname()[1])); time.sleep(60)"
        put(os.path.join(self.proj, "child.py"), child)
        spawn = "import subprocess,sys,time; subprocess.Popen([sys.executable,'child.py']); time.sleep(60)"
        for run, step, total, cap in (("runs/0004", 2, 8, "step_seconds"), ("runs/0005", 8, 2, "pass_seconds")):
            self.configure_steps(step, total, warmup=spawn, stop="from pathlib import Path; Path('stopped').touch()")
            start = time.monotonic()
            result = self.run_pass(run)
            self.assertLess(time.monotonic() - start, 8)
            self.assertEqual(result.returncode, 0, result.stderr)
            raw = Path(self.proj, run, "raw")
            self.assertEqual(json.loads((raw / "meta.json").read_text())["status"], "TIMEOUT")
            self.assertRegex(self.verdict(run), rf"^VERDICT CRASH: .*warmup.*{cap}.*2")
            self.assertTrue(json.loads(Path(self.proj, "state/pass.json").read_text())["finished"])
            port = Path(self.proj, "port")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", int(port.read_text())))
            port.unlink()
            Path(self.proj, "stopped").unlink()

    def test_stalled_and_finished_status(self):
        self.configure_steps()
        root = Path(self.proj)
        put(root / "state/pass.json", {"run": "runs/0004", "started": time.time()-60, "finished": False, "pid": 1})
        stalled = self.py("climb.py", "status")
        self.assertRegex(stalled, r"^LOOP STALLED: .*runs/0004.*kill it, record the CRASH, take the next idea")
        self.py("climb.py", "record", "--run", "runs/0004", "--idea", "hung", "--category", "setup",
                "--work", "SETTING", "--part", "all", "--desc", "killed", "--verdict", "CRASH")
        self.assertRegex(self.py("climb.py", "status"), "^LOOP RUNNING:")  # the recorded CRASH clears the stall
        (root / "STOP").touch()
        (root / "REPORT.md").touch()
        self.assertRegex(self.py("climb.py", "status"), "^LOOP FINISHED:")
        (root / "STOP").unlink()
        self.project(budget={"step_seconds": 5, "pass_seconds": 20, "run_hours": 1})
        self.py("climb.py", "record", "--run", "runs/0001", "--idea", "base", "--category", "setup",
                "--work", "SETTING", "--part", "all", "--desc", "start", "--verdict", "BASELINE")
        p = root / "results.tsv"
        rows = p.read_text().splitlines()
        first = rows[1].split("\t")
        first[1] = "2000-01-01T00:00Z"
        p.write_text(rows[0] + "\n" + "\t".join(first) + "\n")
        self.assertRegex(self.py("climb.py", "status"), "^LOOP FINISHED:")

    def test_locked_scoring_files(self):
        scorer = Path(self.proj, "score.py")
        scorer.write_text("print(1)")
        self.project(locked=["score.py"])
        self.py("climb.py", "lock", "runs/0001", "runs/0002", "runs/0003")
        lock = json.loads(Path(self.proj, "evaluator.lock").read_text())
        self.assertEqual(set(lock["files"]), {"climb.py", "score.py"})
        scorer.write_text("print(2)")
        self.assertIn("VERDICT VOID: scorer file changed: score.py", self.verdict("runs/0001"))

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "matplotlib is not installed")
    def test_progress_draws_sample_results(self):
        root = Path(self.proj)
        p = root / "results.tsv"
        fields = p.read_text().strip().split("\t")
        with p.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fields, delimiter="\t")
            for i, (v, score) in enumerate((("BASELINE", 1), ("AA", 1.01), ("AA", .99), ("REJECT", .98),
                                            ("KEEP", 1.1), ("REJECT", 1.07), ("KEEP", 1.2), ("CRASH", "")), 1):
                writer.writerow({"pass": i, "verdict": v, "vs_start": score})
        r = subprocess.run([sys.executable, str(root / "progress.py")], cwd=self.tmp, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        png = (root / "progress.png").read_bytes()
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(png), 4096)

    def test_aa_refuses_a_band_from_nothing(self):
        for name in ("0001", "0002", "0003"):
            self.run_dir(name, {"a": None, "b": None})
        r = subprocess.run([sys.executable, "climb.py", "lock", "runs/0001", "runs/0002", "runs/0003"], cwd=self.proj,
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("NOT LOCKED", r.stderr)


if __name__ == "__main__":
    unittest.main(warnings="ignore")
