"""guardrail_lint (plan 2026-10-17, D8): no new model-authored prohibition lands in an agent-facing doc.

Contract:
- the repo's agent-facing docs pass the lint (the keep-list holds every vetted line);
- a banned line in a fresh doc fails the lint, a mechanical guard and an allowlisted keep pass (the script's --selftest);
- the keep-list exists and is a plain text file the owner can veto line by line.
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "guardrail_lint.py"
ALLOW = ROOT / "scripts" / "guardrail_allowlist.txt"


class GuardrailLint(unittest.TestCase):
    def test_the_repo_has_no_new_prohibition(self):
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_ban_fails_and_keeps_pass(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--selftest"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("selftest PASS", r.stdout)

    def test_the_keep_list_is_plain_text(self):
        self.assertTrue(ALLOW.exists(), "scripts/guardrail_allowlist.txt exists")
        lines = [ln for ln in ALLOW.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
        self.assertTrue(lines, "the keep-list holds at least one entry")


if __name__ == "__main__":
    unittest.main()
