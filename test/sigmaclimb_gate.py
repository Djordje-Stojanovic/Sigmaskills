"""The held-out gate of the sigmaclimb template, with fake numbers and the real scripts.
Run: python3 test/sigmaclimb_gate.py   (test/sigmaclimb-gate.test.js does it under npm test)"""
import hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile, unittest

BENCH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "sigmaclimb", "assets", "project-template", "scripts", "bench")


def put(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))


def make_run(proj, name, k):
    """A run whose every probe is k times the baseline. k=1.2 is a clear KEEP."""
    raw = os.path.join(proj, "runs", name, "raw")
    put(os.path.join(raw, "speed.json"), {
        "replay": {"wall_s": 100 / k, "ttft_p50_s": 1, "turns": []}, "short": {"decode_tps_geo": 50 * k}, "long": {"decode_tps": 30 * k},
        "prefill": {"prefill_tps_geo": 2000 * k, "64k": {"prefill_tps": 2000 * k}, "128k": {"ttft_s": 9}},
        "parallel": {"aggregate_tps": 80 * k}})
    put(os.path.join(raw, "gate.json"), {"tf_top1": 0.99, "tf_dlp": 0.01, "dec_dlp": 0.01, "dec_prefix": 0.9, "reliability_ok": 10,
                                         "reliability_total": 10, "empty_outputs": 0, "looping_outputs": 0})
    put(os.path.join(raw, "meta.json"), {"status": "OK"})
    for n in ("bw_before", "bw_after"):
        put(os.path.join(raw, n + ".json"), {"copy_gbps": 200})
    put(os.path.join(proj, "runs", name, "invariants.json"), {"ok": True, "problems": []})
    put(os.path.join(proj, "runs", name, "serve.sh"), "vllm serve model\n")  # a confirmation run runs the same change


