"""Run the sigmadeeplook tests, one process per test file, files in parallel.

Default (`npm test`): only the quick files in FAST. Every other file runs real look.py passes over
generated media and takes minutes; set SIGMA_SLOW_TESTS=1 to run them all.
"""
import glob
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
FAST = {
    "test_references_schedule.py", "test_v2_real.py", "test_v2_s18_cleanup.py", "test_v2_ask_fields.py",
    "test_v2_binx.py", "test_v2_r8.py", "test_v2_r8b.py", "test_v2_adapt.py",
}
files = sorted(os.path.basename(f) for f in glob.glob(os.path.join(HERE, "test_*.py")))
if not os.environ.get("SIGMA_SLOW_TESTS"):
    files = [f for f in files if f in FAST]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
root = os.path.dirname(os.path.dirname(HERE))


def run(name):
    start = time.time()
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "test/sigmadeeplook", "-p", name],
                       cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return name, r.returncode, time.time() - start, r.stdout + r.stderr


BUDGET = 60  # seconds of wall time for the default files, together
started = time.time()
bad = 0
with ThreadPoolExecutor(max(2, (os.cpu_count() or 4) - 1)) as pool:
    for name, code, secs, out in pool.map(run, files):
        print(f"{'ok  ' if code == 0 else 'FAIL'} {secs:6.1f}s {name}")
        if code != 0:
            bad += 1
            print(out)
total = time.time() - started
print(f"{len(files) - bad}/{len(files)} files passed in {total:.1f}s")
if not os.environ.get("SIGMA_SLOW_TESTS") and total > BUDGET:
    print(f"FAIL: the default sigmadeeplook tests took {total:.0f}s, over the {BUDGET}s budget; move the slow file out of FAST")
    bad += 1
sys.exit(1 if bad else 0)
