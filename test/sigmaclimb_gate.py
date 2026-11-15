"""The held-out gate of the sigmaclimb template, with fake numbers and the real scripts.
The sealing user is `nobody` (passwordless sudo needed); the loop's user is whoever runs this. Else the tests skip.
Run: python3 test/sigmaclimb_gate.py   (test/sigmaclimb-gate.test.js does it under npm test)"""
import hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile, unittest

AS = ["sudo", "-n", "-u", "nobody"]
CAN_SEAL = os.getuid() != 0 and subprocess.run(AS + ["true"], capture_output=True).returncode == 0

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


@unittest.skipUnless(CAN_SEAL, "needs a non-root user with passwordless sudo to `nobody`: the gate needs a second user")
class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.chmod(self.tmp, 0o777)  # `nobody` makes the sealed folder in here
        self.proj, self.sealed = os.path.join(self.tmp, "proj"), os.path.join(self.tmp, "sealed")
        self.bench = os.path.join(self.proj, "scripts", "bench")
        os.makedirs(self.bench)
        for n in ("verdict.py", "heldout.py"):
            shutil.copy(os.path.join(BENCH, n), self.bench)
        for name, k in (("0001", 1.0), ("0002", 1.2), ("0003", 1.2)):
            make_run(self.proj, name, k)
        put(os.path.join(self.proj, "state", "champion.json"), {"runs": ["runs/0001"]})
        self.set_project(self.sealed)
        files = {n: hashlib.sha256(pathlib.Path(self.bench, n).read_bytes()).hexdigest() for n in ("verdict.py", "heldout.py")}
        put(os.path.join(self.proj, "evaluator.lock"), {"files": files, "thresholds": {
            "bw_median": 200, "spread": {}, "score_spread": 0.01, "baseline_runs": ["runs/0001"], "tf_top1_min": 0.99,
            "tf_dlp_max": 0.01, "dec_dlp_max": 0.01, "dec_prefix_min": 0.9, "reliability_min": 10, "looping_max": 0}})
        self.sealer("init", self.sealed)
        self.set_check(1.15)

    def tearDown(self):
        subprocess.run(AS + ["rm", "-rf", self.sealed], capture_output=True)
        shutil.rmtree(self.tmp)

    def set_project(self, sealed):
        put(os.path.join(self.proj, "project.json"), {"keep_floor": 0.05, "sealed_dir": sealed})

    def sealer(self, *args, script=None):
        """Run heldout.py as the sealing user."""
        return subprocess.run(AS + [sys.executable, script or os.path.join(self.bench, "heldout.py"), *args], capture_output=True, text=True)

    def verdict(self, *args):
        return subprocess.run([sys.executable, os.path.join(self.bench, "verdict.py"), *args], cwd=self.proj, capture_output=True, text=True)

    def set_check(self, ratio, extra=""):
        """The owner's sealed script. It prints secrets and numbers on purpose, to prove none reach the loop."""
        code = ('import sys\nprint("SECRET-INPUT-42 score 1.07")\nprint("SECRET-INPUT-42", file=sys.stderr)\n' + extra +
                f'print(\'{{"gate_ok": true, "ratio": {ratio}}}\')\n')
        subprocess.run(AS + ["tee", os.path.join(self.sealed, "inputs", "check.py")], input=code, text=True, capture_output=True, check=True)

    def look(self, run="runs/0002"):
        self.verdict(run)  # the loop writes verdict.json first
        return self.sealer("check", self.proj, run, script=os.path.join(self.sealed, "heldout.py"))

    def promote(self):
        r = self.verdict("promote", "runs/0002", "runs/0003")
        champ = json.loads(pathlib.Path(self.proj, "state", "champion.json").read_text())
        return r.stdout.strip().splitlines()[-1], champ

    def test_no_result_is_refused(self):
        self.verdict("runs/0002")  # a KEEP with a visible gain
        line, champ = self.promote()
        self.assertIn("REFUSED: no held-out result for runs/0002", line)
        self.assertEqual(champ, {"runs": ["runs/0001"]})

    def test_fail_is_refused(self):
        self.set_check(1.01)  # visible +20 %: half is +10 %, the sealed set shows +1 %
        self.assertEqual(self.look().stdout, "FAIL\n")
        self.assertIn("REFUSED: held-out FAIL", self.promote()[0])

    def test_pass_for_another_change_is_refused(self):
        self.assertEqual(self.look().stdout, "PASS\n")
        put(os.path.join(self.proj, "runs/0002/serve.sh"), "vllm serve model --other-change\n")
        self.assertIn("REFUSED: stale held-out result: change differs", self.promote()[0])

    def test_pass_for_another_confirmation_change_is_refused(self):
        self.look()
        put(os.path.join(self.proj, "runs/0003/serve.sh"), "vllm serve model --other-change\n")
        self.assertIn("REFUSED: a confirmation run is another change", self.promote()[0])

    def test_pass_for_another_config_is_refused(self):
        self.look()
        put(os.path.join(self.proj, "project.json"), {"keep_floor": 0.0, "sealed_dir": self.sealed})
        self.assertIn("REFUSED: stale held-out result: config differs", self.promote()[0])

    def test_pass_for_another_score_is_refused(self):
        self.look()
        make_run(self.proj, "0001", 0.9)  # the champion got slower, so the fresh score of 0002 is higher than at the look
        self.assertIn("REFUSED: stale held-out result: score differs", self.promote()[0])

    def test_pass_for_another_run_is_refused(self):
        self.look("runs/0003")  # 0003 passes, 0002 never looked
        self.assertIn("REFUSED: no held-out result for runs/0002", self.promote()[0])

    def test_forged_pass_in_a_folder_the_loop_owns_is_refused(self):
        self.look()
        forged = os.path.join(self.tmp, "forged")  # same files, but this user made them
        shutil.copytree(self.sealed, forged, ignore=shutil.ignore_patterns("inputs"))
        self.set_project(forged)
        os.chmod(os.path.join(forged, "results"), 0o555)  # even read-only, it is the loop's own folder
        self.assertIn("this user owns or can write it", self.promote()[0])
        os.chmod(os.path.join(forged, "results"), 0o755)

    def test_matching_pass_promotes_and_a_hand_edit_does_not(self):
        out = self.look()
        self.assertEqual((out.stdout, out.stderr), ("PASS\n", ""))  # no score, no input text leaks
        line, champ = self.promote()
        self.assertTrue(line.startswith("PROMOTED"), line)
        self.assertEqual(champ, {"runs": ["runs/0002", "runs/0003"], "heldout_run": "runs/0002"})
        self.assertNotIn("VOID", self.verdict("runs/0002").stdout)
        put(os.path.join(self.proj, "state", "champion.json"), {"runs": ["runs/0002", "runs/0003"]})  # skip promote
        self.assertIn("VOID: champion has no held-out PASS", self.verdict("runs/0002").stdout)

    def test_a_crash_or_bad_output_is_a_fail(self):
        self.set_check(1.15, extra="sys.exit(3)\n")
        self.assertEqual(self.look().stdout, "FAIL\n")
        self.verdict("runs/0003")
        subprocess.run(AS + ["tee", os.path.join(self.sealed, "inputs", "check.py")], input="print('not json')\n", text=True, capture_output=True)
        self.assertEqual(self.sealer("check", self.proj, "runs/0003", script=os.path.join(self.sealed, "heldout.py")).stdout, "FAIL\n")

    def test_a_change_that_moves_during_the_check_is_a_fail(self):
        swap = f'open({os.path.join(self.proj, "runs/0002/serve.sh")!r}, "w").write("other")\n'
        os.chmod(os.path.join(self.proj, "runs/0002/serve.sh"), 0o666)
        self.set_check(1.15, extra=swap)
        self.assertEqual(self.look().stdout, "FAIL\n")

    def test_one_look_per_run_and_a_spent_set(self):
        self.assertEqual(self.look().stdout, "PASS\n")
        self.set_check(1.0)
        self.assertEqual(self.look().stdout, "PASS\n")  # same run: the stored answer, no second look
        self.sealer("init", self.sealed, "--looks", "1")
        self.assertEqual(self.look("runs/0003").stdout, "FAIL\n")  # spent
        self.assertFalse(os.path.exists(os.path.join(self.sealed, "results", "0003.json")))

    def test_sealed_folder_is_closed_to_the_loop_user(self):
        inputs = os.path.join(self.sealed, "inputs")
        self.assertEqual(oct(os.stat(inputs).st_mode & 0o777), "0o700")
        self.assertNotEqual(os.stat(inputs).st_uid, os.getuid())  # the sealing user owns it
        self.assertTrue(os.path.exists(os.path.join(self.sealed, "share")))  # control: the rest of the folder is open
        with self.assertRaises(PermissionError):
            os.listdir(inputs)
        with self.assertRaises(PermissionError):
            open(os.path.join(inputs, "check.py")).read()


if __name__ == "__main__":
    unittest.main()