@unittest.skipIf(os.getuid() == 0, "root can write everywhere, so the gate always refuses")
class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.chmod(self.tmp, 0o755)
        self.proj, self.sealed = os.path.join(self.tmp, "proj"), os.path.join(self.tmp, "sealed")
        bench = os.path.join(self.proj, "scripts", "bench")
        os.makedirs(bench)
        for n in ("verdict.py", "heldout.py"):
            shutil.copy(os.path.join(BENCH, n), bench)
        for name, k in (("0001", 1.0), ("0002", 1.2), ("0003", 1.2)):
            make_run(self.proj, name, k)
        put(os.path.join(self.proj, "state", "champion.json"), {"runs": ["runs/0001"]})
        put(os.path.join(self.proj, "project.json"), {"keep_floor": 0.05, "sealed_dir": self.sealed})
        files = {n: hashlib.sha256(pathlib.Path(bench, n).read_bytes()).hexdigest() for n in ("verdict.py", "heldout.py")}
        put(os.path.join(self.proj, "evaluator.lock"), {"files": files, "thresholds": {
            "bw_median": 200, "spread": {}, "score_spread": 0.01, "baseline_runs": ["runs/0001"], "tf_top1_min": 0.99,
            "tf_dlp_max": 0.01, "dec_dlp_max": 0.01, "dec_prefix_min": 0.9, "reliability_min": 10, "looping_max": 0}})
        self.py(os.path.join(bench, "heldout.py"), "init", self.sealed)
        self.set_check(1.15)

    def tearDown(self):
        for sub in ("results",):
            d = os.path.join(self.sealed, sub)
            os.chmod(d, 0o755)
            for f in os.listdir(d):
                os.chmod(os.path.join(d, f), 0o644)
        shutil.rmtree(self.tmp)

    def py(self, *args):
        return subprocess.run([sys.executable, *args], cwd=self.proj, capture_output=True, text=True)

    def verdict(self, *args):
        return self.py(os.path.join(self.proj, "scripts", "bench", "verdict.py"), *args)

    def set_check(self, ratio):
        """The owner's sealed script. It prints secrets and numbers on purpose, to prove none reach the loop."""
        script = os.path.join(self.sealed, "inputs", "check.py")
        put(script, 'import sys\nprint("SECRET-INPUT-42 score 1.07")\nprint("SECRET-INPUT-42", file=sys.stderr)\n'
                    f'print(\'{{"gate_ok": true, "ratio": {ratio}}}\')\n')

    def look(self, run="runs/0002"):
        self.verdict(run)  # the loop writes verdict.json first
        return self.py(os.path.join(self.sealed, "heldout.py"), "check", self.proj, run)

    def lock_results(self):
        d = os.path.join(self.sealed, "results")
        for f in os.listdir(d):
            os.chmod(os.path.join(d, f), 0o444)
        os.chmod(d, 0o555)

    def promote(self):
        self.lock_results()
        r = self.verdict("promote", "runs/0002", "runs/0003")
        champ = json.loads(pathlib.Path(self.proj, "state", "champion.json").read_text())
        return r.stdout.strip().splitlines()[-1], champ

    def test_no_result_is_refused(self):
        self.assertIn("REFUSED: no held-out result for runs/0002", self.promote()[0])
        self.assertEqual(self.promote()[1], {"runs": ["runs/0001"]})

    def test_fail_is_refused(self):
        self.set_check(1.01)  # visible +20 %: half is +10 %, the sealed set shows +1 %
        self.assertEqual(self.look().stdout, "FAIL\n")
        self.assertIn("REFUSED: held-out FAIL", self.promote()[0])

    def test_pass_for_another_change_is_refused(self):
        self.assertEqual(self.look().stdout, "PASS\n")
        put(os.path.join(self.proj, "runs/0002/serve.sh"), "vllm serve model --other-change\n")
        self.assertIn("REFUSED: stale held-out result: change differs", self.promote()[0])

    def test_pass_for_another_config_is_refused(self):
        self.look()
        put(os.path.join(self.proj, "project.json"), {"keep_floor": 0.0, "sealed_dir": self.sealed})
        self.assertIn("REFUSED: stale held-out result: config differs", self.promote()[0])

    def test_pass_for_another_run_is_refused(self):
        self.look("runs/0003")  # 0003 passes, 0002 never looked
        self.assertIn("REFUSED: no held-out result for runs/0002", self.promote()[0])

    def test_forged_pass_is_refused_while_results_are_writable(self):
        self.look()  # a real PASS, but the loop's user could have written it
        r = self.verdict("promote", "runs/0002", "runs/0003")
        self.assertIn("this user can write it", r.stdout)

    def test_matching_pass_promotes_and_a_hand_edit_does_not(self):
        out = self.look()
        self.assertEqual((out.stdout, out.stderr), ("PASS\n", ""))  # no score, no input text leaks
        line, champ = self.promote()
        self.assertTrue(line.startswith("PROMOTED"), line)
        self.assertEqual(champ, {"runs": ["runs/0002", "runs/0003"], "heldout_run": "runs/0002"})
        self.assertNotIn("VOID", self.verdict("runs/0002").stdout)
        put(os.path.join(self.proj, "state", "champion.json"), {"runs": ["runs/0002", "runs/0003"]})  # skip promote
        self.assertIn("VOID: champion has no held-out PASS", self.verdict("runs/0002").stdout)

    def test_sealed_folder_is_closed_to_the_loop_user(self):
        inputs = os.path.join(self.sealed, "inputs")
        self.assertEqual(oct(os.stat(inputs).st_mode & 0o777), "0o700")
        self.assertEqual(oct(os.stat(os.path.join(inputs, "check.py")).st_mode & 0o777), "0o600")
        as_other = ["sudo", "-n", "-u", "nobody"]
        if subprocess.run(as_other + ["true"], capture_output=True).returncode:
            self.skipTest("no passwordless sudo to a second user on this machine")
        readable = subprocess.run(as_other + ["cat", os.path.join(self.sealed, "share")], capture_output=True)
        self.assertEqual(readable.returncode, 0)  # control: the user can reach the folder around the inputs
        for p in (inputs, os.path.join(inputs, "check.py")):
            self.assertNotEqual(subprocess.run(as_other + ["ls" if p == inputs else "cat", p], capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
